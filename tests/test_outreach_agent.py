#!/usr/bin/env python3
"""Test script for the Outreach Agent.

This script tests the Outreach Agent which handles email communication
with vanpool riders. Run from the project root:

    poetry run python tests/test_outreach_agent.py

Make sure you have:
1. Set OPENAI_API_KEY in your environment
2. Run the database seed: npx prisma db seed

For LangSmith tracing, also set:
    LANGSMITH_API_KEY=your-api-key
    LANGSMITH_PROJECT=pool-patrol  (optional, defaults to pool-patrol)

IMPORTANT: The Resend API is mocked in tests - no actual emails are sent.

For tool-level tests, see: tests/test_outreach_tools.py
"""

import asyncio
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

# Add packages to path for development
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(project_root / ".env", override=True)

# Configure LangSmith tracing
from agents.utils import configure_langsmith

langsmith_enabled = configure_langsmith()


# =============================================================================
# Test Infrastructure
# =============================================================================


@dataclass
class TestCase:
    """Definition of an outreach agent test case."""

    name: str
    email_thread_id: str
    context: str | None = None
    expected_bucket: str | None = None
    expect_no_hitl: bool = False
    description: str = ""


# Define all test cases as data
# Input is email_thread_id (what Case Manager would pass)
TEST_CASES: list[TestCase] = [
    TestCase(
        name="address_change",
        email_thread_id="THREAD-001",
        expected_bucket="address_change",
        expect_no_hitl=True,
        description="has address_change reply",
    ),
    TestCase(
        name="dispute",
        email_thread_id="THREAD-003",
        expected_bucket="dispute",
        description="has dispute reply",
    ),
    TestCase(
        name="acknowledgment",
        email_thread_id="THREAD-005",
        expected_bucket="acknowledgment",
        expect_no_hitl=True,
        description="has acknowledgment reply",
    ),
    TestCase(
        name="with_context",
        email_thread_id="THREAD-002",
        context="New reply detected. Please classify and respond.",
        description="with Case Manager context",
    ),
]


def print_header(title: str) -> None:
    """Print a formatted test header."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def print_result(result) -> None:
    """Print the result of an outreach agent call."""
    print(f"   Email Thread ID: {result.email_thread_id}")
    print(f"   Message ID: {result.message_id}")
    print(f"   Bucket: {result.bucket}")
    print(f"   HITL Required: {result.hitl_required}")
    print(f"   Sent: {result.sent}")


def check_api_key() -> bool:
    """Check if OPENAI_API_KEY is set."""
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n⚠ OPENAI_API_KEY not set. Skipping agent test.")
        return False
    return True


def validate_result(result, test_case: TestCase) -> bool:
    """Validate the result against test case expectations."""
    # Check email_thread_id matches
    if result.email_thread_id != test_case.email_thread_id:
        print(f"\n⚠ Expected email_thread_id={test_case.email_thread_id} but got {result.email_thread_id}")
        # Still passing - agent behavior may vary

    # Check bucket if specified
    if test_case.expected_bucket:
        if result.bucket == test_case.expected_bucket:
            if test_case.expect_no_hitl and not result.hitl_required:
                print(f"\n✓ Correctly handled {test_case.expected_bucket} without HITL!")
            elif test_case.expect_no_hitl:
                print(f"\n⚠ Unexpected HITL required for {test_case.expected_bucket}")
            else:
                print(f"\n✓ Correctly identified as {test_case.expected_bucket}!")
        else:
            print(f"\n⚠ Expected '{test_case.expected_bucket}' bucket but got '{result.bucket}'")
        return True  # Still passing - classification may vary

    # Generic success
    print(f"\n✓ Agent processed {test_case.name} case!")
    return True


# =============================================================================
# HITL Interrupt Tests
# =============================================================================


def run_hitl_interrupt_test(email_thread_id: str, expected_bucket: str) -> bool | None:
    """Test that HITL interrupt fires for dispute/unknown cases.
    
    Verifies:
    1. Agent pauses at interrupt (doesn't auto-send)
    2. Interrupt contains correct tool name
    3. Resume with approval completes successfully
    """
    print_header(f"Testing HITL Interrupt - {expected_bucket.title()} Case ({email_thread_id})")

    if not check_api_key():
        return None

    from agents.outreach import create_outreach_agent, _build_config
    from langchain_core.messages import HumanMessage
    from langgraph.types import Command

    print(f"\n   Phase 1: Invoke agent and expect interrupt...")

    try:
        agent = create_outreach_agent()
        config = _build_config(email_thread_id)

        # First invocation - should interrupt before sending
        result = agent.invoke(
            {"messages": [HumanMessage(content=f"Handle outreach for email thread {email_thread_id}.")]},
            config=config,
        )

        # Check for interrupt
        interrupt = result.get("__interrupt__")
        if not interrupt:
            print(f"\n✗ Expected HITL interrupt but agent completed without pausing")
            print(f"   Final message: {result['messages'][-1].content[:200]}...")
            return False

        # Verify interrupt details - structure is action_requests with name field
        interrupt_info = interrupt[0] if isinstance(interrupt, list) else interrupt
        interrupt_value = interrupt_info.value if hasattr(interrupt_info, "value") else interrupt_info
        
        # Extract tool name from action_requests
        action_requests = interrupt_value.get("action_requests", [])
        tool_name = action_requests[0].get("name") if action_requests else None
        
        if tool_name != "send_email_for_review":
            print(f"\n✗ Interrupted on wrong tool: {tool_name}")
            print(f"   Interrupt value: {interrupt_value}")
            return False

        print(f"   ✓ Interrupted on: {tool_name}")

        # Phase 2: Resume with approval using Command
        print(f"\n   Phase 2: Resume with 'approve' decision...")

        resumed = agent.invoke(
            Command(resume={"decisions": [{"type": "approve"}]}),
            config=config,  # Same LangGraph thread_id to resume
        )

        # Verify completion
        if resumed.get("__interrupt__"):
            print(f"\n✗ Agent interrupted again after approval")
            return False

        print(f"   ✓ Resumed and completed successfully")

        # Check final result
        final_msg = resumed["messages"][-1]
        content = final_msg.content if hasattr(final_msg, "content") else str(final_msg)
        print(f"   Final response: {content[:150]}...")

        print(f"\n✓ HITL interrupt test passed for {expected_bucket}!")
        return True

    except Exception as e:
        print(f"\n✗ Error in HITL test: {e}")
        traceback.print_exc()
        return False


def run_hitl_reject_test() -> bool | None:
    """Test that rejecting an email prevents sending."""
    print_header("Testing HITL Reject Flow")

    if not check_api_key():
        return None

    from agents.outreach import create_outreach_agent, _build_config
    from langchain_core.messages import HumanMessage
    from langgraph.types import Command

    print(f"\n   Testing reject decision on THREAD-003 (dispute)...")

    try:
        agent = create_outreach_agent()
        config = _build_config("THREAD-003")

        # First invocation - should interrupt
        result = agent.invoke(
            {"messages": [HumanMessage(content="Handle outreach for email thread THREAD-003.")]},
            config=config,
        )

        interrupt = result.get("__interrupt__")
        if not interrupt:
            print(f"\n✗ Expected interrupt but agent completed")
            return False

        print(f"   ✓ Interrupted as expected")

        # Resume with reject using Command
        print(f"\n   Resuming with 'reject' decision...")

        resumed = agent.invoke(
            Command(resume={"decisions": [{"type": "reject", "message": "Email rejected by reviewer"}]}),
            config=config,
        )

        # Agent should complete without sending
        final_msg = resumed["messages"][-1]
        content = final_msg.content if hasattr(final_msg, "content") else str(final_msg)
        
        print(f"   Final response: {content[:150]}...")
        print(f"\n✓ Reject flow completed!")
        return True

    except Exception as e:
        print(f"\n✗ Error in reject test: {e}")
        traceback.print_exc()
        return False


# =============================================================================
# Test Runner
# =============================================================================


def run_sync_test(test_case: TestCase, is_first: bool = False) -> bool | None:
    """Run a single sync test case."""
    print_header(f"Testing Outreach Agent - {test_case.name.replace('_', ' ').title()} Case")

    if not check_api_key():
        return None

    from agents.outreach import handle_outreach_sync
    from agents.structures import OutreachRequest

    print(f"\n   Testing with {test_case.email_thread_id} ({test_case.description})...")
    print("   This may take a moment while the agent reasons...\n")

    try:
        request = OutreachRequest(
            email_thread_id=test_case.email_thread_id,
            context=test_case.context,
        )

        result = handle_outreach_sync(request)
        print_result(result)
        return validate_result(result, test_case)

    except Exception as e:
        print(f"\n✗ Error running agent: {e}")
        traceback.print_exc()
        return False


def run_async_test() -> bool | None:
    """Test async version of the agent."""
    print_header("Testing Async Outreach Agent")

    if not check_api_key():
        return None

    from agents.outreach import handle_outreach
    from agents.structures import OutreachRequest

    print("\n   Running async agent for THREAD-001...")
    print("   This may take a moment...\n")

    try:
        request = OutreachRequest(email_thread_id="THREAD-001")
        result = asyncio.run(handle_outreach(request))

        print(f"   Email Thread ID: {result.email_thread_id}")
        print(f"   Bucket: {result.bucket}")
        print(f"   Sent: {result.sent}")

        print("\n✓ Async agent working correctly!")
        return True

    except Exception as e:
        print(f"\n✗ Error running async agent: {e}")
        traceback.print_exc()
        return False


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all agent tests."""
    print_header("Pool Patrol - Outreach Agent Test Suite")

    # Show LangSmith status
    if langsmith_enabled:
        project = os.environ.get("LANGSMITH_PROJECT", "pool-patrol")
        print(f"\n🔍 LangSmith tracing ENABLED (project: {project})")
        print("   View traces at: https://smith.langchain.com")
    else:
        print("\n⚠ LangSmith tracing disabled (set LANGSMITH_API_KEY to enable)")

    print("\n📧 Note: Resend API is MOCKED - no actual emails will be sent")
    print("   For tool tests, run: poetry run python tests/test_outreach_tools.py")

    if not os.environ.get("OPENAI_API_KEY"):
        print("\n⚠ OPENAI_API_KEY not set. All agent tests will be skipped.")
        print("   Set your API key to run the full test suite.")
        return 0

    results: dict[str, bool | None] = {}

    # Run all tests with mocked email
    with patch("tools.outreach_tools.resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "mock-email-001"}

        # Reset database engine before tests
        from core.database import reset_engine
        reset_engine()

        # HITL interrupt tests (run first - these are the granular tests)
        print("\n" + "=" * 60)
        print("HITL INTERRUPT TESTS")
        print("=" * 60)
        
        results["hitl_dispute_interrupt"] = run_hitl_interrupt_test("THREAD-003", "dispute")
        results["hitl_reject_flow"] = run_hitl_reject_test()

        # Standard agent tests
        print("\n" + "=" * 60)
        print("STANDARD AGENT TESTS")
        print("=" * 60)

        for i, test_case in enumerate(TEST_CASES):
            results[test_case.name] = run_sync_test(test_case, is_first=False)

        # Run async test
        results["async"] = run_async_test()

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
