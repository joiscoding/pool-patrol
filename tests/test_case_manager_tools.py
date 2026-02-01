#!/usr/bin/env python3
"""Test script for the Case Manager tools.

This script tests the individual tools used by the Case Manager agent:
- run_shift_specialist
- run_location_specialist (stubbed)
- upsert_case (create or update)
- get_case_status
- close_case
- run_outreach
- cancel_membership

Run from the project root:

    poetry run python tests/test_case_manager_tools.py

Make sure you have:
1. Run the database seed: bun run db:seed (or npx prisma db seed)
2. For agent tools: Set OPENAI_API_KEY in your environment
3. For email sending: Set RESEND_API_KEY (optional, emails will fail gracefully without it)
"""

import os
import sys
from pathlib import Path

# Add packages to path for development
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(project_root / ".env", override=True)

# Configure LangSmith tracing
from agents.utils import configure_langsmith
langsmith_enabled = configure_langsmith()

# Store case_id from test_open_case so test_close_case can close the same case
_test_case_id = None


# =============================================================================
# Test Utilities
# =============================================================================


def print_header(title: str) -> None:
    """Print a formatted test header."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def check_api_key() -> bool:
    """Check if OPENAI_API_KEY is set."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n⚠ OPENAI_API_KEY not set. Skipping this test.")
        return False
    return True


# =============================================================================
# Verification Specialist Tool Tests
# =============================================================================


def test_run_location_specialist():
    """Test the stubbed location specialist tool."""
    print_header("Testing run_location_specialist tool (stubbed)")

    from tools.case_manager_tools import run_location_specialist

    print("\n1. Running location specialist for test employees...")
    result = run_location_specialist.invoke({
        "employee_ids": ["EMP-1001", "EMP-1002"],
        "vanpool_id": "VP-101",
    })

    print(f"   Verdict: {result['verdict']}")
    print(f"   Confidence: {result['confidence']}")
    print(f"   Reasoning: {result['reasoning']}")
    print(f"   Evidence: {result['evidence']}")

    # Verify stub always passes
    if result["verdict"] != "pass":
        print("   ✗ Stubbed tool should always return 'pass'")
        return False

    if result["confidence"] != 5:
        print("   ✗ Stubbed tool should return confidence 5")
        return False

    print("\n✓ run_location_specialist tool working correctly!")
    return True


def test_run_shift_specialist():
    """Test the shift specialist tool (calls real agent)."""
    print_header("Testing run_shift_specialist tool")

    if not check_api_key():
        return None

    from tools.case_manager_tools import run_shift_specialist

    print("\n1. Running shift specialist for VP-101 employees...")
    print("   This calls the real Shift Specialist agent (may take a moment)...\n")

    # Use employees from VP-101 (from mock data)
    result = run_shift_specialist.invoke({
        "employee_ids": ["EMP-1001", "EMP-1002", "EMP-1003"],
    })

    print(f"   Verdict: {result['verdict']}")
    print(f"   Confidence: {result['confidence']}")
    print(f"   Reasoning: {result['reasoning'][:100]}...")
    print(f"   Evidence count: {len(result.get('evidence', []))}")

    # Verify structure and expected outcome
    if "verdict" not in result:
        print("   ✗ Result should have a verdict")
        return False

    if result["verdict"] != "pass":
        print(f"   ✗ Expected verdict 'pass' for VP-101 employees, got '{result['verdict']}'")
        return False

    if "confidence" not in result or not (1 <= result["confidence"] <= 5):
        print("   ✗ Result should have confidence 1-5")
        return False

    print("\n✓ run_shift_specialist tool working correctly!")
    return True


# =============================================================================
# Case Lifecycle Tool Tests
# =============================================================================


def test_upsert_case():
    """Test creating and updating investigation cases."""
    global _test_case_id
    print_header("Testing upsert_case tool")

    from tools.case_manager_tools import upsert_case
    from core.database import get_session
    from core.db_models import Case, CaseStatus

    # Use a test-only vanpool ID that won't exist in mock data
    print("\n1. Creating a new case for VP-TEST-001...")
    result = upsert_case.invoke({
        "vanpool_id": "VP-TEST-001",
        "reason": "Test case - shift mismatch detected",
        "failed_checks": ["shift"],
    })

    if "error" in result:
        print(f"   Error: {result['error']}")
        return False

    _test_case_id = result['case_id']
    created = result.get('created', True)
    print(f"   Case ID: {_test_case_id}")
    print(f"   Status: {result['status']}")
    print(f"   Vanpool ID: {result['vanpool_id']}")
    print(f"   Created: {created}")

    if not _test_case_id:
        print("   ✗ Should have returned a case_id")
        return False

    # Verify case exists in database
    print("\n2. Verifying case exists in database...")
    with get_session() as session:
        db_case = session.query(Case).filter(Case.case_id == _test_case_id).first()
        if db_case is None:
            print(f"   ✗ Case {_test_case_id} not found in database")
            return False
        print(f"   ✓ Case found in database with status: {db_case.status}")

    # Test updating the case
    print("\n3. Updating the case with new status...")
    update_result = upsert_case.invoke({
        "vanpool_id": "VP-TEST-001",
        "case_id": _test_case_id,
        "reason": "Updated reason - re-verification pending",
        "failed_checks": ["shift", "location"],
        "status": "pending_reply",
    })

    if "error" in update_result:
        print(f"   Error: {update_result['error']}")
        return False

    if update_result.get('created', True) is True:
        print("   ✗ Should have updated existing case, not created new")
        return False

    print(f"   ✓ Case updated, created={update_result.get('created')}")
    print(f"   New status: {update_result['status']}")

    # Verify update in database
    print("\n4. Verifying update in database...")
    with get_session() as session:
        db_case = session.query(Case).filter(Case.case_id == _test_case_id).first()
        if db_case is None:
            print(f"   ✗ Case {_test_case_id} not found in database")
            return False
        if db_case.status != "pending_reply":
            print(f"   ✗ Expected status 'pending_reply', got '{db_case.status}'")
            return False
        meta = db_case.case_metadata or {}
        if "location" not in meta.get("failed_checks", []):
            print("   ✗ Failed checks should include 'location'")
            return False
        print(f"   ✓ Case updated correctly: status={db_case.status}, failed_checks={meta.get('failed_checks')}")

    print("\n✓ upsert_case tool working correctly!")
    return True


def test_get_case_status():
    """Test getting case status."""
    print_header("Testing get_case_status tool")

    from tools.case_manager_tools import get_case_status

    # Use CASE-001 from mock data
    print("\n1. Getting status for CASE-001...")
    result = get_case_status.invoke({"case_id": "CASE-001"})

    if "error" in result:
        print(f"   Error: {result['error']}")
        return False

    print(f"   Case ID: {result['case_id']}")
    print(f"   Vanpool ID: {result['vanpool_id']}")
    print(f"   Status: {result['status']}")
    print(f"   Created At: {result['created_at']}")
    print(f"   Has Email Thread: {result.get('has_email_thread', False)}")
    if result.get("email_thread_id"):
        print(f"   Email Thread ID: {result['email_thread_id']}")

    # Test non-existent case
    print("\n2. Getting status for non-existent case...")
    result_404 = get_case_status.invoke({"case_id": "CASE-FAKE"})
    if "error" in result_404:
        print(f"   ✓ Correctly returned error: {result_404['error']}")
    else:
        print("   ✗ Should have returned error for non-existent case")
        return False

    print("\n✓ get_case_status tool working correctly!")
    return True


def test_close_case():
    """Test closing a case (closes the case created by test_upsert_case)."""
    global _test_case_id
    print_header("Testing close_case tool")

    from tools.case_manager_tools import close_case
    from core.database import get_session
    from core.db_models import Case, CaseStatus

    # Use the case created by test_upsert_case
    if not _test_case_id:
        print("   ✗ No case ID from test_upsert_case - run test_upsert_case first")
        return False

    print(f"\n1. Closing case {_test_case_id} (created by test_upsert_case)...")
    result = close_case.invoke({
        "case_id": _test_case_id,
        "outcome": "resolved",
        "reason": "Test closure - employee updated data",
    })

    if "error" in result:
        print(f"   Error: {result['error']}")
        return False

    print(f"   Case ID: {result['case_id']}")
    print(f"   Status: {result['status']}")
    print(f"   Outcome: {result['outcome']}")
    print(f"   Resolved At: {result['resolved_at']}")

    # Verify case is closed in database
    print("\n2. Verifying case is closed in database...")
    with get_session() as session:
        db_case = session.query(Case).filter(Case.case_id == _test_case_id).first()
        if db_case is None:
            print(f"   ✗ Case {_test_case_id} not found in database")
            return False
        if db_case.status != CaseStatus.RESOLVED:
            print(f"   ✗ Expected status 'resolved', got '{db_case.status}'")
            return False
        print(f"   ✓ Case status in database: {db_case.status}")

    # Test invalid outcome
    print("\n3. Testing invalid outcome...")
    invalid_result = close_case.invoke({
        "case_id": _test_case_id,
        "outcome": "invalid_outcome",
        "reason": "Test",
    })
    if "error" in invalid_result:
        print(f"   ✓ Correctly returned error: {invalid_result['error']}")
    else:
        print("   ✗ Should have returned error for invalid outcome")
        return False

    print("\n✓ close_case tool working correctly!")
    return True


# =============================================================================
# Outreach Tool Tests
# =============================================================================


def test_run_outreach():
    """Test the run_outreach tool (calls real Outreach Agent)."""
    print_header("Testing run_outreach tool")

    if not check_api_key():
        return None

    from tools.case_manager_tools import run_outreach

    print("\n1. Running outreach for CASE-001...")
    print("   This calls the real Outreach Agent (may take a moment)...\n")

    result = run_outreach.invoke({
        "case_id": "CASE-001",
        "context": "Shift verification failed - testing outreach tool",
    })

    if "error" in result:
        print(f"   Error: {result['error']}")
        return False

    print(f"   Email Thread ID: {result.get('email_thread_id')}")
    print(f"   Bucket: {result.get('bucket')}")
    print(f"   HITL Required: {result.get('hitl_required')}")
    print(f"   Sent: {result.get('sent')}")

    print("\n✓ run_outreach tool working correctly!")
    return True


# =============================================================================
# Membership Action Tool Tests
# =============================================================================


def test_cancel_membership():
    """Test the cancel_membership tool."""
    print_header("Testing cancel_membership tool")

    from tools.case_manager_tools import cancel_membership

    # Note: This test actually removes a rider from the database
    # In production, this would be gated by HITL middleware

    print("\n1. Testing cancel_membership for non-existent case...")
    result = cancel_membership.invoke({
        "case_id": "CASE-FAKE",
        "employee_id": "EMP-1001",
        "reason": "Test cancellation",
    })

    if "error" in result:
        print(f"   ✓ Correctly returned error: {result['error']}")
    else:
        print("   ✗ Should have returned error for non-existent case")
        return False

    # Test with valid case but non-rider employee
    print("\n2. Testing cancel_membership for non-rider employee...")
    result2 = cancel_membership.invoke({
        "case_id": "CASE-001",
        "employee_id": "EMP-9999",
        "reason": "Test cancellation",
    })

    if "error" in result2:
        print(f"   ✓ Correctly returned error: {result2['error']}")
    else:
        print("   ✗ Should have returned error for non-rider employee")
        return False

    # Note: We don't test actual cancellation to avoid modifying test data
    print("\n   Note: Skipping actual cancellation to preserve test data")

    print("\n✓ cancel_membership tool error handling working correctly!")
    return True


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all tool tests."""
    print_header("Pool Patrol - Case Manager Tools Test Suite")

    print("\n📋 Testing Case Manager tools individually")
    print("   For full agent tests, see: tests/test_case_manager.py (coming soon)")

    # Reset database engine once at start
    from core.database import reset_engine
    reset_engine()

    results = {}

    # Verification specialist tests
    results["run_location_specialist"] = test_run_location_specialist()
    results["run_shift_specialist"] = test_run_shift_specialist()

    # Case lifecycle tests
    results["upsert_case"] = test_upsert_case()
    results["get_case_status"] = test_get_case_status()
    results["close_case"] = test_close_case()

    # Outreach tool test
    results["run_outreach"] = test_run_outreach()

    # Membership action tests
    results["cancel_membership"] = test_cancel_membership()

    # Summary
    print_header("Test Summary")

    for name, result in results.items():
        if result is True:
            status = "✓ Pass"
        elif result is False:
            status = "✗ Fail"
        else:
            status = "⚠ Skipped"
        print(f"  {name}: {status}")

    # Return exit code
    failures = [r for r in results.values() if r is False]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
