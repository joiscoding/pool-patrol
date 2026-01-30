#!/usr/bin/env python3
"""Create a LangSmith dataset for evaluating the Shift Specialist agent.

This module creates a dataset from the mock data to evaluate whether the
Shift Specialist correctly identifies shift mismatches in vanpools.

Usage (Poetry):
    poetry run python packages/data/create_langsmith_dataset.py

Requirements:
    - Python environment set up with Poetry
    - LANGSMITH_API_KEY environment variable set

Reference: https://docs.langchain.com/langsmith/manage-datasets-programmatically
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
    
    with open(mock_dir / "vanpools.json") as f:
        vanpools = json.load(f)
    
    with open(mock_dir / "shifts.json") as f:
        shifts = json.load(f)
    
    return employees, vanpools, shifts


def analyze_vanpool_shifts(vanpool: dict, employees: list, shifts: list) -> dict:
    """Analyze a vanpool to determine expected verdict and evidence.
    
    Args:
        vanpool: Vanpool data with riders
        employees: List of all employees
        shifts: List of all shift definitions
        
    Returns:
        Dict with expected verdict and metadata
    """
    # Build lookup maps
    employee_map = {e["employee_id"]: e for e in employees}
    shift_map = {s["id"]: s["name"] for s in shifts}
    
    # Get shift for each rider
    rider_shifts = []
    for rider in vanpool["riders"]:
        emp_id = rider["employee_id"]
        if emp_id in employee_map:
            shift_id = employee_map[emp_id].get("shift_id")
            shift_name = shift_map.get(shift_id, "Unknown")
            rider_shifts.append({
                "employee_id": emp_id,
                "shift_id": shift_id,
                "shift_name": shift_name,
            })
    
    # Count unique shifts
    unique_shifts = set(r["shift_name"] for r in rider_shifts)
    shift_counts = {}
    for r in rider_shifts:
        shift_counts[r["shift_name"]] = shift_counts.get(r["shift_name"], 0) + 1
    
    # Determine expected verdict
    # If all riders have the same shift, it should PASS
    # If there are mixed shifts, it should FAIL
    if len(unique_shifts) == 1:
        expected_verdict = "pass"
        reasoning = f"All {len(rider_shifts)} riders work the same shift: {list(unique_shifts)[0]}"
    else:
        expected_verdict = "fail"
        majority_shift = max(shift_counts.keys(), key=lambda k: shift_counts[k])
        mismatched = [r for r in rider_shifts if r["shift_name"] != majority_shift]
        reasoning = (
            f"Shift mismatch detected. Majority shift is {majority_shift} ({shift_counts[majority_shift]} riders), "
            f"but {len(mismatched)} rider(s) have different shifts: "
            + ", ".join(f"{r['employee_id']} ({r['shift_name']})" for r in mismatched)
        )
    
    return {
        "vanpool_id": vanpool["vanpool_id"],
        "expected_verdict": expected_verdict,
        "rider_count": len(rider_shifts),
        "unique_shifts": list(unique_shifts),
        "shift_breakdown": shift_counts,
        "reasoning": reasoning,
        "rider_details": rider_shifts,
    }


def create_custom_edge_cases() -> list:
    """Create custom edge case examples for testing.
    
    These cover scenarios not present in the vanpool mock data.
    """
    # Employee IDs by shift type (from mock data):
    # Day Shift: EMP-1001, EMP-1002, EMP-1003, EMP-1004, EMP-1005, etc.
    # Night Shift: EMP-1006, EMP-1007, EMP-1008, EMP-1009, etc.
    # Swing Shift: EMP-1016, EMP-1017, EMP-1018, EMP-1019, etc.
    
    edge_cases = [
        # 0 employees - should fail
        {
            "inputs": {"employee_ids": []},
            "outputs": {
                "verdict": "fail",
                "reasoning": "No employees provided. Cannot verify shift compatibility with an empty list.",
            },
            "metadata": {"test_case": "empty_list"},
        },
        # 1 day shift employee - should pass
        {
            "inputs": {"employee_ids": ["EMP-1001"]},
            "outputs": {
                "verdict": "pass",
                "reasoning": "Single employee on Day Shift. No shift conflicts possible.",
            },
            "metadata": {"test_case": "single_day_shift"},
        },
        # 1 night shift employee - should pass
        {
            "inputs": {"employee_ids": ["EMP-1006"]},
            "outputs": {
                "verdict": "pass",
                "reasoning": "Single employee on Night Shift. No shift conflicts possible.",
            },
            "metadata": {"test_case": "single_night_shift"},
        },
        # 1 swing shift employee - should pass
        {
            "inputs": {"employee_ids": ["EMP-1016"]},
            "outputs": {
                "verdict": "pass",
                "reasoning": "Single employee on Swing Shift. No shift conflicts possible.",
            },
            "metadata": {"test_case": "single_swing_shift"},
        },
        # 2 day shift employees - should pass
        {
            "inputs": {"employee_ids": ["EMP-1001", "EMP-1002"]},
            "outputs": {
                "verdict": "pass",
                "reasoning": "All 2 employees work the same shift: Day Shift.",
            },
            "metadata": {"test_case": "two_day_shift"},
        },
        # 2 night shift employees - should pass
        {
            "inputs": {"employee_ids": ["EMP-1006", "EMP-1007"]},
            "outputs": {
                "verdict": "pass",
                "reasoning": "All 2 employees work the same shift: Night Shift.",
            },
            "metadata": {"test_case": "two_night_shift"},
        },
        # 2 swing shift employees - should pass
        {
            "inputs": {"employee_ids": ["EMP-1016", "EMP-1017"]},
            "outputs": {
                "verdict": "pass",
                "reasoning": "All 2 employees work the same shift: Swing Shift.",
            },
            "metadata": {"test_case": "two_swing_shift"},
        },
        # 2 employees: 1 day + 1 night - should fail
        {
            "inputs": {"employee_ids": ["EMP-1001", "EMP-1006"]},
            "outputs": {
                "verdict": "fail",
                "reasoning": "Shift mismatch detected. 1 employee on Day Shift, 1 employee on Night Shift.",
            },
            "metadata": {"test_case": "two_day_night_mix"},
        },
        # 2 employees: 1 night + 1 swing - should fail
        {
            "inputs": {"employee_ids": ["EMP-1006", "EMP-1016"]},
            "outputs": {
                "verdict": "fail",
                "reasoning": "Shift mismatch detected. 1 employee on Night Shift, 1 employee on Swing Shift.",
            },
            "metadata": {"test_case": "two_night_swing_mix"},
        },
        # 8 employees: 7 day + 1 night - should fail
        {
            "inputs": {"employee_ids": ["EMP-1001", "EMP-1002", "EMP-1003", "EMP-1004", "EMP-1005", "EMP-1010", "EMP-1011", "EMP-1006"]},
            "outputs": {
                "verdict": "fail",
                "reasoning": "Shift mismatch detected. Majority shift is Day Shift (7 employees), but 1 employee has a different shift: EMP-1006 (Night Shift).",
            },
            "metadata": {"test_case": "seven_day_one_night"},
        },
        # 8 employees: 7 night + 1 day - should fail
        {
            "inputs": {"employee_ids": ["EMP-1006", "EMP-1007", "EMP-1008", "EMP-1009", "EMP-1014", "EMP-1025", "EMP-1026", "EMP-1001"]},
            "outputs": {
                "verdict": "fail",
                "reasoning": "Shift mismatch detected. Majority shift is Night Shift (7 employees), but 1 employee has a different shift: EMP-1001 (Day Shift).",
            },
            "metadata": {"test_case": "seven_night_one_day"},
        },
        # 8 employees: 7 swing + 1 day - should fail
        {
            "inputs": {"employee_ids": ["EMP-1016", "EMP-1017", "EMP-1018", "EMP-1019", "EMP-1034", "EMP-1035", "EMP-1036", "EMP-1001"]},
            "outputs": {
                "verdict": "fail",
                "reasoning": "Shift mismatch detected. Majority shift is Swing Shift (7 employees), but 1 employee has a different shift: EMP-1001 (Day Shift).",
            },
            "metadata": {"test_case": "seven_swing_one_day"},
        },
        # 8 employees: 7 day + 1 swing - should fail
        {
            "inputs": {"employee_ids": ["EMP-1001", "EMP-1002", "EMP-1003", "EMP-1004", "EMP-1005", "EMP-1010", "EMP-1011", "EMP-1016"]},
            "outputs": {
                "verdict": "fail",
                "reasoning": "Shift mismatch detected. Majority shift is Day Shift (7 employees), but 1 employee has a different shift: EMP-1016 (Swing Shift).",
            },
            "metadata": {"test_case": "seven_day_one_swing"},
        },
        # 8 employees: 7 night + 1 swing - should fail
        {
            "inputs": {"employee_ids": ["EMP-1006", "EMP-1007", "EMP-1008", "EMP-1009", "EMP-1014", "EMP-1025", "EMP-1026", "EMP-1016"]},
            "outputs": {
                "verdict": "fail",
                "reasoning": "Shift mismatch detected. Majority shift is Night Shift (7 employees), but 1 employee has a different shift: EMP-1016 (Swing Shift).",
            },
            "metadata": {"test_case": "seven_night_one_swing"},
        },
        # 8 employees: 7 swing + 1 night - should fail
        {
            "inputs": {"employee_ids": ["EMP-1016", "EMP-1017", "EMP-1018", "EMP-1019", "EMP-1034", "EMP-1035", "EMP-1036", "EMP-1006"]},
            "outputs": {
                "verdict": "fail",
                "reasoning": "Shift mismatch detected. Majority shift is Swing Shift (7 employees), but 1 employee has a different shift: EMP-1006 (Night Shift).",
            },
            "metadata": {"test_case": "seven_swing_one_night"},
        },
    ]
    
    return edge_cases


def create_evaluation_examples(employees: list, vanpools: list, shifts: list) -> list:
    """Create evaluation examples from mock data.
    
    Returns:
        List of example dicts with inputs, outputs, and metadata
    """
    examples = []
    
    # Add custom edge cases first
    print("\n  Custom edge cases:")
    edge_cases = create_custom_edge_cases()
    for case in edge_cases:
        case["metadata"]["reasoning"] = case["outputs"]["reasoning"]
        examples.append(case)
        test_name = case["metadata"]["test_case"]
        verdict = case["outputs"]["verdict"].upper()
        print(f"    {test_name}: {verdict}")
    
    # Add vanpool-derived examples
    print("\n  Vanpool-derived examples:")
    for vanpool in vanpools:
        analysis = analyze_vanpool_shifts(vanpool, employees, shifts)
        
        # Input: list of employee IDs
        employee_ids = [rider["employee_id"] for rider in vanpool["riders"]]
        
        example = {
            "inputs": {
                "employee_ids": employee_ids,
            },
            "outputs": {
                "verdict": analysis["expected_verdict"],
                "reasoning": analysis["reasoning"],
            },
            "metadata": {
                "test_case": vanpool["vanpool_id"],
                "reasoning": analysis["reasoning"],
            },
        }
        examples.append(example)
        
        print(f"    {vanpool['vanpool_id']}: {analysis['expected_verdict'].upper()} "
              f"({analysis['shift_breakdown']})")
    
    return examples


def create_langsmith_dataset(dataset_name: str, examples: list, description: str = None):
    """Create or update a LangSmith dataset with the given examples.
    
    Args:
        dataset_name: Name of the dataset
        examples: List of example dicts with inputs, outputs, and metadata
        description: Optional description for the dataset
    """
    from langsmith import Client
    
    client = Client()
    
    # Check if dataset already exists
    existing_datasets = list(client.list_datasets(dataset_name=dataset_name))
    
    if existing_datasets:
        dataset = existing_datasets[0]
        print(f"\n✓ Found existing dataset: {dataset_name} (id: {dataset.id})")
        
        # Delete existing examples to replace with new ones
        existing_examples = list(client.list_examples(dataset_id=dataset.id))
        if existing_examples:
            print(f"  Deleting {len(existing_examples)} existing examples...")
            for ex in existing_examples:
                client.delete_example(ex.id)
    else:
        # Create new dataset
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description=description or "Evaluation dataset for Shift Specialist agent",
        )
        print(f"\n✓ Created new dataset: {dataset_name} (id: {dataset.id})")
    
    # Add examples - extract inputs, outputs, and metadata as separate lists
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
    print("Pool Patrol - LangSmith Dataset Creator")
    print("=" * 60)
    
    # Check for API key
    if not os.environ.get("LANGSMITH_API_KEY"):
        print("\n✗ Error: LANGSMITH_API_KEY environment variable not set")
        print("  Set your API key to create datasets on LangSmith.")
        return 1
    
    # Load mock data
    print("\n1. Loading mock data...")
    employees, vanpools, shifts = load_mock_data()
    print(f"   Loaded {len(employees)} employees, {len(vanpools)} vanpools, {len(shifts)} shifts")
    
    # Create evaluation examples
    print("\n2. Analyzing vanpools for expected verdicts...")
    examples = create_evaluation_examples(employees, vanpools, shifts)
    
    # Summary
    pass_count = sum(1 for e in examples if e["outputs"]["verdict"] == "pass")
    fail_count = sum(1 for e in examples if e["outputs"]["verdict"] == "fail")
    print(f"\n   Summary: {pass_count} PASS, {fail_count} FAIL")
    
    # Create LangSmith dataset
    print("\n3. Creating LangSmith dataset...")
    dataset_name = "shift-specialist-eval"
    description = (
        "Evaluation dataset for the Shift Specialist agent. "
        "Tests whether the agent correctly identifies shift mismatches in vanpools. "
        "Created from Pool Patrol mock data."
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
