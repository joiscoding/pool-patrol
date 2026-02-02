#!/usr/bin/env python3
"""Create a medium LangSmith dataset for evaluating the Case Manager Agent.

All 12 vanpools covering different case lifecycle states:

TIMEOUT/CANCELLATION:
  1. VP-103: pre_cancel status, timeout elapsed - must cancel membership

PENDING REPLY (continue outreach):
  2. VP-108: pending_reply, shift mismatch
  3. VP-109: pending_reply, multiple mixed shifts

CLEAN/VERIFIED (no case or resolved):
  5. VP-104: No case, all swing shift - pass verification
  6. VP-105: No case, all day shift - pass verification
  7. VP-107: Resolved (false_positive) - pass verification
  8. VP-110: No case, all night shift - pass verification
  9. VP-112: Resolved (verified_compliant) - pass verification

EDGE CASES:
 10. VP-999: Non-existent vanpool - error (not found)
 11. VP-EMPTY: Empty vanpool (no riders) - error (no riders)
 12. "": Invalid input (empty string) - error (invalid)

Usage (Poetry):
    poetry run python packages/data/create_case_manager_med.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)


# All 12 vanpools covering the full case lifecycle
# expected_tools: Tools that MUST be called (superset match - extras OK)
EXAMPLES = [
    # =========================================================================
    # TIMEOUT/CANCELLATION SCENARIOS
    # =========================================================================
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
            # Timeout scenario: must attempt cancellation
            "expected_tools": ["cancel_membership"],
        },
    },
    # =========================================================================
    # PENDING REPLY SCENARIOS (continue outreach)
    # =========================================================================
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
            # Existing case pending reply: must continue outreach
            "expected_tools": ["run_outreach"],
        },
    },
    {
        "inputs": {
            "vanpool_id": "VP-109",
        },
        "outputs": {
            "vanpool_id": "VP-109",
            "case_id": "CASE-008",
            "outcome": "pending",
            "reasoning": "Existing case with multiple shift mismatches (day/swing/night). Awaiting employee response.",
            "hitl_required": False,
            # Existing case pending reply: must continue outreach
            "expected_tools": ["run_outreach"],
        },
    },
    # =========================================================================
    # CLEAN/VERIFIED SCENARIOS (no case or resolved)
    # =========================================================================
    {
        "inputs": {
            "vanpool_id": "VP-104",
        },
        "outputs": {
            "vanpool_id": "VP-104",
            "case_id": None,
            "outcome": "verified",
            "reasoning": "All verification checks passed. All employees on swing shift.",
            "hitl_required": False,
            # No case: must run verification specialists
            "expected_tools": ["run_shift_specialist", "run_location_specialist"],
        },
    },
    {
        "inputs": {
            "vanpool_id": "VP-105",
        },
        "outputs": {
            "vanpool_id": "VP-105",
            "case_id": None,
            "outcome": "verified",
            "reasoning": "All verification checks passed. All employees on day shift.",
            "hitl_required": False,
            # No case: must run verification specialists
            "expected_tools": ["run_shift_specialist", "run_location_specialist"],
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
            "reasoning": "Previous case resolved as false positive. Verification checks passed.",
            "hitl_required": False,
            # Resolved case: must run verification specialists
            "expected_tools": ["run_shift_specialist", "run_location_specialist"],
        },
    },
    {
        "inputs": {
            "vanpool_id": "VP-110",
        },
        "outputs": {
            "vanpool_id": "VP-110",
            "case_id": None,
            "outcome": "verified",
            "reasoning": "All verification checks passed. All employees on night shift.",
            "hitl_required": False,
            # No case: must run verification specialists
            "expected_tools": ["run_shift_specialist", "run_location_specialist"],
        },
    },
    {
        "inputs": {
            "vanpool_id": "VP-112",
        },
        "outputs": {
            "vanpool_id": "VP-112",
            "case_id": None,
            "outcome": "verified",
            "reasoning": "Previous case resolved as verified compliant. All employees on day shift.",
            "hitl_required": False,
            # Resolved case: must run verification specialists
            "expected_tools": ["run_shift_specialist", "run_location_specialist"],
        },
    },
    # =========================================================================
    # EDGE CASES (error handling)
    # =========================================================================
    {
        "inputs": {
            "vanpool_id": "VP-999",
        },
        "outputs": {
            "vanpool_id": "VP-999",
            "case_id": None,
            "outcome": "error",
            "reasoning": "Vanpool not found in database.",
            "hitl_required": False,
            # Non-existent vanpool: returns error, no tools needed
            "expected_tools": [],
        },
    },
    {
        "inputs": {
            "vanpool_id": "VP-EMPTY",
        },
        "outputs": {
            "vanpool_id": "VP-EMPTY",
            "case_id": None,
            "outcome": "error",
            "reasoning": "Vanpool has no riders to verify.",
            "hitl_required": False,
            # Empty vanpool: returns error, no tools needed
            "expected_tools": [],
        },
    },
    {
        "inputs": {
            "vanpool_id": "",
        },
        "outputs": {
            "vanpool_id": "",
            "case_id": None,
            "outcome": "error",
            "reasoning": "Invalid input: vanpool_id is empty.",
            "hitl_required": False,
            # Invalid input: returns error, no tools needed
            "expected_tools": [],
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
        description=description or "Medium evaluation dataset for Case Manager Agent",
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
    print("Pool Patrol - Case Manager Agent Medium Dataset Creator")
    print("=" * 60)

    if not os.environ.get("LANGSMITH_API_KEY"):
        print("\n✗ Error: LANGSMITH_API_KEY not set")
        return 1

    print(f"\nExamples ({len(EXAMPLES)} vanpools):")
    for ex in EXAMPLES:
        vp_id = ex["inputs"]["vanpool_id"]
        outcome = ex["outputs"]["outcome"]
        reasoning = ex["outputs"]["reasoning"]
        print(f"  - {vp_id}: {outcome}")
        print(f"    {reasoning}")

    dataset_name = "case-manager-eval-med-with-traj"
    description = "Medium evaluation dataset for Case Manager Agent (all 12 vanpools)."

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
