"""Initial outreach email templates for vanpool eligibility cases."""

from enum import Enum


class IssueType(Enum):
    """Types of issues that trigger outreach."""
    LOCATION = "location"
    SHIFT = "shift"
    BOTH = "both"


def get_subject(vanpool_id: str, issue_type: IssueType) -> str:
    """Generate email subject based on issue type."""
    if issue_type == IssueType.LOCATION:
        return f"Vanpool Eligibility Review - {vanpool_id} - Action Required"
    elif issue_type == IssueType.SHIFT:
        return f"Vanpool Schedule Review - {vanpool_id} - Action Required"
    else:  # BOTH
        return f"Vanpool Eligibility Review - {vanpool_id} - Action Required"


def get_initial_outreach_email(
    vanpool_id: str,
    issue_type: IssueType,
    location_details: str | None = None,
    shift_details: str | None = None,
) -> str:
    """
    Generate the initial outreach email body for a vanpool case.
    
    Args:
        vanpool_id: The vanpool identifier (e.g., "VP-101")
        issue_type: The type of issue (LOCATION, SHIFT, or BOTH)
        location_details: Optional details about the location mismatch
        shift_details: Optional details about the shift mismatch
    
    Returns:
        The formatted email body
    """
    
    # Opening
    body = f"Dear {vanpool_id} Vanpool Members,\n\n"
    body += "As part of our routine vanpool program review, we are verifying the eligibility of all participants.\n\n"
    
    # Issue-specific content
    if issue_type == IssueType.LOCATION:
        body += "Our records indicate a potential discrepancy with one or more rider home addresses. "
        body += "The registered address may be outside the typical service area for this vanpool route.\n\n"
        if location_details:
            body += f"{location_details}\n\n"
        body += "Please confirm your current home address by replying to this email.\n\n"
        
    elif issue_type == IssueType.SHIFT:
        body += "Our records indicate a potential mismatch between your work schedule and the vanpool operating hours. "
        body += "The vanpool departure/arrival times may not align with your assigned shift.\n\n"
        if shift_details:
            body += f"{shift_details}\n\n"
        body += "Please confirm your current work schedule by replying to this email.\n\n"
        
    else:  # BOTH
        body += "Our records indicate potential discrepancies that require verification:\n\n"
        body += "1. **Address Verification**: One or more rider addresses may be outside the typical service area for this route.\n"
        if location_details:
            body += f"   {location_details}\n"
        body += "\n"
        body += "2. **Schedule Alignment**: The vanpool operating hours may not align with your assigned work shift.\n"
        if shift_details:
            body += f"   {shift_details}\n"
        body += "\n"
        body += "Please confirm both your current home address and work schedule by replying to this email.\n\n"
    
    # Action items
    body += "**What we need from you:**\n"
    if issue_type == IssueType.LOCATION:
        body += "- Confirm your current home address\n"
        body += "- If your address has changed, please provide your updated information\n"
    elif issue_type == IssueType.SHIFT:
        body += "- Confirm your current work shift assignment\n"
        body += "- Let us know if the current vanpool schedule meets your commute needs\n"
    else:  # BOTH
        body += "- Confirm your current home address\n"
        body += "- Confirm your current work shift assignment\n"
        body += "- Let us know if your situation has changed\n"
    
    # Closing
    body += "\nPlease respond within 5 business days.\n\n"
    body += "Thank you for your cooperation.\n\n"
    body += "Pool Patrol Team"
    
    return body


# Pre-built templates for common scenarios
TEMPLATES = {
    "location_mismatch": {
        "subject": "Vanpool Eligibility Review - {vanpool_id} - Action Required",
        "body": """Dear {vanpool_id} Vanpool Members,

As part of our routine vanpool program review, we are verifying the eligibility of all participants.

Our records indicate a potential discrepancy with one or more rider home addresses. The registered address may be outside the typical service area for this vanpool route.

{location_details}

Please confirm your current home address by replying to this email.

**What we need from you:**
- Confirm your current home address
- If your address has changed, please provide your updated information

Please respond within 5 business days.

Thank you for your cooperation.

Pool Patrol Team"""
    },
    
    "shift_mismatch": {
        "subject": "Vanpool Schedule Review - {vanpool_id} - Action Required",
        "body": """Dear {vanpool_id} Vanpool Members,

As part of our routine vanpool program review, we are verifying the eligibility of all participants.

Our records indicate a potential mismatch between your work schedule and the vanpool operating hours. The vanpool departure/arrival times may not align with your assigned shift.

{shift_details}

Please confirm your current work schedule by replying to this email.

**What we need from you:**
- Confirm your current work shift assignment
- Let us know if the current vanpool schedule meets your commute needs

Please respond within 5 business days.

Thank you for your cooperation.

Pool Patrol Team"""
    },
    
    "both_mismatch": {
        "subject": "Vanpool Eligibility Review - {vanpool_id} - Action Required",
        "body": """Dear {vanpool_id} Vanpool Members,

As part of our routine vanpool program review, we are verifying the eligibility of all participants.

Our records indicate potential discrepancies that require verification:

1. **Address Verification**: One or more rider addresses may be outside the typical service area for this route.
   {location_details}

2. **Schedule Alignment**: The vanpool operating hours may not align with your assigned work shift.
   {shift_details}

Please confirm both your current home address and work schedule by replying to this email.

**What we need from you:**
- Confirm your current home address
- Confirm your current work shift assignment
- Let us know if your situation has changed

Please respond within 5 business days.

Thank you for your cooperation.

Pool Patrol Team"""
    }
}


def render_template(
    template_key: str,
    vanpool_id: str,
    location_details: str = "",
    shift_details: str = "",
) -> dict[str, str]:
    """
    Render an email template with the provided variables.
    
    Args:
        template_key: One of "location_mismatch", "shift_mismatch", or "both_mismatch"
        vanpool_id: The vanpool identifier
        location_details: Details about the location issue (optional)
        shift_details: Details about the shift issue (optional)
    
    Returns:
        Dict with "subject" and "body" keys
    """
    template = TEMPLATES.get(template_key)
    if not template:
        raise ValueError(f"Unknown template: {template_key}")
    
    return {
        "subject": template["subject"].format(vanpool_id=vanpool_id),
        "body": template["body"].format(
            vanpool_id=vanpool_id,
            location_details=location_details,
            shift_details=shift_details,
        ).strip()
    }
