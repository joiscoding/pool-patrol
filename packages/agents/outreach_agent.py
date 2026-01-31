"""Outreach Agent - Handles email communication with vanpool riders.

This agent is responsible for:
1. Fetching and reviewing email conversation history
2. Classifying inbound replies into appropriate buckets
3. Sending appropriate responses (with HITL for disputes/unknown)

The agent uses HumanInTheLoopMiddleware to pause for human review
when sending emails for dispute or unknown classifications.
"""

import os
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from agents.structures import OutreachResult
from agents.utils import parse_legacy_verification_result
from prompts.outreach import OUTREACH_AGENT_PROMPT, OUTREACH_AGENT_PROMPT_VERSION
from tools.outreach import (
    get_email_thread,
    get_email_thread_by_case,
    classify_reply,
    send_email,
    send_email_for_review,
)


# =============================================================================
# LangSmith Tracing Configuration
# =============================================================================


def configure_langsmith():
    """Configure LangSmith tracing if API key is available."""
    if os.environ.get("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGSMITH_PROJECT", "pool-patrol")
        return True
    return False


# Auto-configure on import
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

    # Inject structured output instructions into the prompt
    structured_prompt = (
        OUTREACH_AGENT_PROMPT
        + "\n\n"
        + OUTPUT_PARSER.get_format_instructions()
    )

    # Create the agent with HITL middleware
    agent = create_agent(
        model=model,
        tools=TOOLS,
        prompt=structured_prompt,
        checkpointer=InMemorySaver(),
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "send_email_for_review": {
                        "allowed_decisions": ["approve", "edit", "reject"],
                    },
                },
            )
        ],
    )

    return agent


# =============================================================================
# Result Parsing
# =============================================================================


def parse_outreach_result(content: str) -> OutreachResult:
    """Parse the agent's response into a structured result."""
    try:
        return OUTPUT_PARSER.parse(content)
    except Exception:
        return parse_legacy_verification_result(content, OutreachResult)


def _build_trace_config(case_id: str, thread_id: str | None = None) -> dict[str, Any]:
    """Build LangSmith trace metadata and tags for this run."""
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    return {
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
        config=_build_trace_config(case_id, thread_id),
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
        config=_build_trace_config(case_id, thread_id),
    )

    # Parse the final message into structured result
    final_message = result["messages"][-1]
    content = final_message.content if hasattr(final_message, "content") else str(final_message)

    return parse_outreach_result(content)


