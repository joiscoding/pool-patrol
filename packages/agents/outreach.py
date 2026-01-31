"""Outreach Agent - Handles email communication with vanpool riders.

This agent is responsible for:
1. Fetching and reviewing email conversation history
2. Classifying inbound replies into appropriate buckets
3. Sending appropriate responses (with HITL for disputes/unknown)

The agent uses HumanInTheLoopMiddleware to pause for human review
when sending emails for dispute or unknown classifications.
"""

import os
import uuid
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from agents.structures import OutreachResult
from agents.utils import configure_langsmith
from prompts.outreach_prompts import OUTREACH_AGENT_PROMPT, OUTREACH_AGENT_PROMPT_VERSION
from tools.outreach_tools import (
    get_email_thread,
    get_email_thread_by_case,
    classify_reply,
    send_email,
    send_email_for_review,
)

# Auto-configure LangSmith on import
_langsmith_enabled = configure_langsmith()


# =============================================================================
# Agent Configuration
# =============================================================================

# Tools available to the agent
TOOLS = [
    get_email_thread,
    get_email_thread_by_case,
    classify_reply,
    send_email,
    send_email_for_review,
]

OUTPUT_PARSER = PydanticOutputParser(pydantic_object=OutreachResult)


def get_model():
    """Get the LLM model for the agent."""
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1"),
        temperature=0,
    )


def create_outreach_agent():
    """Create the Outreach Agent with HITL support.

    The agent uses HumanInTheLoopMiddleware to pause for human review
    when calling send_email_for_review (for dispute/unknown classifications).

    Returns:
        A LangGraph agent that can handle email outreach tasks.
    """
    model = get_model()

    # Create the agent with HITL middleware and enforced response schema
    agent = create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=OUTREACH_AGENT_PROMPT,
        checkpointer=InMemorySaver(),
        response_format=OutreachResult,  # Enforces deterministic JSON output
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "send_email_for_review": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                        "description": "Email send requires human approval",
                    },
                },
            )
        ],
    )

    return agent


# =============================================================================
# Result Parsing
# =============================================================================


def parse_outreach_result(content: str | dict) -> OutreachResult:
    """Parse the agent's response into a structured result.
    
    With response_format, the content may already be a dict or valid JSON.
    Falls back gracefully if the agent returns wrong schema.
    """
    # If already a dict (from structured output), try to validate
    if isinstance(content, dict):
        # Check if it looks like OutreachResult fields
        if "thread_id" in content:
            return OutreachResult.model_validate(content)
        # Agent returned wrong schema (VerificationResult) - create default
        return OutreachResult(
            thread_id="unknown",
            bucket="unknown",
            hitl_required=True,
            sent=False,
        )
    
    # Try parsing as JSON first (from response_format)
    try:
        import json
        data = json.loads(content)
        if "thread_id" in data:
            return OutreachResult.model_validate(data)
        # Wrong schema in JSON
        return OutreachResult(
            thread_id="unknown",
            bucket="unknown", 
            hitl_required=True,
            sent=False,
        )
    except (json.JSONDecodeError, ValueError):
        pass
    
    # Fallback to PydanticOutputParser for text format
    try:
        return OUTPUT_PARSER.parse(content)
    except Exception:
        # Last resort - return safe default
        return OutreachResult(
            thread_id="unknown",
            bucket="unknown",
            hitl_required=True,
            sent=False,
        )


def _build_config(case_id: str, thread_id: str | None = None) -> dict[str, Any]:
    """Build config with thread ID for persistence and LangSmith tracing."""
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    
    # Generate unique thread ID for checkpointer persistence
    persistence_thread_id = thread_id or f"case-{case_id}-{uuid.uuid4()}"
    
    return {
        # Thread config required for checkpointer persistence
        "configurable": {
            "thread_id": persistence_thread_id,
        },
        # LangSmith trace metadata
        "run_name": "outreach_agent",
        "tags": ["agent:outreach", "component:communication"],
        "metadata": {
            "agent": "outreach_agent",
            "case_id": case_id,
            "thread_id": thread_id,
            "prompt_version": OUTREACH_AGENT_PROMPT_VERSION,
            "model": model_name,
        },
    }


# =============================================================================
# Entry Points
# =============================================================================


async def handle_outreach(
    case_id: str,
    thread_id: str | None = None,
) -> OutreachResult:
    """Main entry point for the Outreach Agent.

    Called by Case Manager when there's activity on a case that requires
    email communication.

    Args:
        case_id: The case ID to handle
        thread_id: Optional thread ID if known

    Returns:
        OutreachResult with thread_id, message_id, bucket, hitl_required, sent
    """
    agent = create_outreach_agent()

    # Build the message for the agent
    if thread_id:
        message = f"Handle outreach for case {case_id}, thread {thread_id}."
    else:
        message = f"Handle outreach for case {case_id}."

    # Run the agent
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config=_build_config(case_id, thread_id),
    )

    # Parse the final message into structured result
    final_message = result["messages"][-1]
    content = final_message.content if hasattr(final_message, "content") else str(final_message)

    return parse_outreach_result(content)


def handle_outreach_sync(
    case_id: str,
    thread_id: str | None = None,
) -> OutreachResult:
    """Synchronous version of handle_outreach."""
    agent = create_outreach_agent()

    # Build the message for the agent
    if thread_id:
        message = f"Handle outreach for case {case_id}, thread {thread_id}."
    else:
        message = f"Handle outreach for case {case_id}."

    # Run the agent
    result = agent.invoke(
        {"messages": [HumanMessage(content=message)]},
        config=_build_config(case_id, thread_id),
    )

    # Parse the final message into structured result
    final_message = result["messages"][-1]
    content = final_message.content if hasattr(final_message, "content") else str(final_message)

    return parse_outreach_result(content)


