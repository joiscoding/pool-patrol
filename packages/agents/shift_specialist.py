"""Shift Specialist Agent - Validates employee shifts against vanpool schedules.

This agent verifies that employees assigned to a vanpool have compatible
work schedules. For example, a day shift vanpool should have day shift workers.

The agent:
1. Fetches the vanpool roster to get all riders
2. For each rider, fetches their shift schedule
3. Determines the expected shift type for the vanpool
4. Identifies any employees with mismatched shifts
5. Returns a structured verdict with evidence
"""

import os
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from agents.state import ShiftVerificationResult
from prompts.shift_specialist import SHIFT_SPECIALIST_PROMPT
from tools.roster import get_vanpool_roster
from tools.shifts import get_employee_shifts


# =============================================================================
# LangSmith Tracing Configuration
# =============================================================================

def configure_langsmith():
    """Configure LangSmith tracing if API key is available.
    
    Set these environment variables to enable tracing:
        LANGSMITH_TRACING=true
        LANGSMITH_API_KEY=your-api-key
        LANGSMITH_PROJECT=pool-patrol
    """
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
TOOLS = [get_vanpool_roster, get_employee_shifts]


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
    
    # Create the agent with tools and system prompt
    agent = create_react_agent(
        model=model,
        tools=TOOLS,
        prompt=SHIFT_SPECIALIST_PROMPT,
    )
    
    return agent


# =============================================================================
# Result Parsing
# =============================================================================


def parse_verification_result(content: str) -> ShiftVerificationResult:
    """Parse the agent's text response into a structured result.
    
    Expected format:
        VERDICT: pass/fail
        CONFIDENCE: 1-5
        REASONING: ...
        EVIDENCE:
        - item 1
        - item 2
    """
    lines = content.strip().split("\n")
    
    verdict = "pass"
    confidence = 3
    reasoning = ""
    evidence = []
    
    current_section = None
    reasoning_lines = []
    evidence_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        line_upper = line_stripped.upper()
        
        if line_upper.startswith("VERDICT:"):
            verdict_text = line_stripped.split(":", 1)[1].strip().lower()
            verdict = "fail" if "fail" in verdict_text else "pass"
            current_section = "verdict"
        elif line_upper.startswith("CONFIDENCE:"):
            try:
                conf_text = line_stripped.split(":", 1)[1].strip()
                # Handle "4/5" or "4" formats
                conf_num = conf_text.split("/")[0].strip()
                confidence = int(conf_num)
                confidence = max(1, min(5, confidence))
            except (ValueError, IndexError):
                confidence = 3
            current_section = "confidence"
        elif line_upper.startswith("REASONING:"):
            reasoning_text = line_stripped.split(":", 1)[1].strip()
            if reasoning_text:
                reasoning_lines.append(reasoning_text)
            current_section = "reasoning"
        elif line_upper.startswith("EVIDENCE:"):
            current_section = "evidence"
        elif current_section == "reasoning" and line_stripped:
            reasoning_lines.append(line_stripped)
        elif current_section == "evidence" and line_stripped:
            # Parse evidence items (starting with - or *)
            if line_stripped.startswith(("-", "*", "•")):
                evidence_text = line_stripped[1:].strip()
                evidence_lines.append(evidence_text)
            elif evidence_lines:  # Continuation of previous item
                evidence_lines[-1] += " " + line_stripped
    
    reasoning = " ".join(reasoning_lines)
    
    # Convert evidence lines to structured format
    evidence = [{"type": "observation", "data": {"description": e}} for e in evidence_lines]
    
    return ShiftVerificationResult(
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        evidence=evidence,
    )


# =============================================================================
# Convenience Functions
# =============================================================================


async def verify_vanpool_shifts(vanpool_id: str) -> ShiftVerificationResult:
    """Verify shift compatibility for a vanpool.
    
    This is the main entry point for the Shift Specialist.
    
    Args:
        vanpool_id: The vanpool ID to verify (e.g., "VP-101")
        
    Returns:
        ShiftVerificationResult with verdict, confidence, reasoning, and evidence
    """
    # Create the agent
    agent = create_shift_specialist()
    
    # Run the agent
    result = await agent.ainvoke({
        "messages": [
            HumanMessage(content=f"Verify shift compatibility for vanpool {vanpool_id}")
        ]
    })
    
    # Parse the final message into structured result
    final_message = result["messages"][-1]
    content = final_message.content if hasattr(final_message, "content") else str(final_message)
    
    return parse_verification_result(content)


def verify_vanpool_shifts_sync(vanpool_id: str) -> ShiftVerificationResult:
    """Synchronous version of verify_vanpool_shifts."""
    # Create the agent
    agent = create_shift_specialist()
    
    # Run the agent
    result = agent.invoke({
        "messages": [
            HumanMessage(content=f"Verify shift compatibility for vanpool {vanpool_id}")
        ]
    })
    
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
