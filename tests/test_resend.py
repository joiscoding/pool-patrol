#!/usr/bin/env python3
"""Integration test for Resend email sending.

This script sends a REAL email via Resend to verify the integration is working.
Run from the project root:

    poetry run python tests/test_resend.py

Make sure you have:
1. Set RESEND_API_KEY in your .env file
2. Verified your sending domain in Resend dashboard

WARNING: This sends actual emails - use sparingly!
"""

import sys
from pathlib import Path

# Add packages to path for development
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(project_root / ".env", override=True)


def test_resend_integration():
    """Send a real test email via Resend."""
    print("\n" + "=" * 60)
    print("Resend Integration Test")
    print("=" * 60)

    from tools.outreach_tools import _send_via_resend, resend, FROM_EMAIL

    # Check API key is configured
    if not resend.api_key:
        print("\n✗ RESEND_API_KEY not configured in .env")
        return False

    print(f"\n✓ Resend API key configured")
    print(f"  From: {FROM_EMAIL}")

    # Send test email
    test_email = "josephyanginfo@gmail.com"
    print(f"\n  Sending test email to: {test_email}")

    result = _send_via_resend(
        to=[test_email],
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
        print(f"\n  Check {test_email} inbox to confirm delivery.")
        return True
    else:
        print(f"\n✗ Failed to send email")
        print(f"  Error: {result.get('error')}")
        return False


def main():
    """Run the integration test."""
    success = test_resend_integration()

    print("\n" + "=" * 60)
    print("Result:", "PASS" if success else "FAIL")
    print("=" * 60 + "\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
