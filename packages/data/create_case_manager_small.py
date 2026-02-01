#!/usr/bin/env python3
"""Create a small LangSmith dataset for evaluating the Case Manager Agent.

Four scenarios covering different case lifecycle states:
1. VP-103: Timeout/cancellation flow (case >1 week old, pre_cancel status)
2. VP-108: Existing case handling (pending_reply status)
3. VP-104: Verification pass (no case, all employees aligned)
4. VP-107: Resolved case (no action needed)

Usage (Poetry):
    poetry run python packages/data/create_case_manager_small.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)


# Four scenarios covering the full case lifecycle
EXAMPLES = [
    {
        "inputs": {
            "vanpool_id": "VP-103",
        },
        "outputs": {
            "vanpool_id": "VP-103",
            "case_id": "CASE-004",
            "outcome": "pending",
            "reasoning": "Case timeout elapsed (>1 week). Attempted membership cancellation requiring HITL approval.",
            "hitl_required": True,
        },
    },
    {
        "inputs": {
            "vanpool_id": "VP-108",
        },
        "outputs": {
            "vanpool_id": "VP-108",
            "case_id": "CASE-007",
            "outcome": "pending",
            "reasoning": "Existing case with shift mismatch. Awaiting employee response.",
            "hitl_required": False,
        },
    },
    {
        "inputs": {
            "vanpool_id": "VP-104",
        },
        "outputs": {
            "vanpool_id": "VP-104",
            "case_id": None,
            "outcome": "verified",
            "reasoning": "All verification checks passed. No issues found.",
            "hitl_required": False,
        },
    },
    {
        "inputs": {
            "vanpool_id": "VP-107",
        },
        "outputs": {
            "vanpool_id": "VP-107",
            "case_id": None,
            "outcome": "verified",
            "reasoning": "No open case. Verification checks passed.",
            "hitl_required": False,
        },
    },
]


def create_langsmith_dataset(dataset_name: str, examples: list, description: str = None):
    """Create a LangSmith dataset with the given examples."""
    from langsmith import Client

    client = Client()

    existing_datasets = list(client.list_datasets(dataset_name=dataset_name))
    if existing_datasets:
        unique_suffix = os.environ.get("LANGSMITH_DATASET_SUFFIX")
        if not unique_suffix:
            unique_suffix = str(int(__import__("time").time()))
        dataset_name = f"{dataset_name}-{unique_suffix}"
        print(f"\n✓ Dataset exists. Creating: {dataset_name}")

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=description or "Small evaluation dataset for Case Manager Agent",
    )
    print(f"\n✓ Created dataset: {dataset_name} (id: {dataset.id})")

    client.create_examples(
        inputs=[ex["inputs"] for ex in examples],
        outputs=[ex["outputs"] for ex in examples],
        dataset_id=dataset.id,
    )

    print(f"✓ Added {len(examples)} examples")
    print(f"\n  View at: https://smith.langchain.com/datasets/{dataset.id}")

    return dataset


def main():
    """Main entry point."""
    print("=" * 60)
    print("Pool Patrol - Case Manager Agent Small Dataset Creator")
    print("=" * 60)

    if not os.environ.get("LANGSMITH_API_KEY"):
        print("\n✗ Error: LANGSMITH_API_KEY not set")
        return 1

    print("\nExamples:")
    for ex in EXAMPLES:
        vp_id = ex["inputs"]["vanpool_id"]
        outcome = ex["outputs"]["outcome"]
        reasoning = ex["outputs"]["reasoning"]
        print(f"  - {vp_id}: {outcome}")
        print(f"    {reasoning}")

    dataset_name = "case-manager-eval-small"
    description = "Small evaluation dataset for Case Manager Agent (4 lifecycle scenarios)."

    try:
        create_langsmith_dataset(dataset_name, EXAMPLES, description)
        print("\n✓ Done!")
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
