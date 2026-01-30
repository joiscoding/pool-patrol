#!/usr/bin/env python3
"""Run LangSmith evaluation experiments for the Shift Specialist agent.

This module evaluates the Shift Specialist agent against the LangSmith dataset.
The agent accepts employee_ids directly, matching the dataset format.

Usage:
    # Run from project root:
    poetry run python -m eval.run_evaluation
    
    # With direct mode (faster):
    poetry run python -m eval.run_evaluation --direct

Requirements:
    - LANGSMITH_API_KEY environment variable set
    - OPENAI_API_KEY environment variable set
"""

import os
import sys
from pathlib import Path
from typing import Any

# Project root is two levels up from this file
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Add packages to path for imports
sys.path.insert(0, str(PROJECT_ROOT / "packages"))

from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langsmith import Client
from langsmith.evaluation import evaluate
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Import from the agents package (after path setup)
from agents.state import ShiftVerificationResult
from agents.shift_specialist import verify_employee_shifts_sync
from agents.utils import parse_legacy_verification_result
from tools.shifts import get_employee_shifts


# =============================================================================
# Configuration
# =============================================================================

DATASET_NAME = "shift-specialist-eval-small"
EXPERIMENT_PREFIX = "shift-specialist"

OUTPUT_PARSER = PydanticOutputParser(pydantic_object=ShiftVerificationResult)


def get_model():
    """Get the LLM model for the agent."""
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0,
    )


# =============================================================================
# Target Functions (what we're evaluating)
# =============================================================================


def get_shifts_for_employees(employee_ids: list[str]) -> list[dict]:
    """Fetch shift info for all employees.
    
    Returns list of dicts with employee_id, shift_name, and any errors.
    """
    shifts = []
    for emp_id in employee_ids:
        result = get_employee_shifts.invoke({"employee_id": emp_id})
        shifts.append({
            "employee_id": emp_id,
            "shift_name": result.get("shift_name", "Unknown"),
            "error": result.get("error"),
        })
    return shifts


def target_function_direct(inputs: dict) -> dict:
    """Direct LLM evaluation (faster, no agent tool-calling).
    
    This version pre-fetches all shift data and passes it directly to the LLM,
    which is faster than having the agent call tools iteratively.
    """
    employee_ids = inputs.get("employee_ids", [])
    
    # Handle empty list edge case
    if not employee_ids:
        return {
            "verdict": "fail",
            "reasoning": "No employees provided. Cannot verify shift compatibility with an empty list.",
        }
    
    # Pre-fetch all shift data
    shifts = get_shifts_for_employees(employee_ids)
    
    # Build context for the LLM
    shift_summary = "\n".join([
        f"- {s['employee_id']}: {s['shift_name']}" + (f" (Error: {s['error']})" if s.get('error') else "")
        for s in shifts
    ])
    
    prompt = f"""You are the Shift Specialist. Analyze whether these employees have compatible shifts for carpooling.

Employee Shifts:
{shift_summary}

Rules:
- All employees must work the SAME shift type to be compatible
- A single employee always passes (no conflict possible)
- If there are employees with different shift types, return "fail"

{OUTPUT_PARSER.get_format_instructions()}"""

    model = get_model()
    response = model.invoke(prompt)
    
    return parse_result(response.content)


def parse_result(content: str) -> dict:
    """Parse the agent's response into verdict and reasoning."""
    try:
        result = OUTPUT_PARSER.parse(content)
        return {
            "verdict": result.verdict,
            "reasoning": result.reasoning,
        }
    except Exception:
        try:
            result = parse_legacy_verification_result(content, ShiftVerificationResult)
            return {
                "verdict": result.verdict,
                "reasoning": result.reasoning,
            }
        except Exception as e:
            # Fallback: try to extract verdict from text
            content_lower = content.lower()
            if '"verdict": "pass"' in content_lower or '"verdict":"pass"' in content_lower:
                verdict = "pass"
            elif '"verdict": "fail"' in content_lower or '"verdict":"fail"' in content_lower:
                verdict = "fail"
            else:
                verdict = "fail"  # Default to fail if we can't parse
            
            return {
                "verdict": verdict,
                "reasoning": f"Parse error: {e}. Raw: {content[:200]}",
            }


def target_function(inputs: dict) -> dict:
    """Target function for LangSmith evaluation.
    
    This function takes the dataset inputs and returns outputs that can be
    compared against the expected outputs. Uses the main Shift Specialist agent
    which now accepts employee_ids directly.
    
    Args:
        inputs: Dict with "employee_ids" key containing list of employee IDs
        
    Returns:
        Dict with "verdict" and "reasoning" keys
    """
    employee_ids = inputs.get("employee_ids", [])
    
    # Use the main agent directly (now accepts employee_ids)
    result = verify_employee_shifts_sync(employee_ids)
    
    return {
        "verdict": result.verdict,
        "reasoning": result.reasoning,
    }


# =============================================================================
# Evaluators
# =============================================================================


def verdict_match(outputs: dict, reference_outputs: dict) -> bool:
    """Check if the verdict matches exactly.
    
    This is the primary metric - did the agent correctly identify
    whether the shift combination is valid or not?
    """
    predicted = outputs.get("verdict")
    expected = reference_outputs.get("verdict")
    
    return {
        "key": "verdict_match",
        "score": predicted == expected
    }

# LLM-as-judge evaluator for correctness checks
# Uses openevals prebuilt CORRECTNESS_PROMPT
correctness_evaluator = create_llm_as_judge(
    prompt=CORRECTNESS_PROMPT,
    feedback_key="correctness",
    model="openai:gpt-4.1-mini",
)


# =============================================================================
# Main Evaluation Runner
# =============================================================================


def run_evaluation(
    dataset_name: str = DATASET_NAME,
    experiment_prefix: str = EXPERIMENT_PREFIX,
    max_concurrency: int = 4,
    use_agent: bool = True,
) -> Any:
    """Run the evaluation experiment on LangSmith.
    
    Args:
        dataset_name: Name of the LangSmith dataset to evaluate against
        experiment_prefix: Prefix for the experiment name
        max_concurrency: Maximum concurrent evaluations
        use_agent: If True, use the full agent with tool-calling. 
                   If False, use direct LLM evaluation (faster).
        
    Returns:
        Evaluation results from LangSmith
    """
    print("=" * 60)
    print("Pool Patrol - Shift Specialist Evaluation")
    print("=" * 60)
    
    # Verify environment
    if not os.environ.get("LANGSMITH_API_KEY"):
        raise ValueError("LANGSMITH_API_KEY environment variable not set")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    # Enable LangSmith tracing
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", "pool-patrol-eval")
    
    # Check dataset exists
    client = Client()
    datasets = list(client.list_datasets(dataset_name=dataset_name))
    if not datasets:
        raise ValueError(f"Dataset '{dataset_name}' not found. Run create_langsmith_dataset.py first.")
    
    dataset = datasets[0]
    example_count = len(list(client.list_examples(dataset_id=dataset.id)))
    
    # Select target function
    target_fn = target_function if use_agent else target_function_direct
    mode = "agent (with tool-calling)" if use_agent else "direct (pre-fetched data)"
    
    print(f"\nDataset: {dataset_name}")
    print(f"Examples: {example_count}")
    print(f"Experiment prefix: {experiment_prefix}")
    print(f"Max concurrency: {max_concurrency}")
    print(f"Model: {os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini')}")
    print(f"Mode: {mode}")
    print(f"Evaluators: verdict_match, correctness (LLM-as-judge)")
    
    print("\n" + "-" * 60)
    print("Running evaluation...")
    print("-" * 60 + "\n")
    
    # Run evaluation with both evaluators:
    # 1. verdict_match - exact match of pass/fail verdict
    # 2. correctness_evaluator - LLM-as-judge for semantic correctness
    results = evaluate(
        target_fn,
        data=dataset_name,
        evaluators=[verdict_match, correctness_evaluator],
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
    )
    
    print("\n" + "=" * 60)
    print("Evaluation Complete!")
    print("=" * 60)
    print(f"\nView results at: https://smith.langchain.com/")
    
    return results


def main():
    """Main entry point with CLI argument parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run Shift Specialist evaluation on LangSmith dataset"
    )
    parser.add_argument(
        "--dataset",
        default=DATASET_NAME,
        help=f"LangSmith dataset name (default: {DATASET_NAME})",
    )
    parser.add_argument(
        "--prefix",
        default=EXPERIMENT_PREFIX,
        help=f"Experiment prefix (default: {EXPERIMENT_PREFIX})",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max concurrent evaluations (default: 4)",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Use direct LLM mode (faster, skips agent tool-calling)",
    )
    
    args = parser.parse_args()
    
    try:
        results = run_evaluation(
            dataset_name=args.dataset,
            experiment_prefix=args.prefix,
            max_concurrency=args.concurrency,
            use_agent=not args.direct,
        )
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
