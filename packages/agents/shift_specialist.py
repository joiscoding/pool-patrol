"""Shift Specialist Agent - Validates employee shift compatibility for carpooling.

This agent verifies that a group of employees have compatible work schedules
for carpooling together. All employees should work the same shift type.

The agent:
1. Takes a list of employee IDs as input
2. Fetches each employee's shift schedule
3. Determines if all employees work the same shift type
4. Identifies any employees with mismatched shifts
5. Returns a structured verdict with evidence
"""

import os
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents.state import ShiftVerificationResult
from agents.utils import parse_legacy_verification_result
from prompts.shift_specialist import SHIFT_SPECIALIST_PROMPT, SHIFT_SPECIALIST_PROMPT_VERSION
from tools.shifts import get_employee_shifts


# =============================================================================
# LangSmith Tracing Configuration
# =============================================================================

def configure_langsmith():
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
TOOLS = [get_employee_shifts]
OUTPUT_PARSER = PydanticOutputParser(pydantic_object=ShiftVerificationResult)


def get_model():
    """Get the LLM model for the agent."""
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0,
    )


def create_shift_specialist():
    """Create the Shift Specialist agent using LangGraph's create_react_agent.
    
    This creates a ReAct-style agent that can use tools to gather information
    and reason about shift compatibility.
    """
    model = get_model()
    
    # Inject structured output instructions into the prompt
    structured_prompt = (
        SHIFT_SPECIALIST_PROMPT
        + "\n\n"
        + OUTPUT_PARSER.get_format_instructions()
    )

    # Create the agent with tools and system prompt
    agent = create_react_agent(
        model=model,
        tools=TOOLS,
        prompt=structured_prompt,
    )
    
    return agent


# =============================================================================
# Result Parsing
# =============================================================================


def parse_verification_result(content: str) -> ShiftVerificationResult:
    """Parse the agent's response into a structured result."""
    try:
        return OUTPUT_PARSER.parse(content)
    except Exception:
        return parse_legacy_verification_result(content, ShiftVerificationResult)


def _build_trace_config(employee_ids: list[str]) -> dict[str, Any]:
    """Build LangSmith trace metadata and tags for this run."""
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
    return {
        "run_name": "shift_specialist",
        "tags": ["agent:shift_specialist", "component:verification"],
        "metadata": {
            "agent": "shift_specialist",
            "employee_ids": employee_ids,
            "employee_count": len(employee_ids),
            "prompt_version": SHIFT_SPECIALIST_PROMPT_VERSION,
            "model": model_name,
        },
    }


# =============================================================================
# Convenience Functions
# =============================================================================


async def verify_employee_shifts(employee_ids: list[str]) -> ShiftVerificationResult:
    """Verify shift compatibility for a group of employees.
    
    This is the main entry point for the Shift Specialist.
    
    Args:
        employee_ids: List of employee IDs to verify (e.g., ["EMP-1001", "EMP-1002"])
        
    Returns:
        ShiftVerificationResult with verdict, confidence, reasoning, and evidence
    """
    # Handle empty list edge case
    if not employee_ids:
        return ShiftVerificationResult(
            verdict="fail",
            confidence=5,
            reasoning="No employees provided. Cannot verify shift compatibility with an empty list.",
            evidence=[],
        )
    
    # Create the agent
    agent = create_shift_specialist()
    
    # Build the message for the agent
    employee_list = ", ".join(employee_ids)
    message = f"Verify shift compatibility for the following employees: {employee_list}"
    
    # Run the agent
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config=_build_trace_config(employee_ids),
    )
    
    # Parse the final message into structured result
    final_message = result["messages"][-1]
    content = final_message.content if hasattr(final_message, "content") else str(final_message)
    
    return parse_verification_result(content)


def verify_employee_shifts_sync(employee_ids: list[str]) -> ShiftVerificationResult:
    """Synchronous version of verify_employee_shifts."""
    # Handle empty list edge case
    if not employee_ids:
        return ShiftVerificationResult(
            verdict="fail",
            confidence=5,
            reasoning="No employees provided. Cannot verify shift compatibility with an empty list.",
            evidence=[],
        )
    
    # Create the agent
    agent = create_shift_specialist()
    
    # Build the message for the agent
    employee_list = ", ".join(employee_ids)
    message = f"Verify shift compatibility for the following employees: {employee_list}"
    
    # Run the agent
    result = agent.invoke(
        {"messages": [HumanMessage(content=message)]},
        config=_build_trace_config(employee_ids),
    )
    
    # Parse the final message into structured result
    final_message = result["messages"][-1]
    content = final_message.content if hasattr(final_message, "content") else str(final_message)
    
    return parse_verification_result(content)


# For backward compatibility
def compile_shift_specialist():
    """Compile the Shift Specialist agent (for backward compatibility)."""
    return create_shift_specialist()


def create_shift_specialist_graph():
    """Create the Shift Specialist agent graph (for backward compatibility)."""
    return create_shift_specialist()
