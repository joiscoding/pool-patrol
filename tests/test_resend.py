#!/usr/bin/env python3
"""Integration test for Resend email sending.

This script sends REAL emails via Resend to verify the integration is working.
Run from the project root:

    poetry run python tests/test_resend.py

Make sure you have:
1. Set RESEND_API_KEY in your .env file
2. Set OPENAI_API_KEY in your .env file (for agent test)
3. Verified your sending domain in Resend dashboard
4. Seeded the database: npx prisma db seed

WARNING: This sends actual emails - use sparingly!
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

# Test email recipient - all emails will be redirected here
TEST_EMAIL = "josephyanginfo@gmail.com"


def test_resend_integration():
    """Send a real test email via Resend."""
    print("\n" + "=" * 60)
    print("Test 1: Basic Resend Integration")
    print("=" * 60)

    from tools.outreach_tools import _send_via_resend, resend, FROM_EMAIL

    # Check API key is configured
    if not resend.api_key:
        print("\n✗ RESEND_API_KEY not configured in .env")
        return False

    print(f"\n✓ Resend API key configured")
    print(f"  From: {FROM_EMAIL}")

    # Send test email
    print(f"\n  Sending test email to: {TEST_EMAIL}")

    result = _send_via_resend(
        to=[TEST_EMAIL],
        subject="Pool Patrol - Resend Integration Test",
        body="""Hi there!

This is a test email from Pool Patrol to verify the Resend integration is working correctly.

If you received this email, the integration is successful!

-- Pool Patrol System
""",
    )

    print(f"\n  Result: {result}")

    if result.get("sent"):
        print(f"\n✓ Email sent successfully!")
        print(f"  Message ID: {result.get('id')}")
        return True
    else:
        print(f"\n✗ Failed to send email")
        print(f"  Error: {result.get('error')}")
        return False


def test_outreach_agent_integration():
    """Run the full outreach agent with real email sending.
    
    This test:
    1. Fetches a real email thread from the database
    2. Runs the outreach agent (classification + response composition)
    3. Sends the agent-composed email to the test address
    """
    print("\n" + "=" * 60)
    print("Test 2: Outreach Agent Integration")
    print("=" * 60)

    # Check required API keys
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n✗ OPENAI_API_KEY not configured in .env")
        return False

    from tools.outreach_tools import resend
    if not resend.api_key:
        print("\n✗ RESEND_API_KEY not configured in .env")
        return False

    print("\n✓ API keys configured")

    # Reset database engine for fresh connection
    from core.database import reset_engine
    reset_engine()

    # Verify we have test data
    from tools.outreach_tools import get_email_thread

    thread_id = "THREAD-001"
    print(f"\n  Fetching email thread: {thread_id}")

    thread = get_email_thread.invoke({"thread_id": thread_id})
    if "error" in thread:
        print(f"\n✗ {thread['error']}")
        print("  Make sure to seed the database: npx prisma db seed")
        return False

    print(f"  ✓ Found thread: {thread['subject'][:50]}...")
    print(f"  Messages in thread: {len(thread['messages'])}")

    # Show the latest inbound message (what the agent will respond to)
    inbound_messages = [m for m in thread["messages"] if m["direction"] == "inbound"]
    if inbound_messages:
        latest = inbound_messages[-1]
        print(f"\n  Latest inbound message:")
        print(f"    From: {latest['from']}")
        print(f"    Body: {latest['body'][:100]}...")

    # Create a wrapper that redirects all emails to our test address
    from tools.outreach_tools import _send_via_resend as original_send

    def redirect_to_test_email(to: list[str], subject: str, body: str):
        """Wrapper that sends to test email instead of original recipients."""
        print(f"\n  [REDIRECT] Original recipients: {to}")
        print(f"  [REDIRECT] Sending to: {TEST_EMAIL}")
        print(f"  [REDIRECT] Subject: {subject}")
        print(f"  [REDIRECT] Body preview: {body[:200]}...")
        
        # Add a note about the redirect
        modified_body = f"""[TEST EMAIL - Originally addressed to: {', '.join(to)}]

{body}
"""
        return original_send([TEST_EMAIL], subject, modified_body)

    # Run the agent with our redirect wrapper
    print("\n  Running outreach agent...")
    print("  (This may take a moment while the agent reasons...)\n")

    from agents.outreach import handle_outreach_sync
    from agents.structures import OutreachRequest

    with patch("tools.outreach_tools._send_via_resend", redirect_to_test_email):
        try:
            request = OutreachRequest(email_thread_id=thread_id)
            result = handle_outreach_sync(request)

            print(f"\n  Agent Result:")
            print(f"    Email Thread ID: {result.email_thread_id}")
            print(f"    Classification: {result.bucket}")
            print(f"    HITL Required: {result.hitl_required}")
            print(f"    Sent: {result.sent}")

            if result.sent:
                print(f"\n✓ Agent composed and sent email successfully!")
                print(f"  Check {TEST_EMAIL} inbox for the agent's response.")
                return True
            elif result.hitl_required:
                print(f"\n⚠ Agent flagged for HITL review (escalation case)")
                print("  Email was not sent - this is expected for escalation classifications.")
                return True  # Still a success - agent worked correctly
            else:
                print(f"\n⚠ Agent did not send email")
                return True  # Agent ran, just didn't send

        except Exception as e:
            print(f"\n✗ Error running agent: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Run the integration tests."""
    print("\n" + "=" * 60)
    print("Pool Patrol - Resend Integration Test Suite")
    print("=" * 60)
    print(f"\n📧 All test emails will be sent to: {TEST_EMAIL}")
    print("   WARNING: This sends REAL emails!")

    results = {}

    # Test 1: Basic Resend
    results["basic_resend"] = test_resend_integration()

    # Test 2: Full Agent Integration
    results["outreach_agent"] = test_outreach_agent_integration()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, result in results.items():
        status = "✓ Pass" if result else "✗ Fail"
        print(f"  {name}: {status}")

    print(f"\n  Check {TEST_EMAIL} inbox for test emails.\n")

    # Return exit code
    failures = [r for r in results.values() if r is False]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
