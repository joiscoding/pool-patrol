#!/usr/bin/env python3
"""Run LangSmith evaluation for the Outreach Agent.

Evaluators:
===========

1. HEURISTIC EVALUATORS (exact match):
   - hitl_match: Does hitl_required match expected? (escalation → True)
   - bucket_match: Does bucket classification match expected?

2. LLM-AS-JUDGE EVALUATORS:
   - answer_relevance: Is the agent's response relevant to the user's message?
   - toxicity: Does the agent's response contain toxic/inappropriate content?

Usage:
    poetry run python -m eval.run_outreach_eval

Requirements:
    - LANGSMITH_API_KEY environment variable
    - OPENAI_API_KEY environment variable
    - Dataset created via: poetry run python packages/data/create_outreach_small.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages"))

from dotenv import load_dotenv
from langsmith import Client
from langsmith.evaluation import evaluate
from openevals.llm import create_llm_as_judge
from openevals.prompts import ANSWER_RELEVANCE_PROMPT
from prompts.eval_prompts import TOXICITY_EVAL_PROMPT

load_dotenv(PROJECT_ROOT / ".env", override=True)

from agents.outreach import handle_outreach_sync
from agents.structures import OutreachRequest
from tools.outreach_tools import get_email_thread


# =============================================================================
# Configuration
# =============================================================================

DATASET_NAME = "outreach-agent-eval-small"
EXPERIMENT_PREFIX = "outreach-agent"


# =============================================================================
# Helper Functions
# =============================================================================


def format_thread_for_eval(thread: dict) -> str:
    """Format email thread as readable text for the evaluator."""
    if "error" in thread:
        return f"Error: {thread['error']}"
    
    lines = [
        f"Thread: {thread['thread_id']}",
        f"Subject: {thread.get('subject', 'N/A')}",
        f"Vanpool: {thread.get('vanpool_id', 'N/A')}",
        "",
        "Messages:",
    ]
    
    for msg in thread.get("messages", []):
        direction = msg.get("direction", "unknown").upper()
        sender = msg.get("from", "unknown")
        body = msg.get("body", "")
        lines.append(f"\n[{direction}] From: {sender}")
        lines.append(body)
    
    return "\n".join(lines)


# =============================================================================
# Target Function
# =============================================================================


def target_function(inputs: dict) -> dict:
    """Run the Outreach Agent on an email thread.
    
    Args:
        inputs: Dict with "email_thread_id" and optional "context"
        
    Returns:
        Dict with bucket, hitl_required, sent, user message, and agent response
    """
    thread_id = inputs["email_thread_id"]
    
    # Fetch the email thread content BEFORE agent runs
    thread_before = get_email_thread.invoke({"thread_id": thread_id})
    
    # Get the last inbound message (user's message)
    user_message = ""
    messages_before = thread_before.get("messages", [])
    inbound_msgs = [m for m in messages_before if m.get("direction") == "inbound"]
    if inbound_msgs:
        user_message = inbound_msgs[-1].get("body", "")
    
    # Run the agent
    request = OutreachRequest(
        email_thread_id=thread_id,
        context=inputs.get("context"),
    )
    result = handle_outreach_sync(request)
    
    # Fetch the thread AFTER agent runs to get the agent's response
    thread_after = get_email_thread.invoke({"thread_id": thread_id})
    
    # Get the agent's response (last outbound message)
    agent_response = ""
    messages_after = thread_after.get("messages", [])
    outbound_msgs = [m for m in messages_after if m.get("direction") == "outbound"]
    if outbound_msgs:
        agent_response = outbound_msgs[-1].get("body", "")
    
    return {
        "email_thread_id": result.email_thread_id,
        "bucket": result.bucket,
        "hitl_required": result.hitl_required,
        "sent": result.sent,
        # For evaluators
        "user_message": user_message,
        "agent_response": agent_response,
    }


# =============================================================================
# Heuristic Evaluators
# =============================================================================


def hitl_match(outputs: dict, reference_outputs: dict) -> dict:
    """Check if hitl_required matches expected.
    
    Critical for ensuring escalations trigger human review.
    """
    predicted = outputs.get("hitl_required")
    expected = reference_outputs.get("hitl_required")
    
    return {
        "key": "hitl_match",
        "score": predicted == expected,
    }


def bucket_match(outputs: dict, reference_outputs: dict) -> dict:
    """Check if bucket classification matches expected.
    
    Verifies intent classification: acknowledgment, question, update, escalation.
    """
    predicted = outputs.get("bucket")
    expected = reference_outputs.get("bucket")
    
    return {
        "key": "bucket_match",
        "score": predicted == expected,
    }


# =============================================================================
# LLM-as-Judge Evaluators
# =============================================================================

# Base evaluator using openevals ANSWER_RELEVANCE_PROMPT
_answer_relevance_judge = create_llm_as_judge(
    prompt=ANSWER_RELEVANCE_PROMPT,
    feedback_key="answer_relevance",
    model="openai:gpt-4.1",
)


def answer_relevance_evaluator(inputs: dict, outputs: dict) -> dict:
    """Custom evaluator that checks if agent's email response is relevant to the user's message.
    
    Uses openevals ANSWER_RELEVANCE_PROMPT with:
    - inputs: The last inbound message from the employee
    - outputs: The agent's drafted email response
    """
    # Get the user's message and agent's response from outputs
    user_message = outputs.get("user_message", "")
    agent_response = outputs.get("agent_response", "")
    
    # If no agent response (e.g., HITL case where email wasn't sent), skip
    if not agent_response:
        return {
            "key": "answer_relevance",
            "score": True,
            "comment": "No email sent (HITL case) - skipping relevance check",
        }
    
    # Call the openevals judge with user's message as input, agent's email as output
    return _answer_relevance_judge(
        inputs=user_message,
        outputs=agent_response,
    )


# Toxicity evaluator using custom prompt
_toxicity_judge = create_llm_as_judge(
    prompt=TOXICITY_EVAL_PROMPT,
    feedback_key="toxicity",
    model="openai:gpt-4.1",
)


def non_toxic_evaluator(inputs: dict, outputs: dict) -> dict:
    """Check if agent's email response is professional and non-toxic.
    
    Uses TOXICITY_EVAL_PROMPT and inverts the score:
    - Prompt returns true if toxic, false if not toxic
    - We invert so LangSmith shows: Non-toxic → 1 (PASS), Toxic → 0 (FAIL)
    """
    agent_response = outputs.get("agent_response", "")
    
    # If no agent response (e.g., HITL case where email wasn't sent), skip
    if not agent_response:
        return {
            "key": "non_toxic",
            "score": True,
            "comment": "No email sent (HITL case) - skipping toxicity check",
        }
    
    # Call the judge (only needs agent response)
    result = _toxicity_judge(
        outputs=agent_response,
    )
    
    # Invert: prompt returns True if toxic, we want True if non-toxic
    return {
        "key": "non_toxic",
        "score": not result.get("score", False),
        "comment": result.get("comment", ""),
    }


# =============================================================================
# Main Evaluation Runner
# =============================================================================


def run_evaluation(
    dataset_name: str = DATASET_NAME,
    experiment_prefix: str = EXPERIMENT_PREFIX,
    max_concurrency: int = 4,
):
    """Run the evaluation experiment on LangSmith."""
    print("=" * 60)
    print("Pool Patrol - Outreach Agent Evaluation")
    print("=" * 60)
    
    if not os.environ.get("LANGSMITH_API_KEY"):
        raise ValueError("LANGSMITH_API_KEY not set")
    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not set")
    
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", "pool-patrol-eval")
    
    client = Client()
    datasets = list(client.list_datasets(dataset_name=dataset_name))
    if not datasets:
        raise ValueError(f"Dataset '{dataset_name}' not found. Run create_outreach_small.py first.")
    
    dataset = datasets[0]
    example_count = len(list(client.list_examples(dataset_id=dataset.id)))
    
    print(f"\nDataset: {dataset_name}")
    print(f"Examples: {example_count}")
    print(f"Evaluators: hitl_match, bucket_match, answer_relevance, toxicity (LLM-as-judge)")
    
    print("\n" + "-" * 60)
    print("Running evaluation...")
    print("-" * 60 + "\n")
    
    results = evaluate(
        target_function,
        data=dataset_name,
        evaluators=[hitl_match, bucket_match, non_toxic_evaluator],
        experiment_prefix=experiment_prefix,
        max_concurrency=max_concurrency,
    )
    
    print("\n" + "=" * 60)
    print("Evaluation Complete!")
    print("=" * 60)
    print(f"\nView results at: https://smith.langchain.com/")
    
    return results


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Outreach Agent evaluation")
    parser.add_argument("--dataset", default=DATASET_NAME)
    parser.add_argument("--prefix", default=EXPERIMENT_PREFIX)
    parser.add_argument("--concurrency", type=int, default=4)
    
    args = parser.parse_args()
    
    try:
        run_evaluation(
            dataset_name=args.dataset,
            experiment_prefix=args.prefix,
            max_concurrency=args.concurrency,
        )
        return 0
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
