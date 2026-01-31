#!/usr/bin/env python3
"""Test script for the Outreach Agent tools.

This script tests the individual tools used by the Outreach Agent:
- get_email_thread
- classify_reply
- send_email
- send_email_for_review

Run from the project root:

    poetry run python tests/test_outreach_tools.py

Make sure you have:
1. Run the database seed: npx prisma db seed
2. For classification tests: Set OPENAI_API_KEY in your environment

IMPORTANT: The Resend API is mocked in tests - no actual emails are sent.
"""

import os
import sys
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
# Database Tools Tests
# =============================================================================


def test_get_email_thread():
    """Test fetching email thread by thread_id."""
    print("\n" + "=" * 60)
    print("Testing get_email_thread tool")
    print("=" * 60)

    # Reset database engine to ensure fresh connection
    from core.database import reset_engine
    reset_engine()

    from tools.outreach_tools import get_email_thread

    # Test fetching an existing thread
    print("\n1. Fetching THREAD-001...")
    result = get_email_thread.invoke({"thread_id": "THREAD-001"})

    if "error" in result:
        print(f"   Error: {result['error']}")
        return False

    print(f"   Thread ID: {result['thread_id']}")
    print(f"   Case ID: {result['case_id']}")
    print(f"   Subject: {result['subject'][:50]}...")
    print(f"   Status: {result['status']}")
    print(f"   Messages: {len(result['messages'])}")

    for i, msg in enumerate(result["messages"][:2], 1):
        direction = msg["direction"]
        preview = msg["body"][:60].replace("\n", " ")
        print(f"   {i}. [{direction}] {preview}...")

    # Test non-existent thread
    print("\n2. Fetching non-existent thread...")
    result_404 = get_email_thread.invoke({"thread_id": "THREAD-FAKE"})
    if "error" in result_404:
        print(f"   ✓ Correctly returned error: {result_404['error']}")
    else:
        print("   ✗ Should have returned error for non-existent thread")
        return False

    print("\n✓ get_email_thread tool working correctly!")
    return True


# =============================================================================
# Classification Tool Tests
# =============================================================================


def test_classify_reply():
    """Test the reply classification tool."""
    print("\n" + "=" * 60)
    print("Testing classify_reply tool")
    print("=" * 60)

    if not os.environ.get("OPENAI_API_KEY"):
        print("\n⚠ OPENAI_API_KEY not set. Skipping classification test.")
        return None

    from tools.outreach_tools import classify_reply

    test_cases = [
        {
            "name": "address_change",
            "message": "Hi, I recently moved to San Jose. My new address is 123 Main St, San Jose, CA 95112.",
            "expected": "address_change",
        },
        {
            "name": "shift_change",
            "message": "Hello, I switched to the night shift last month. I now work 10pm to 6am.",
            "expected": "shift_change",
        },
        {
            "name": "acknowledgment",
            "message": "Thanks for checking. My address is correct and I still use the vanpool daily.",
            "expected": "acknowledgment",
        },
        {
            "name": "info_request",
            "message": "Can you explain why I'm being reviewed? What information do you need from me?",
            "expected": "info_request",
        },
        {
            "name": "dispute",
            "message": "This is ridiculous. I've been on this vanpool for years without problems. This feels like harassment.",
            "expected": "dispute",
        },
    ]

    all_passed = True
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. Testing '{case['name']}' classification...")
        print(f"   Message: \"{case['message'][:50]}...\"")

        result = classify_reply.invoke({"message_body": case["message"]})

        bucket = result.get("bucket", "unknown")
        reasoning = result.get("reasoning", "No reasoning provided")

        print(f"   Result: {bucket}")
        print(f"   Reasoning: {reasoning[:80]}...")

        if bucket == case["expected"]:
            print(f"   ✓ Correctly classified as '{case['expected']}'")
        else:
            print(f"   ✗ Expected '{case['expected']}' but got '{bucket}'")
            all_passed = False

    if all_passed:
        print("\n✓ classify_reply tool working correctly!")
    else:
        print("\n⚠ Some classifications did not match expected buckets")

    return all_passed


# =============================================================================
# Email Sending Tests (with mocked Resend API)
# =============================================================================


@patch("tools.outreach_tools.resend.Emails.send")
def test_send_email(mock_send):
    """Test send_email tool with mocked Resend API."""
    print("\n" + "=" * 60)
    print("Testing send_email tool (mocked)")
    print("=" * 60)

    # Mock successful response
    mock_send.return_value = {"id": "mock-email-id-123"}

    from tools.outreach_tools import send_email

    print("\n1. Sending test email...")
    result = send_email.invoke({
        "to": ["test@example.com"],
        "subject": "Test Subject",
        "body": "Test body content",
    })

    print(f"   Result: {result}")

    if result.get("sent"):
        print(f"   ✓ Email sent successfully (ID: {result.get('id')})")
    else:
        print(f"   ✗ Email failed to send: {result.get('error')}")
        return False

    # Verify mock was called correctly
    mock_send.assert_called_once()
    call_args = mock_send.call_args[0][0]
    assert call_args["to"] == ["test@example.com"]
    assert call_args["subject"] == "Test Subject"
    print("   ✓ Resend API called with correct arguments")

    print("\n✓ send_email tool working correctly!")
    return True


@patch("tools.outreach_tools.resend.Emails.send")
def test_send_email_for_review(mock_send):
    """Test send_email_for_review tool with mocked Resend API."""
    print("\n" + "=" * 60)
    print("Testing send_email_for_review tool (mocked)")
    print("=" * 60)

    # Mock successful response
    mock_send.return_value = {"id": "mock-review-email-456"}

    from tools.outreach_tools import send_email_for_review

    print("\n1. Sending email for review...")
    result = send_email_for_review.invoke({
        "to": ["dispute@example.com"],
        "subject": "Re: Your Vanpool Review",
        "body": "We understand your concern...",
    })

    print(f"   Result: {result}")

    if result.get("sent"):
        print(f"   ✓ Email sent (ID: {result.get('id')})")
        print("   Note: In production, HITL middleware would intercept this call")
    else:
        print(f"   ✗ Email failed: {result.get('error')}")
        return False

    print("\n✓ send_email_for_review tool working correctly!")
    return True


@patch("tools.outreach_tools.resend.Emails.send")
def test_send_email_no_api_key(mock_send):
    """Test send_email handles missing API key gracefully."""
    print("\n" + "=" * 60)
    print("Testing send_email error handling")
    print("=" * 60)

    # Temporarily clear the API key
    import tools.outreach_tools as outreach_tools
    original_key = outreach_tools.resend.api_key
    outreach_tools.resend.api_key = ""

    from tools.outreach_tools import send_email

    print("\n1. Testing with no API key...")
    result = send_email.invoke({
        "to": ["test@example.com"],
        "subject": "Test",
        "body": "Test",
    })

    # Restore key
    outreach_tools.resend.api_key = original_key

    if result.get("sent") is False and "error" in result:
        print(f"   ✓ Correctly returned error: {result['error']}")
    else:
        print("   ✗ Should have returned error for missing API key")
        return False

    print("\n✓ Error handling working correctly!")
    return True


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all tool tests."""
    print("\n" + "=" * 60)
    print("Pool Patrol - Outreach Tools Test Suite")
    print("=" * 60)

    print("\n📧 Note: Resend API is MOCKED - no actual emails will be sent")

    results = {}

    # Database tool tests
    results["get_email_thread"] = test_get_email_thread()

    # Classification tool tests (needs API key)
    results["classify_reply"] = test_classify_reply()

    # Email sending tool tests (mocked)
    results["send_email"] = test_send_email()
    results["send_email_for_review"] = test_send_email_for_review()
    results["error_handling"] = test_send_email_no_api_key()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

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
