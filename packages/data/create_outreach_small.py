#!/usr/bin/env python3
"""Create a small LangSmith dataset for evaluating the Outreach Agent.

This module creates a minimal dataset with three example paths:
  - HITL path: dispute/unknown classification requiring human review
  - Initial outreach path: case needing first email draft
  - Respawn path: existing thread with reply needing follow-up

Usage (Poetry):
    poetry run python packages/data/create_outreach_small.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Project root is two levels up from this file
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Load environment variables
load_dotenv(PROJECT_ROOT / ".env", override=True)


def load_mock_data():
    """Load mock data from JSON files."""
    mock_dir = PROJECT_ROOT / "mock"

    with open(mock_dir / "cases.json") as f:
        cases = json.load(f)

    with open(mock_dir / "email_threads.json") as f:
        email_threads = json.load(f)

    return cases, email_threads


def pick_example_threads(cases: list, email_threads: list) -> dict:
    """Pick email threads for HITL, initial outreach, and respawn examples.
    
    Selection criteria:
    - HITL: Thread with dispute or unknown bucket in last inbound reply
    - Initial outreach: Thread with only outbound messages (no replies yet)
    - Respawn: Thread with address_change or acknowledgment that needs follow-up
    """
    thread_map = {t["thread_id"]: t for t in email_threads}
    case_map = {c["case_id"]: c for c in cases}
    
    hitl_thread = None
    initial_outreach_thread = None
    respawn_thread = None
    
    for thread in email_threads:
        thread_id = thread["thread_id"]
        messages = thread.get("messages", [])
        
        # Get the last inbound message classification
        inbound_msgs = [m for m in messages if m.get("direction") == "inbound"]
        last_inbound_bucket = inbound_msgs[-1].get("classification_bucket") if inbound_msgs else None
        
        # HITL path: dispute or unknown classification
        if last_inbound_bucket in ("dispute", "unknown") and hitl_thread is None:
            hitl_thread = thread
            continue
        
        # Initial outreach: only outbound messages (no inbound replies yet)
        if not inbound_msgs and thread["status"] == "active" and initial_outreach_thread is None:
            initial_outreach_thread = thread
            continue
        
        # Respawn path: thread with address_change needing follow-up
        if last_inbound_bucket == "address_change" and respawn_thread is None:
            respawn_thread = thread
            continue
    
    # Fallback selections if primary criteria not met
    if hitl_thread is None:
        # Pick first thread with any inbound reply
        for thread in email_threads:
            if any(m.get("direction") == "inbound" for m in thread.get("messages", [])):
                hitl_thread = thread
                break
    
    if initial_outreach_thread is None:
        # Pick first active thread
        for thread in email_threads:
            if thread["status"] == "active":
                initial_outreach_thread = thread
                break
    
    if respawn_thread is None:
        # Pick a thread different from others
        for thread in email_threads:
            if thread not in (hitl_thread, initial_outreach_thread):
                respawn_thread = thread
                break
    
    return {
        "hitl": hitl_thread,
        "initial_outreach": initial_outreach_thread,
        "respawn": respawn_thread,
    }


def create_examples(cases: list, email_threads: list) -> list:
    """Create three evaluation examples (HITL, initial outreach, respawn)."""
    chosen = pick_example_threads(cases, email_threads)
    
    hitl_thread = chosen["hitl"]
    initial_thread = chosen["initial_outreach"]
    respawn_thread = chosen["respawn"]
    
    # Get last inbound classification for HITL thread
    hitl_inbound = [m for m in hitl_thread["messages"] if m.get("direction") == "inbound"]
    hitl_bucket = hitl_inbound[-1].get("classification_bucket", "unknown") if hitl_inbound else "unknown"
    
    # Get classification for respawn thread
    respawn_inbound = [m for m in respawn_thread["messages"] if m.get("direction") == "inbound"]
    respawn_bucket = respawn_inbound[-1].get("classification_bucket", "acknowledgment") if respawn_inbound else None
    
    examples = [
        # Path 1: HITL - dispute/unknown classification requires human review
        {
            "inputs": {
                "email_thread_id": hitl_thread["thread_id"],
                "context": f"Inbound reply classified as '{hitl_bucket}'. Requires human review before responding.",
            },
            "outputs": {
                "email_thread_id": hitl_thread["thread_id"],
                "bucket": hitl_bucket,
                "hitl_required": True,
                "sent": False,  # Should NOT auto-send for dispute/unknown
            },
            "metadata": {
                "test_case": "hitl_path",
                "path_type": "human_in_the_loop",
                "case_id": hitl_thread.get("case_id"),
                "vanpool_id": hitl_thread.get("vanpool_id"),
                "reasoning": f"Thread has '{hitl_bucket}' classification which requires HITL review before sending response.",
            },
        },
        # Path 2: Initial outreach - draft first email for a case
        {
            "inputs": {
                "email_thread_id": initial_thread["thread_id"],
                "context": "New case opened. Draft initial outreach email to vanpool members.",
            },
            "outputs": {
                "email_thread_id": initial_thread["thread_id"],
                "bucket": None,  # No inbound reply to classify yet
                "hitl_required": False,
                "sent": True,  # Initial outreach can be auto-sent
            },
            "metadata": {
                "test_case": "initial_outreach_path",
                "path_type": "initial_outreach",
                "case_id": initial_thread.get("case_id"),
                "vanpool_id": initial_thread.get("vanpool_id"),
                "reasoning": "No prior communication. Agent should draft and send initial outreach email.",
            },
        },
        # Path 3: Respawn - existing thread with reply needs follow-up
        {
            "inputs": {
                "email_thread_id": respawn_thread["thread_id"],
                "context": f"Inbound reply received with '{respawn_bucket}' classification. Continue conversation.",
            },
            "outputs": {
                "email_thread_id": respawn_thread["thread_id"],
                "bucket": respawn_bucket,
                "hitl_required": False,  # address_change/acknowledgment can be auto-handled
                "sent": True,  # Should send follow-up response
            },
            "metadata": {
                "test_case": "respawn_path",
                "path_type": "respawn_followup",
                "case_id": respawn_thread.get("case_id"),
                "vanpool_id": respawn_thread.get("vanpool_id"),
                "reasoning": f"Existing thread with '{respawn_bucket}' reply. Agent should draft appropriate follow-up.",
            },
        },
    ]
    
    return examples


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
        print(
            "\n✓ Dataset name already exists. Creating new dataset: "
            f"{dataset_name}"
        )

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=description or "Small evaluation dataset for Outreach Agent",
    )
    print(f"\n✓ Created new dataset: {dataset_name} (id: {dataset.id})")

    print(f"\n  Adding {len(examples)} examples to dataset...")
    inputs = [ex["inputs"] for ex in examples]
    outputs = [ex["outputs"] for ex in examples]
    metadata = [ex["metadata"] for ex in examples]

    client.create_examples(
        inputs=inputs,
        outputs=outputs,
        metadata=metadata,
        dataset_id=dataset.id,
    )

    print(f"\n✓ Successfully added {len(examples)} examples to dataset '{dataset_name}'")
    print(f"\n  View at: https://smith.langchain.com/datasets/{dataset.id}")

    return dataset


def main():
    """Main entry point."""
    print("=" * 60)
    print("Pool Patrol - Outreach Agent Small Dataset Creator")
    print("=" * 60)

    if not os.environ.get("LANGSMITH_API_KEY"):
        print("\n✗ Error: LANGSMITH_API_KEY environment variable not set")
        print("  Set your API key to create datasets on LangSmith.")
        return 1

    print("\n1. Loading mock data...")
    cases, email_threads = load_mock_data()
    print(f"   Loaded {len(cases)} cases, {len(email_threads)} email threads")

    print("\n2. Creating outreach evaluation examples...")
    examples = create_examples(cases, email_threads)
    
    # Summarize paths
    hitl_count = sum(1 for e in examples if e["metadata"]["path_type"] == "human_in_the_loop")
    initial_count = sum(1 for e in examples if e["metadata"]["path_type"] == "initial_outreach")
    respawn_count = sum(1 for e in examples if e["metadata"]["path_type"] == "respawn_followup")
    print(f"   Summary: {hitl_count} HITL, {initial_count} Initial Outreach, {respawn_count} Respawn")
    
    for ex in examples:
        print(f"   - {ex['metadata']['test_case']}: {ex['inputs']['email_thread_id']}")

    print("\n3. Creating LangSmith dataset...")
    dataset_name = "outreach-agent-eval-small"
    description = (
        "Small evaluation dataset for the Outreach Agent. "
        "Contains three paths: HITL (dispute/unknown), Initial Outreach, and Respawn (follow-up)."
    )

    try:
        dataset = create_langsmith_dataset(dataset_name, examples, description)

        print("\n" + "=" * 60)
        print("Dataset Creation Complete!")
        print("=" * 60)
        print(f"\n  Dataset: {dataset_name}")
        print(f"  Examples: {len(examples)}")
        print(f"  HITL cases: {hitl_count}")
        print(f"  Initial outreach cases: {initial_count}")
        print(f"  Respawn cases: {respawn_count}")

        return 0

    except Exception as e:
        print(f"\n✗ Error creating dataset: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
