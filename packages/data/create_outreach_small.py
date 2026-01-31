#!/usr/bin/env python3
"""Create a small LangSmith dataset for evaluating the Outreach Agent.

Three happy path examples using THREAD-001, THREAD-003, and THREAD-008.

Usage (Poetry):
    poetry run python packages/data/create_outreach_small.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True)


# Three happy path examples (matching tests/test_outreach_agent.py)
# Paste the AI-drafted emails from test runs into the metadata.draft_email field
EXAMPLES = [
    {
        "inputs": {
            "email_thread_id": "THREAD-001",
            "context": "Process this email thread.",
        },
        "outputs": {
            "email_thread_id": "THREAD-001",
            "bucket": "update",
            "hitl_required": False,
            "sent": True,
        },
        "metadata": {
            "description": "Bob Johnson moved to LA, needs address update in Employee Portal",
            "draft_email": """Hi Bob,

Thank you for letting us know about your address change. We appreciate you keeping us informed about your living situation.

Before we can confirm your continued vanpool eligibility, please update your home address in the Employee Portal. Once you've made the update there, reply to this email and we'll verify your eligibility for VP-101.

If you have any questions about the process, feel free to reach out.

Best regards,
Pool Patrol Team""",
        },
    },
    {
        "inputs": {
            "email_thread_id": "THREAD-003",
            "context": "Process this email thread.",
        },
        "outputs": {
            "email_thread_id": "THREAD-003",
            "bucket": "escalation",
            "hitl_required": True,
            "sent": False,
        },
        "metadata": {
            "description": "Xavier disputes the review, feels it's harassment",
            "draft_email": """Hi Xavier,

Thank you for your response. I understand your concern, and I want to assure you that this is a routine review conducted for all vanpool participants—it is not targeted at any individual.

Our records show your address is in San Diego (92101), which is approximately 480 miles from the Fremont Factory. We want to ensure this commute arrangement still works for you and meets program guidelines.

Could you please confirm your current home address and help us understand your commute arrangement?

Best regards,
Pool Patrol Team""",
        },
    },
    {
        "inputs": {
            "email_thread_id": "THREAD-008",
            "context": "Process this email thread.",
        },
        "outputs": {
            "email_thread_id": "THREAD-008",
            "bucket": "acknowledgment",
            "hitl_required": False,
            "sent": True,
        },
        "metadata": {
            "description": "Charlie Cooper confirms 'All good here' - no changes needed",
            "draft_email": """Hi Charlie,

Thank you for confirming your address. Your vanpool eligibility for VP-112 has been verified.

No further action is needed on your part. If anything changes in the future, please let us know.

Best regards,
Pool Patrol Team""",
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
        description=description or "Small evaluation dataset for Outreach Agent",
    )
    print(f"\n✓ Created dataset: {dataset_name} (id: {dataset.id})")

    client.create_examples(
        inputs=[ex["inputs"] for ex in examples],
        outputs=[ex["outputs"] for ex in examples],
        metadata=[ex.get("metadata") for ex in examples],
        dataset_id=dataset.id,
    )

    print(f"✓ Added {len(examples)} examples")
    print(f"\n  View at: https://smith.langchain.com/datasets/{dataset.id}")

    return dataset


def main():
    """Main entry point."""
    print("=" * 60)
    print("Pool Patrol - Outreach Agent Small Dataset Creator")
    print("=" * 60)

    if not os.environ.get("LANGSMITH_API_KEY"):
        print("\n✗ Error: LANGSMITH_API_KEY not set")
        return 1

    print("\nExamples:")
    for ex in EXAMPLES:
        tid = ex["inputs"]["email_thread_id"]
        bucket = ex["outputs"]["bucket"]
        print(f"  - {tid}: {bucket}")

    dataset_name = "outreach-agent-eval-small"
    description = "Small evaluation dataset for Outreach Agent (3 happy paths)."

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
