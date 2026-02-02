"""Outreach Agent - Handles email communication with vanpool riders.

This agent is responsible for:
1. Reviewing preloaded email conversation history
2. Classifying inbound replies into appropriate buckets
3. Sending appropriate responses (with HITL for escalations)

The agent uses HumanInTheLoopMiddleware to pause for human review
when sending emails for escalation classifications.
"""

import json
import os
import uuid
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langsmith import traceable

from agents.structures import OutreachRequest, OutreachResult
from agents.utils import configure_langsmith
from prompts.outreach_prompts import OUTREACH_AGENT_PROMPT, OUTREACH_AGENT_PROMPT_VERSION
from tools.outreach_tools import (
    get_email_thread,  # Used for preloading only, not as agent tool
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
# Note: get_email_thread is preloaded, not a tool
TOOLS = [
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
    when calling send_email_for_review (for escalation classifications).

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
        if "email_thread_id" in content:
            return OutreachResult.model_validate(content)
        # Agent returned wrong schema (VerificationResult) - create default
        return OutreachResult(
            email_thread_id="unknown",
            bucket="escalation",
            hitl_required=True,
            sent=False,
        )
    
    # Try parsing as JSON first (from response_format)
    try:
        import json
        data = json.loads(content)
        if "email_thread_id" in data:
            return OutreachResult.model_validate(data)
        # Wrong schema in JSON
        return OutreachResult(
            email_thread_id="unknown",
            bucket="escalation", 
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
            email_thread_id="unknown",
            bucket="escalation",
            hitl_required=True,
            sent=False,
        )


def _build_config(email_thread_id: str) -> dict[str, Any]:
    """Build config with thread ID for persistence and LangSmith tracing.
    
    Note: 'thread_id' in configurable is for LangGraph checkpointer (HITL resume).
    'email_thread_id' in metadata is the business ID from email_threads table.
    
    The run_name and tags are set on the @traceable decorator for the entry points.
    """
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    
    return {
        # Thread config required for checkpointer persistence (LangGraph concept)
        "configurable": {
            "thread_id": f"outreach-{email_thread_id}-{uuid.uuid4()}",
        },
        # LangSmith trace metadata (run_name and tags are on @traceable decorator)
        "metadata": {
            "agent": "outreach_agent",
            "email_thread_id": email_thread_id,
            "prompt_version": OUTREACH_AGENT_PROMPT_VERSION,
            "model": model_name,
        },
    }


# =============================================================================
# Entry Points
# =============================================================================


def _preload_thread_data(thread_id: str) -> dict | None:
    """Preload email thread data for the agent.
    
    Returns:
        Thread data dict or None if not found
    """
    # Call the underlying function (not the tool wrapper)
    return get_email_thread.func(thread_id=thread_id)


def _build_message(request: OutreachRequest, thread_data: dict) -> str:
    """Build the input message for the agent with preloaded thread data."""
    # Compact JSON for token efficiency
    thread_json = json.dumps(thread_data, separators=(",", ":"), default=str)
    
    message = f"""Handle outreach for email thread {request.email_thread_id}.

## Email Thread (preloaded)
{thread_json}

## Context from Case Manager
{request.context or "No additional context provided."}

Review the thread and take appropriate action.
"""
    return message


@traceable(
    run_type="chain",
    name="outreach_agent",
    tags=["agent:outreach", "component:communication"],
)
async def handle_outreach(request: OutreachRequest) -> OutreachResult:
    """Main entry point for the Outreach Agent.

    Called by Case Manager when there's activity on a thread that requires
    email communication.

    Args:
        request: OutreachRequest with email_thread_id and optional context

    Returns:
        OutreachResult with email_thread_id, message_id, bucket, hitl_required, sent
    """
    # Preload thread data
    thread_data = _preload_thread_data(request.email_thread_id)
    
    if thread_data is None or "error" in thread_data:
        return OutreachResult(
            email_thread_id=request.email_thread_id,
            bucket=None,
            hitl_required=False,
            sent=False,
        )
    
    agent = create_outreach_agent()

    # Run the agent with preloaded data
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=_build_message(request, thread_data))]},
        config=_build_config(request.email_thread_id),
    )

    # Parse the final message into structured result
    final_message = result["messages"][-1]
    content = final_message.content if hasattr(final_message, "content") else str(final_message)

    return parse_outreach_result(content)


@traceable(
    run_type="chain",
    name="outreach_agent",
    tags=["agent:outreach", "component:communication"],
)
def handle_outreach_sync(request: OutreachRequest) -> OutreachResult:
    """Synchronous version of handle_outreach."""
    # Preload thread data
    thread_data = _preload_thread_data(request.email_thread_id)
    
    if thread_data is None or "error" in thread_data:
        return OutreachResult(
            email_thread_id=request.email_thread_id,
            bucket=None,
            hitl_required=False,
            sent=False,
        )
    
    agent = create_outreach_agent()

    # Run the agent with preloaded data
    result = agent.invoke(
        {"messages": [HumanMessage(content=_build_message(request, thread_data))]},
        config=_build_config(request.email_thread_id),
    )

    # Parse the final message into structured result
    final_message = result["messages"][-1]
    content = final_message.content if hasattr(final_message, "content") else str(final_message)

    return parse_outreach_result(content)
