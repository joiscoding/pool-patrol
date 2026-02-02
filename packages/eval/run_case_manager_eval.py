#!/usr/bin/env python3
"""Run LangSmith evaluation for the Case Manager Agent.

Evaluators:
===========

1. HEURISTIC EVALUATORS (exact match):
   - outcome_match: Does outcome match expected? (verified, pending, resolved)
   - hitl_match: Does hitl_required match expected?

2. TRAJECTORY EVALUATORS (tool selection):
   - trajectory_match: Did the agent call the required tools? (superset match)

3. LLM-AS-JUDGE EVALUATORS:
   - correctness: Is the agent's decision semantically correct?

Usage:
    poetry run python -m eval.run_case_manager_eval

Requirements:
    - LANGSMITH_API_KEY environment variable
    - OPENAI_API_KEY environment variable
    - Dataset created via: poetry run python packages/data/create_case_manager_small.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages"))

from dotenv import load_dotenv

# Load env FIRST, then enable tracing BEFORE importing agents
load_dotenv(PROJECT_ROOT / ".env", override=True)
os.environ["LANGSMITH_TRACING"] = "true"
os.environ.setdefault("LANGSMITH_PROJECT", "pool-patrol-eval")

from agentevals.trajectory.match import create_trajectory_match_evaluator
from langchain_core.messages import AIMessage
from langsmith import Client
from langsmith.evaluation import evaluate
from openevals.llm import create_llm_as_judge
from openevals.prompts import CORRECTNESS_PROMPT

# Import agent AFTER tracing is configured
from agents.case_manager import investigate_vanpool_sync_with_trajectory
from agents.structures import CaseManagerRequest


# =============================================================================
# Configuration
# =============================================================================

DATASET_NAME = "case-manager-eval-small-with-traj"
EXPERIMENT_PREFIX = "case-manager"


# =============================================================================
# Target Function
# =============================================================================


def target_function(inputs: dict) -> dict:
    """Run the Case Manager Agent on a vanpool investigation.
    
    Args:
        inputs: Dict with "vanpool_id" key
        
    Returns:
        Dict with vanpool_id, case_id, outcome, reasoning, hitl_required, and messages
    """
    vanpool_id = inputs["vanpool_id"]
    
    # Run the agent with trajectory capture
    request = CaseManagerRequest(vanpool_id=vanpool_id)
    result_with_trajectory = investigate_vanpool_sync_with_trajectory(request)
    result = result_with_trajectory.result
    
    return {
        "vanpool_id": result.vanpool_id,
        "case_id": result.case_id,
        "outcome": result.outcome,
        "reasoning": result.reasoning,
        "hitl_required": result.hitl_required,
        # Include messages for trajectory evaluation
        "messages": result_with_trajectory.messages,
    }


# =============================================================================
# Heuristic Evaluators
# =============================================================================


def outcome_match(outputs: dict, reference_outputs: dict) -> dict:
    """Check if outcome matches expected.
    
    Verifies the agent correctly identified the case state:
    - verified: No issues, all checks passed
    - pending: Investigation ongoing, awaiting response
    - resolved: Case closed successfully
    """
    predicted = outputs.get("outcome")
    expected = reference_outputs.get("outcome")
    
    return {
        "key": "outcome_match",
        "score": predicted == expected,
    }


def hitl_match(outputs: dict, reference_outputs: dict) -> dict:
    """Check if hitl_required matches expected.
    
    Critical for ensuring membership cancellations and escalations
    trigger human review.
    """
    predicted = outputs.get("hitl_required")
    expected = reference_outputs.get("hitl_required")
    
    return {
        "key": "hitl_match",
        "score": predicted == expected,
    }


# =============================================================================
# Trajectory Evaluators (Tool Selection)
# =============================================================================

# Base trajectory evaluator with superset mode (agent must call at least the expected tools)
_trajectory_match_evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="superset",
    tool_args_match_mode="ignore",  # Only match tool names, not arguments
)


def trajectory_match(outputs: dict, reference_outputs: dict) -> dict:
    """Check if the agent called all required tools (superset match).
    
    Converts expected_tools list to a reference trajectory and uses
    agentevals trajectory match with superset mode.
    
    - superset: Agent must call AT LEAST the expected tools (extras OK)
    - tool_args_match_mode="ignore": Only tool names matter, not arguments
    """
    expected_tools = reference_outputs.get("expected_tools", [])
    messages = outputs.get("messages", [])
    
    # Handle empty cases
    if not expected_tools:
        return {"key": "trajectory_match", "score": True}
    if not messages:
        return {"key": "trajectory_match", "score": False}
    
    # Build reference trajectory from expected_tools
    # Each tool becomes a tool_call in an AIMessage
    reference_trajectory = [
        AIMessage(
            content="",
            tool_calls=[
                {"id": f"expected_{i}", "name": tool_name, "args": {}}
                for i, tool_name in enumerate(expected_tools)
            ],
        )
    ]
    
    # Run the trajectory match evaluator
    result = _trajectory_match_evaluator(
        outputs=messages,
        reference_outputs=reference_trajectory,
    )
    
    return {
        "key": "trajectory_match",
        "score": result.get("score", False),
        "comment": result.get("comment"),
    }


# =============================================================================
# LLM-as-Judge Evaluators
# =============================================================================

# Correctness evaluator using openevals CORRECTNESS_PROMPT
correctness_evaluator = create_llm_as_judge(
    prompt=CORRECTNESS_PROMPT,
    feedback_key="correctness",
    model="openai:gpt-4.1",
)


# =============================================================================
# Main Evaluation Runner
# =============================================================================


def run_evaluation(
    dataset_name: str = DATASET_NAME,
    experiment_prefix: str = EXPERIMENT_PREFIX,
    max_concurrency: int = 4,
):
    """Run the evaluation experiment on LangSmith."""
    print("=" * 60)
    print("Pool Patrol - Case Manager Agent Evaluation")
    print("=" * 60)
    
    if not os.environ.get("LANGSMITH_API_KEY"):
        raise ValueError("LANGSMITH_API_KEY not set")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set")
    
    client = Client()
    datasets = list(client.list_datasets(dataset_name=dataset_name))
    if not datasets:
        raise ValueError(
            f"Dataset '{dataset_name}' not found. "
            "Run create_case_manager_small.py first."
        )
    
    dataset = datasets[0]
    example_count = len(list(client.list_examples(dataset_id=dataset.id)))
    
    print(f"\nDataset: {dataset_name}")
    print(f"Examples: {example_count}")
    print(f"Model: {os.environ.get('OPENAI_MODEL', 'gpt-4.1')}")
    print(f"Evaluators: outcome_match, hitl_match, trajectory_match, correctness (LLM-as-judge)")
    
    print("\n" + "-" * 60)
    print("Running evaluation...")
    print("-" * 60 + "\n")
    
    results = evaluate(
        target_function,
        data=dataset_name,
        evaluators=[outcome_match, hitl_match, trajectory_match, correctness_evaluator],
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
    )
    
    print("\n" + "=" * 60)
    print("Evaluation Complete!")
    print("=" * 60)
    print(f"\nView results at: https://smith.langchain.com/")
    
    return results


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Case Manager Agent evaluation")
    parser.add_argument("--dataset", default=DATASET_NAME)
    parser.add_argument("--prefix", default=EXPERIMENT_PREFIX)
    parser.add_argument("--concurrency", type=int, default=4)
    
    args = parser.parse_args()
    
    try:
        run_evaluation(
            dataset_name=args.dataset,
            experiment_prefix=args.prefix,
            max_concurrency=args.concurrency,
        )
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
