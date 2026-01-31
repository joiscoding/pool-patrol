#!/usr/bin/env python3
"""Test script for the Shift Specialist agent.

This script demonstrates the Shift Specialist verifying shift compatibility
for groups of employees. Run from the project root:

    poetry run python tests/test_shift_specialist.py

Make sure you have:
1. Set OPENAI_API_KEY in your environment
2. Run the database seed: npx prisma db seed

For LangSmith tracing, also set:
    LANGSMITH_API_KEY=your-api-key
    LANGSMITH_PROJECT=pool-patrol  (optional, defaults to pool-patrol)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add packages to path for development
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from dotenv import load_dotenv

# Load environment variables (override=True ensures .env takes precedence over shell env)
load_dotenv(project_root / ".env", override=True)

# Configure LangSmith tracing
from agents.utils import configure_langsmith
langsmith_enabled = configure_langsmith()


def test_tools():
    """Test that the tools work correctly."""
    print("=" * 60)
    print("Testing LangChain Tools")
    print("=" * 60)
    
    # Reset database engine to ensure fresh connection
    from core.database import reset_engine  # type: ignore[import-not-found]
    reset_engine()
    
    from tools import get_vanpool_roster, get_employee_shifts, list_all_shifts
    
    # Test list_all_shifts
    print("\n1. Testing list_all_shifts...")
    shifts_result = list_all_shifts.invoke({})
    print(f"   Found {shifts_result['count']} shifts:")
    for shift in shifts_result["shifts"]:
        print(f"   - {shift['id']}: {shift['name']}")
    
    # Test get_vanpool_roster
    print("\n2. Testing get_vanpool_roster for VP-101...")
    roster_result = get_vanpool_roster.invoke({"vanpool_id": "VP-101"})
    if "error" in roster_result:
        print(f"   Error: {roster_result['error']}")
    else:
        print(f"   Vanpool: {roster_result['vanpool_id']}")
        print(f"   Work Site: {roster_result['work_site']}")
        print(f"   Rider Count: {roster_result['rider_count']}")
        print(f"   Riders:")
        for rider in roster_result["riders"][:3]:  # Show first 3
            print(f"   - {rider['employee_id']}: {rider['first_name']} {rider['last_name']}")
        if roster_result["rider_count"] > 3:
            print(f"   ... and {roster_result['rider_count'] - 3} more")
    
    # Test get_employee_shifts
    print("\n3. Testing get_employee_shifts for EMP-1001...")
    shift_result = get_employee_shifts.invoke({"employee_id": "EMP-1001"})
    if "error" in shift_result:
        print(f"   Error: {shift_result['error']}")
    else:
        print(f"   Employee: {shift_result['employee_name']}")
        print(f"   Shift: {shift_result['shift_name']}")
        print(f"   Schedule:")
        for day in shift_result["schedule"][:3]:  # Show first 3 days
            print(f"   - {day['day']}: {day['start_time']} - {day['end_time']}")
        print(f"   PTO Dates: {shift_result['pto_dates'] or 'None'}")
    
    # Test EMP-1014 (Leo Nguyen) - should be Night Shift (VP-103 mismatch case)
    print("\n4. Testing get_employee_shifts for EMP-1014 (should be Night Shift)...")
    shift_result_1014 = get_employee_shifts.invoke({"employee_id": "EMP-1014"})
    if "error" in shift_result_1014:
        print(f"   Error: {shift_result_1014['error']}")
        return False
    else:
        print(f"   Employee: {shift_result_1014['employee_name']}")
        print(f"   Shift: {shift_result_1014['shift_name']}")
        expected_shift = "Night Shift"
        if shift_result_1014['shift_name'] == expected_shift:
            print(f"   ✓ Correctly identified as {expected_shift}")
        else:
            print(f"   ✗ Expected '{expected_shift}' but got '{shift_result_1014['shift_name']}'")
            return False
    
    print("\n✓ All tools working correctly!")
    return True


def get_employee_ids_for_vanpool(vanpool_id: str) -> list[str]:
    """Helper to get employee IDs for a vanpool."""
    from tools import get_vanpool_roster
    roster = get_vanpool_roster.invoke({"vanpool_id": vanpool_id})
    if "error" in roster:
        return []
    return [rider["employee_id"] for rider in roster["riders"]]


def test_shift_specialist():
    """Test the Shift Specialist agent."""
    print("\n" + "=" * 60)
    print("Testing Shift Specialist Agent")
    print("=" * 60)
    
    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n⚠ OPENAI_API_KEY not set. Skipping agent test.")
        print("  Set your API key to test the full agent.")
        return False
    
    from agents import verify_employee_shifts_sync
    
    # Get employee IDs for VP-101 (Day Shift vanpool)
    employee_ids = get_employee_ids_for_vanpool("VP-101")
    print(f"\n1. Verifying {len(employee_ids)} employees from VP-101 (Day Shift vanpool)...")
    print(f"   Employee IDs: {employee_ids[:3]}..." if len(employee_ids) > 3 else f"   Employee IDs: {employee_ids}")
    print("   This may take a moment while the agent reasons...\n")
    
    try:
        result = verify_employee_shifts_sync(employee_ids)
        
        print(f"   Verdict: {result.verdict.upper()}")
        print(f"   Confidence: {result.confidence}/5")
        print(f"   Reasoning: {result.reasoning[:200]}..." if len(result.reasoning) > 200 else f"   Reasoning: {result.reasoning}")
        print(f"   Evidence items: {len(result.evidence)}")
        
        for i, evidence in enumerate(result.evidence[:3], 1):
            print(f"   {i}. {evidence}")
        
        print("\n✓ Shift Specialist agent working correctly!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error running agent: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mixed_shift_vanpool():
    """Test with VP-102 which has Night Shift employees."""
    print("\n" + "=" * 60)
    print("Testing VP-102 employees (Night Shift - should PASS)")
    print("=" * 60)
    
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n⚠ OPENAI_API_KEY not set. Skipping.")
        return False
    
    from agents import verify_employee_shifts_sync
    
    # Get employee IDs for VP-102
    employee_ids = get_employee_ids_for_vanpool("VP-102")
    print(f"\n   Verifying {len(employee_ids)} employees from VP-102...")
    print("   This may take a moment...\n")
    
    try:
        result = verify_employee_shifts_sync(employee_ids)
        
        print(f"   Verdict: {result.verdict.upper()}")
        print(f"   Confidence: {result.confidence}/5")
        print(f"   Reasoning: {result.reasoning[:200]}..." if len(result.reasoning) > 200 else f"   Reasoning: {result.reasoning}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


def test_mismatch_vanpool():
    """Test with VP-103 which has a shift mismatch (Day + Night)."""
    print("\n" + "=" * 60)
    print("Testing VP-103 employees (Mixed shifts - should FAIL)")
    print("=" * 60)
    
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n⚠ OPENAI_API_KEY not set. Skipping.")
        return False
    
    from agents import verify_employee_shifts_sync
    
    # Get employee IDs for VP-103 (5 Day Shift + 1 Night Shift)
    employee_ids = get_employee_ids_for_vanpool("VP-103")
    print(f"\n   Verifying {len(employee_ids)} employees from VP-103 (5 Day Shift + 1 Night Shift)...")
    print("   This may take a moment...\n")
    
    try:
        result = verify_employee_shifts_sync(employee_ids)
        
        print(f"   Verdict: {result.verdict.upper()}")
        print(f"   Confidence: {result.confidence}/5")
        print(f"   Reasoning: {result.reasoning[:300]}..." if len(result.reasoning) > 300 else f"   Reasoning: {result.reasoning}")
        print(f"\n   Evidence items: {len(result.evidence)}")
        for i, evidence in enumerate(result.evidence[:3], 1):
            desc = evidence.get('data', {}).get('description', str(evidence))
            print(f"   {i}. {desc[:100]}..." if len(desc) > 100 else f"   {i}. {desc}")
        
        # This should be a FAIL
        if result.verdict == "fail":
            print("\n✓ Correctly detected shift mismatch!")
            return True
        else:
            print("\n⚠ Expected FAIL but got PASS")
            return False
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_async_vanpools():
    """Test async verification for VP-102 and VP-103 employees in parallel."""
    print("\n" + "=" * 60)
    print("Testing async verification (VP-102 + VP-103 employees)")
    print("=" * 60)

    if not os.environ.get("OPENAI_API_KEY"):
        print("\n⚠ OPENAI_API_KEY not set. Skipping.")
        return False

    from agents import verify_employee_shifts

    # Get employee IDs for both vanpools
    employee_ids_102 = get_employee_ids_for_vanpool("VP-102")
    employee_ids_103 = get_employee_ids_for_vanpool("VP-103")

    async def run_checks():
        return await asyncio.gather(
            verify_employee_shifts(employee_ids_102),
            verify_employee_shifts(employee_ids_103),
        )

    print(f"\n   Verifying {len(employee_ids_102)} + {len(employee_ids_103)} employees concurrently...")
    print("   This may take a moment...\n")

    try:
        result_102, result_103 = asyncio.run(run_checks())

        print(f"   VP-102 employees Verdict: {result_102.verdict.upper()}")
        print(f"   VP-103 employees Verdict: {result_103.verdict.upper()}")

        if result_102.verdict != "pass":
            print("\n⚠ Expected VP-102 employees to PASS")
            return False
        if result_103.verdict != "fail":
            print("\n⚠ Expected VP-103 employees to FAIL")
            return False

        print("\n✓ Async verification returned expected verdicts!")
        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Pool Patrol - Shift Specialist Test Suite")
    print("=" * 60)
    
    # Show LangSmith status
    if langsmith_enabled:
        project = os.environ.get("LANGSMITH_PROJECT", "pool-patrol")
        print(f"\n🔍 LangSmith tracing ENABLED (project: {project})")
        print("   View traces at: https://smith.langchain.com")
    else:
        print("\n⚠ LangSmith tracing disabled (set LANGSMITH_API_KEY to enable)")
    
    # Test tools first (no API key needed)
    tools_ok = test_tools()
    
    if not tools_ok:
        print("\n✗ Tool tests failed. Fix issues before testing agent.")
        return 1
    
    # Test agent (needs API key)
    agent_ok = test_shift_specialist()
    
    mismatch_ok = False
    if agent_ok:
        # Run additional tests
        test_mixed_shift_vanpool()
        mismatch_ok = test_mismatch_vanpool()
        test_async_vanpools()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"  Tools: {'✓ Pass' if tools_ok else '✗ Fail'}")
    print(f"  Agent (PASS case): {'✓ Pass' if agent_ok else '⚠ Skipped (no API key)' if not os.environ.get('OPENAI_API_KEY') else '✗ Fail'}")
    print(f"  Agent (FAIL case): {'✓ Pass' if mismatch_ok else '⚠ Skipped' if not os.environ.get('OPENAI_API_KEY') else '✗ Fail'}")
    
    return 0 if tools_ok else 1


if __name__ == "__main__":
    sys.exit(main())
