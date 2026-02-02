"""Tools for email operations in the Outreach Agent.

This module provides tools for:
- Fetching email threads from the database
- Classifying inbound replies using LLM
- Sending emails via Resend API (with and without HITL review)
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any

import resend
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from core.database import get_session
from core.db_models import (
    EmailThread,
    Employee,
    Message,
    MessageDirection,
    MessageStatusEnum,
    Rider,
    to_json,
)
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
    """Fetch email thread, all messages, and vanpool rider emails by thread_id.

    Use this tool to retrieve the full conversation history for a case.
    Also returns rider_emails so you know who to send emails to.

    Args:
        thread_id: The thread ID (e.g., "THREAD-001")

    Returns:
        A dictionary with:
        - thread_id: The thread ID
        - case_id: Associated case ID
        - vanpool_id: Associated vanpool ID
        - subject: Email subject line
        - status: Thread status (active, closed, archived)
        - rider_emails: List of email addresses for vanpool riders (use these as recipients)
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

        result = thread.to_dict(include_messages=True)
        
        # Get rider emails for this vanpool
        riders = (
            session.query(Rider)
            .filter(Rider.vanpool_id == thread.vanpool_id)
            .all()
        )
        
        if riders:
            employee_ids = [r.employee_id for r in riders]
            employees = (
                session.query(Employee)
                .filter(Employee.employee_id.in_(employee_ids))
                .all()
            )
            result["rider_emails"] = [emp.email for emp in employees if emp.email]
        else:
            result["rider_emails"] = []
        
        return result


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


def _save_message_to_db(thread_id: str, to: list[str], body: str, sent: bool) -> str:
    """Save the sent message to the database.
    
    Returns:
        The generated message_id
    """
    message_id = f"MSG-{uuid.uuid4().hex[:8].upper()}"
    
    with get_session() as session:
        new_message = Message(
            message_id=message_id,
            thread_id=thread_id,
            from_email=FROM_EMAIL,
            to_emails=to_json(to),
            sent_at=datetime.now(),  # Use local time (PrismaDateTime expects local, not UTC)
            body=body,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatusEnum.SENT if sent else MessageStatusEnum.DRAFT,
        )
        session.add(new_message)
        session.commit()
    
    return message_id


@tool
def send_email(thread_id: str, to: list[str], subject: str, body: str) -> dict:
    """Send email via Resend API and save to database.

    Use this tool for initial outreach OR when classify_reply returns: 
    acknowledgment, question, or update.

    This tool sends the email immediately without human review.

    Args:
        thread_id: The thread ID to associate this message with
        to: List of recipient email addresses
        subject: Email subject line
        body: Email body text

    Returns:
        A dictionary with:
        - message_id: The database message ID
        - resend_id: The Resend API message ID if successful
        - sent: True if email was sent
        - error: Error message if failed
    """
    # Send the email
    send_result = _send_via_resend(to, subject, body)
    
    # Save to database
    message_id = _save_message_to_db(
        thread_id=thread_id,
        to=to,
        body=body,
        sent=send_result.get("sent", False),
    )
    
    return {
        "message_id": message_id,
        "resend_id": send_result.get("id"),
        "sent": send_result.get("sent", False),
        "error": send_result.get("error"),
    }


@tool
def send_email_for_review(thread_id: str, to: list[str], subject: str, body: str) -> dict:
    """Send email via Resend API after human review and save to database.

    Use this tool when classify_reply returns: escalation.

    This tool will trigger HITL middleware - human will be able to:
    - Approve: Send email as drafted
    - Edit: Modify content before sending
    - Reject: Cancel sending

    Args:
        thread_id: The thread ID to associate this message with
        to: List of recipient email addresses
        subject: Email subject line
        body: Email body text (draft for human review)

    Returns:
        A dictionary with:
        - message_id: The database message ID
        - resend_id: The Resend API message ID if approved and sent
        - sent: True if email was sent (after approval)
        - error: Error message if failed or rejected
    """
    # The actual sending happens here, but the HumanInTheLoopMiddleware
    # will intercept this tool call and pause for human approval
    send_result = _send_via_resend(to, subject, body)
    
    # Save to database
    message_id = _save_message_to_db(
        thread_id=thread_id,
        to=to,
        body=body,
        sent=send_result.get("sent", False),
    )
    
    return {
        "message_id": message_id,
        "resend_id": send_result.get("id"),
        "sent": send_result.get("sent", False),
        "error": send_result.get("error"),
    }
