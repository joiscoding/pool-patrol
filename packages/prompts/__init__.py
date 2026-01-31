"""Pool Patrol Prompts - System prompts and email templates for agents."""

from .shift_specialist_prompts import SHIFT_SPECIALIST_PROMPT
from .initial_outreach import (
    IssueType,
    get_subject,
    get_initial_outreach_email,
    render_template,
    TEMPLATES,
)

__all__ = [
    "SHIFT_SPECIALIST_PROMPT",
    "IssueType",
    "get_subject",
    "get_initial_outreach_email",
    "render_template",
    "TEMPLATES",
]
