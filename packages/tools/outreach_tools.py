"""Tools for email operations in the Outreach Agent.

This module provides tools for:
- Fetching email threads from the database
- Classifying inbound replies using LLM
- Sending emails via Resend API (with and without HITL review)
"""

import json
import os
from typing import Any

import resend
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from core.database import get_session
from core.db_models import EmailThread
from prompts.outreach_prompts import CLASSIFICATION_PROMPT


# Configure Resend API
resend.api_key = os.environ.get("RESEND_API_KEY", "")

# Email sender configuration
FROM_EMAIL = "Pool Patrol <contact@send.joyax.co>"


# =============================================================================
# Database Tools
# =============================================================================


@tool
def get_email_thread(thread_id: str) -> dict:
    """Fetch email thread and all messages by thread_id.

    Use this tool to retrieve the full conversation history for a case.

    Args:
        thread_id: The thread ID (e.g., "THREAD-001")

    Returns:
        A dictionary with:
        - thread_id: The thread ID
        - case_id: Associated case ID
        - vanpool_id: Associated vanpool ID
        - subject: Email subject line
        - status: Thread status (active, closed, archived)
        - messages: List of messages in chronological order, each with:
            - message_id: Unique message ID
            - from: Sender email
            - to: List of recipient emails
            - sent_at: Timestamp
            - body: Message content
            - direction: "inbound" or "outbound"
            - classification: Classification bucket if classified
        - error: Error message if thread not found
    """
    with get_session() as session:
        thread = (
            session.query(EmailThread)
            .filter(EmailThread.thread_id == thread_id)
            .first()
        )

        if thread is None:
            return {"error": f"Email thread {thread_id} not found"}

        return thread.to_dict(include_messages=True)


# =============================================================================
# Classification Tool
# =============================================================================


@tool
def classify_reply(message_body: str) -> dict:
    """Classify an inbound email reply into a bucket.

    Use this tool when you receive an inbound message that needs classification.

    Args:
        message_body: The body text of the email to classify

    Returns:
        A dictionary with:
        - bucket: Classification bucket (acknowledgment, question, update, escalation)
        - reasoning: Brief explanation of the classification
    """
    model = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0,
    )

    prompt = CLASSIFICATION_PROMPT.format(
        message_body=message_body,
    )

    response = model.invoke(prompt)
    content = response.content

    # Parse JSON response
    try:
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())
        return result
    except (json.JSONDecodeError, IndexError):
        return {
            "bucket": "escalation",
            "reasoning": f"Failed to parse classification response: {content[:200]}",
        }


# =============================================================================
# Email Sending Tools
# =============================================================================


def _send_via_resend(to: list[str], subject: str, body: str) -> dict[str, Any]:
    """Internal function to send email via Resend API."""
    if not resend.api_key:
        return {
            "error": "RESEND_API_KEY not configured",
            "sent": False,
        }

    try:
        result = resend.Emails.send({
            "from": FROM_EMAIL,
            "to": to,
            "subject": subject,
            "text": body,
        })
        return {
            "id": result.get("id"),
            "sent": True,
        }
    except Exception as e:
        return {
            "error": str(e),
            "sent": False,
        }


@tool
def send_email(to: list[str], subject: str, body: str) -> dict:
    """Send email via Resend API. Use for non-escalation classifications.

    Use this tool when classify_reply returns: acknowledgment, question, or update.

    This tool sends the email immediately without human review.

    Args:
        to: List of recipient email addresses
        subject: Email subject line
        body: Email body text

    Returns:
        A dictionary with:
        - id: The Resend message ID if successful
        - sent: True if email was sent
        - error: Error message if failed
    """
    return _send_via_resend(to, subject, body)


@tool
def send_email_for_review(to: list[str], subject: str, body: str) -> dict:
    """Send email via Resend API after human review. Use for escalation classifications.

    Use this tool when classify_reply returns: escalation.

    This tool will trigger HITL middleware - human will be able to:
    - Approve: Send email as drafted
    - Edit: Modify content before sending
    - Reject: Cancel sending

    Args:
        to: List of recipient email addresses
        subject: Email subject line
        body: Email body text (draft for human review)

    Returns:
        A dictionary with:
        - id: The Resend message ID if approved and sent
        - sent: True if email was sent (after approval)
        - error: Error message if failed or rejected
    """
    # The actual sending happens here, but the HumanInTheLoopMiddleware
    # will intercept this tool call and pause for human approval
    return _send_via_resend(to, subject, body)
