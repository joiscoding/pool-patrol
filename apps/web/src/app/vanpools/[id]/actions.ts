'use server';

import { revalidatePath } from 'next/cache';

export interface AuditResult {
  success: boolean;
  vanpool_id?: string;
  case_id?: string | null;
  outcome?: string;
  reasoning?: string;
  outreach_summary?: string | null;
  hitl_required?: boolean;
  error?: string;
}

export interface UpdateDraftResult {
  success: boolean;
  message_id?: string;
  body?: string;
  error?: string;
}

export interface SendDraftResult {
  success: boolean;
  message_id?: string;
  sent?: boolean;
  error?: string;
}

export interface CancelVanpoolResult {
  success: boolean;
  cancelled?: boolean;
  vanpool_id?: string;
  error?: string;
}

/**
 * Triggers a full re-audit of a vanpool using the Case Manager agent.
 * 
 * This calls the FastAPI backend which runs:
 * 1. Verification specialists (shift, location)
 * 2. Case creation/updates if issues found
 * 3. Outreach handling (emails, reply processing)
 * 4. HITL flow for membership cancellation
 */
export async function auditVanpool(vanpoolId: string): Promise<AuditResult> {
  const apiUrl = process.env.POOL_PATROL_API_URL || 'http://localhost:8000';

  try {
    const response = await fetch(`${apiUrl}/api/vanpools/${vanpoolId}/audit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || `Audit failed with status ${response.status}`,
      };
    }

    const data = await response.json();

    return {
      success: true,
      vanpool_id: data.vanpool_id,
      case_id: data.case_id,
      outcome: data.outcome,
      reasoning: data.reasoning,
      outreach_summary: data.outreach_summary,
      hitl_required: data.hitl_required,
    };
  } catch (error) {
    console.error('Error auditing vanpool:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to connect to API',
    };
  }
}

/**
 * Updates a draft message's body content.
 */
export async function updateDraftMessage(
  messageId: string,
  body: string,
  vanpoolId: string
): Promise<UpdateDraftResult> {
  const apiUrl = process.env.POOL_PATROL_API_URL || 'http://localhost:8000';

  try {
    const response = await fetch(`${apiUrl}/api/emails/messages/${messageId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ body }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || `Update failed with status ${response.status}`,
      };
    }

    const data = await response.json();
    revalidatePath(`/vanpools/${vanpoolId}`);

    return {
      success: true,
      message_id: data.message_id,
      body: data.body,
    };
  } catch (error) {
    console.error('Error updating draft message:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to connect to API',
    };
  }
}

/**
 * Sends a draft message via the email API.
 */
export async function sendDraftMessage(
  messageId: string,
  vanpoolId: string
): Promise<SendDraftResult> {
  const apiUrl = process.env.POOL_PATROL_API_URL || 'http://localhost:8000';

  try {
    const response = await fetch(`${apiUrl}/api/emails/messages/${messageId}/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || `Send failed with status ${response.status}`,
      };
    }

    const data = await response.json();
    revalidatePath(`/vanpools/${vanpoolId}`);

    return {
      success: true,
      message_id: data.message_id,
      sent: data.sent,
      error: data.error,
    };
  } catch (error) {
    console.error('Error sending draft message:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to connect to API',
    };
  }
}

/**
 * Cancels an entire vanpool service.
 */
export async function cancelVanpool(
  caseId: string,
  vanpoolId: string
): Promise<CancelVanpoolResult> {
  const apiUrl = process.env.POOL_PATROL_API_URL || 'http://localhost:8000';

  try {
    const response = await fetch(`${apiUrl}/api/cases/${caseId}/cancel-vanpool`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        success: false,
        error: errorData.detail || `Cancellation failed with status ${response.status}`,
      };
    }

    const data = await response.json();
    revalidatePath(`/vanpools/${vanpoolId}`);
    revalidatePath('/');

    return {
      success: true,
      cancelled: data.cancelled,
      vanpool_id: data.vanpool_id,
    };
  } catch (error) {
    console.error('Error cancelling vanpool:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to connect to API',
    };
  }
}
