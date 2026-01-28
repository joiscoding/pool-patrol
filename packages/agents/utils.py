"""Shared utilities for agent output handling."""

from typing import Any, Type, TypeVar

from agents.state import VerificationResult

ResultT = TypeVar("ResultT", bound=VerificationResult)


def parse_legacy_verification_result(content: str, result_cls: Type[ResultT]) -> ResultT:
    """Parse a legacy text response into a structured result."""
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

    return result_cls(
        verdict=verdict,
        confidence=confidence,
        reasoning=reasoning,
        evidence=evidence,
    )
