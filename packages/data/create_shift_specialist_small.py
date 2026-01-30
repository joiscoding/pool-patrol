#!/usr/bin/env python3
"""Create a small LangSmith dataset for evaluating the Shift Specialist agent.

This module creates a minimal dataset with two examples:
  - one happy path (all employees same shift)
  - one not-happy path (mixed shifts)

Usage (Poetry):
    poetry run python packages/data/create_shift_specialist_small.py
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

    with open(mock_dir / "employees.json") as f:
        employees = json.load(f)

    with open(mock_dir / "shifts.json") as f:
        shifts = json.load(f)

    return employees, shifts


def pick_small_example_ids(employees: list, shifts: list) -> dict:
    """Pick employee IDs for one happy and one not-happy example."""
    shift_id_by_name = {s["name"]: s["id"] for s in shifts}

    day_shift_id = shift_id_by_name.get("Day Shift")
    night_shift_id = shift_id_by_name.get("Night Shift")

    def ids_for_shift(shift_id: str) -> list:
        return [e["employee_id"] for e in employees if e.get("shift_id") == shift_id]

    if day_shift_id and night_shift_id:
        day_ids = ids_for_shift(day_shift_id)
        night_ids = ids_for_shift(night_shift_id)
        if len(day_ids) >= 2 and len(night_ids) >= 1:
            return {
                "happy": [day_ids[0], day_ids[1]],
                "not_happy": [day_ids[0], night_ids[0]],
            }

    # Fallback: group by shift_id and choose two different shifts
    by_shift = {}
    for emp in employees:
        shift_id = emp.get("shift_id")
        if not shift_id:
            continue
        by_shift.setdefault(shift_id, []).append(emp["employee_id"])

    shift_ids = [sid for sid, ids in by_shift.items() if len(ids) >= 1]
    if not shift_ids:
        raise RuntimeError("No employees with shift assignments found.")

    happy_shift_id = next((sid for sid, ids in by_shift.items() if len(ids) >= 2), None)
    if not happy_shift_id:
        raise RuntimeError("Not enough employees on the same shift for happy path.")

    other_shift_id = next((sid for sid in shift_ids if sid != happy_shift_id), None)
    if not other_shift_id:
        raise RuntimeError("Not enough distinct shifts for not-happy path.")

    return {
        "happy": [by_shift[happy_shift_id][0], by_shift[happy_shift_id][1]],
        "not_happy": [by_shift[happy_shift_id][0], by_shift[other_shift_id][0]],
    }


def create_examples(employees: list, shifts: list) -> list:
    """Create two evaluation examples (happy + not-happy)."""
    employee_map = {e["employee_id"]: e for e in employees}
    shift_map = {s["id"]: s["name"] for s in shifts}

    chosen = pick_small_example_ids(employees, shifts)
    happy_ids = chosen["happy"]
    not_happy_ids = chosen["not_happy"]

    def shift_name(employee_id: str) -> str:
        shift_id = employee_map[employee_id].get("shift_id")
        return shift_map.get(shift_id, "Unknown")

    happy_shift = shift_name(happy_ids[0])
    not_happy_shift_a = shift_name(not_happy_ids[0])
    not_happy_shift_b = shift_name(not_happy_ids[1])

    return [
        {
            "inputs": {"employee_ids": happy_ids},
            "outputs": {
                "verdict": "pass",
                "reasoning": f"All 2 employees work the same shift: {happy_shift}.",
            },
            "metadata": {
                "test_case": "small_happy_path",
                "reasoning": f"All 2 employees work the same shift: {happy_shift}.",
            },
        },
        {
            "inputs": {"employee_ids": not_happy_ids},
            "outputs": {
                "verdict": "fail",
                "reasoning": (
                    f"Shift mismatch detected. 1 employee on {not_happy_shift_a}, "
                    f"1 employee on {not_happy_shift_b}."
                ),
            },
            "metadata": {
                "test_case": "small_not_happy_path",
                "reasoning": (
                    f"Shift mismatch detected. 1 employee on {not_happy_shift_a}, "
                    f"1 employee on {not_happy_shift_b}."
                ),
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
        print(
            "\n✓ Dataset name already exists. Creating new dataset: "
            f"{dataset_name}"
        )

    dataset = client.create_dataset(
        dataset_name=dataset_name,
        description=description or "Small evaluation dataset for Shift Specialist agent",
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
    print("Pool Patrol - LangSmith Small Dataset Creator")
    print("=" * 60)

    if not os.environ.get("LANGSMITH_API_KEY"):
        print("\n✗ Error: LANGSMITH_API_KEY environment variable not set")
        print("  Set your API key to create datasets on LangSmith.")
        return 1

    print("\n1. Loading mock data...")
    employees, shifts = load_mock_data()
    print(f"   Loaded {len(employees)} employees, {len(shifts)} shifts")

    print("\n2. Creating small evaluation examples...")
    examples = create_examples(employees, shifts)
    pass_count = sum(1 for e in examples if e["outputs"]["verdict"] == "pass")
    fail_count = sum(1 for e in examples if e["outputs"]["verdict"] == "fail")
    print(f"   Summary: {pass_count} PASS, {fail_count} FAIL")

    print("\n3. Creating LangSmith dataset...")
    dataset_name = "shift-specialist-eval-small"
    description = (
        "Small evaluation dataset for the Shift Specialist agent. "
        "Contains one happy path and one not-happy path example."
    )

    try:
        dataset = create_langsmith_dataset(dataset_name, examples, description)

        print("\n" + "=" * 60)
        print("Dataset Creation Complete!")
        print("=" * 60)
        print(f"\n  Dataset: {dataset_name}")
        print(f"  Examples: {len(examples)}")
        print(f"  Pass cases: {pass_count}")
        print(f"  Fail cases: {fail_count}")

        return 0

    except Exception as e:
        print(f"\n✗ Error creating dataset: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
