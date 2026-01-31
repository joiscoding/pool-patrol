#!/usr/bin/env python3
"""Run LangSmith evaluation for the Outreach Agent.

Evaluators (TODO):
===================

1. HEURISTIC EVALUATORS (exact match):
   - hitl_match: Does hitl_required match expected? (escalation → True)
   - bucket_match: Does bucket classification match expected?

2. LLM-AS-JUDGE EVALUATORS (for draft_email in metadata):
   - correctness: Is the email factually correct given the thread context?
   - hallucination: Does the email contain made-up information?
   - tone: Is the tone professional and appropriate?

Usage:
    poetry run python -m eval.run_outreach_eval

Requirements:
    - LANGSMITH_API_KEY environment variable
    - OPENAI_API_KEY environment variable
    - Dataset created via: poetry run python packages/data/create_outreach_small.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages"))

from dotenv import load_dotenv
from langsmith import Client
from langsmith.evaluation import evaluate

load_dotenv(PROJECT_ROOT / ".env", override=True)

from agents.outreach import handle_outreach_sync
from agents.structures import OutreachRequest


# =============================================================================
# Configuration
# =============================================================================

DATASET_NAME = "outreach-agent-eval-small"
EXPERIMENT_PREFIX = "outreach-agent"


# =============================================================================
# Target Function
# =============================================================================


def target_function(inputs: dict) -> dict:
    """Run the Outreach Agent on an email thread.
    
    Args:
        inputs: Dict with "email_thread_id" and optional "context"
        
    Returns:
        Dict with bucket, hitl_required, sent fields
    """
    request = OutreachRequest(
        email_thread_id=inputs["email_thread_id"],
        context=inputs.get("context"),
    )
    
    result = handle_outreach_sync(request)
    
    return {
        "email_thread_id": result.email_thread_id,
        "bucket": result.bucket,
        "hitl_required": result.hitl_required,
        "sent": result.sent,
    }


# =============================================================================
# Heuristic Evaluators
# =============================================================================


def hitl_match(outputs: dict, reference_outputs: dict) -> dict:
    """Check if hitl_required matches expected.
    
    Critical for ensuring escalations trigger human review.
    """
    predicted = outputs.get("hitl_required")
    expected = reference_outputs.get("hitl_required")
    
    return {
        "key": "hitl_match",
        "score": predicted == expected,
    }


def bucket_match(outputs: dict, reference_outputs: dict) -> dict:
    """Check if bucket classification matches expected.
    
    Verifies intent classification: acknowledgment, question, update, escalation.
    """
    predicted = outputs.get("bucket")
    expected = reference_outputs.get("bucket")
    
    return {
        "key": "bucket_match",
        "score": predicted == expected,
    }


# =============================================================================
# LLM-as-Judge Evaluators (TODO)
# =============================================================================

# TODO: correctness_evaluator - Is the drafted email factually correct?
# TODO: hallucination_evaluator - Does the email contain made-up info?
# TODO: tone_evaluator - Is the tone professional and appropriate?


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
    print("Pool Patrol - Outreach Agent Evaluation")
    print("=" * 60)
    
    if not os.environ.get("LANGSMITH_API_KEY"):
        raise ValueError("LANGSMITH_API_KEY not set")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set")
    
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", "pool-patrol-eval")
    
    client = Client()
    datasets = list(client.list_datasets(dataset_name=dataset_name))
    if not datasets:
        raise ValueError(f"Dataset '{dataset_name}' not found. Run create_outreach_small.py first.")
    
    dataset = datasets[0]
    example_count = len(list(client.list_examples(dataset_id=dataset.id)))
    
    print(f"\nDataset: {dataset_name}")
    print(f"Examples: {example_count}")
    print(f"Evaluators: hitl_match, bucket_match")
    
    print("\n" + "-" * 60)
    print("Running evaluation...")
    print("-" * 60 + "\n")
    
    results = evaluate(
        target_function,
        data=dataset_name,
        evaluators=[hitl_match, bucket_match],
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
    
    parser = argparse.ArgumentParser(description="Run Outreach Agent evaluation")
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
