'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { updateDraftMessage, sendDraftMessage } from '@/app/vanpools/[id]/actions';

interface DraftMessageEditorProps {
  messageId: string;
  vanpoolId: string;
  initialBody: string;
  fromEmail: string;
  toEmails: string[];
  sentAt: Date;
}

export function DraftMessageEditor({
  messageId,
  vanpoolId,
  initialBody,
  fromEmail,
  toEmails,
  sentAt,
}: DraftMessageEditorProps) {
  const [body, setBody] = useState(initialBody);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, startSaving] = useTransition();
  const [isSending, startSending] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const router = useRouter();

  const handleSave = () => {
    setError(null);
    startSaving(async () => {
      const result = await updateDraftMessage(messageId, body, vanpoolId);
      if (result.success) {
        setIsEditing(false);
        setSuccess('Draft saved');
        setTimeout(() => setSuccess(null), 2000);
      } else {
        setError(result.error || 'Failed to save draft');
      }
    });
  };

  const handleSend = () => {
    setError(null);
    startSending(async () => {
      // Save any pending changes first
      if (body !== initialBody) {
        const saveResult = await updateDraftMessage(messageId, body, vanpoolId);
        if (!saveResult.success) {
          setError(saveResult.error || 'Failed to save draft before sending');
          return;
        }
      }

      const result = await sendDraftMessage(messageId, vanpoolId);
      if (result.success && result.sent) {
        setSuccess('Email sent successfully');
        router.refresh();
      } else {
        setError(result.error || 'Failed to send email');
      }
    });
  };

  const handleCancel = () => {
    setBody(initialBody);
    setIsEditing(false);
    setError(null);
  };

  const formatDateTime = (date: Date) => {
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  return (
    <div className="px-4 py-3 bg-amber-50 border-l-4 border-amber-400">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="text-sm">
          <span className="font-medium text-amber-700">
            {fromEmail.split('@')[0]}
          </span>
          <span className="text-xs text-amber-600 ml-2">(Pool Patrol - Draft)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs px-2 py-0.5 bg-amber-200 text-amber-800 rounded font-medium">
            DRAFT - PENDING REVIEW
          </span>
          <span className="text-xs text-amber-500">
            {formatDateTime(sentAt)}
          </span>
        </div>
      </div>

      {/* Recipients */}
      <div className="text-xs text-amber-600 mb-3">
        To: {toEmails.join(', ')}
      </div>

      {/* Body */}
      {isEditing ? (
        <div className="space-y-3">
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className="w-full h-64 p-3 text-sm border border-amber-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-amber-400 resize-y"
            placeholder="Email body..."
          />
          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-3 py-1.5 text-sm font-medium bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 disabled:bg-neutral-400 disabled:cursor-not-allowed"
            >
              {isSaving ? 'Saving...' : 'Save Draft'}
            </button>
            <button
              onClick={handleCancel}
              disabled={isSaving}
              className="px-3 py-1.5 text-sm font-medium text-neutral-600 hover:text-neutral-900 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="text-sm text-neutral-700 whitespace-pre-wrap mb-4">
          {body}
        </div>
      )}

      {/* Status Messages */}
      {error && (
        <div className="mb-3 px-3 py-2 text-sm bg-red-100 text-red-700 rounded-lg">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-3 px-3 py-2 text-sm bg-emerald-100 text-emerald-700 rounded-lg">
          {success}
        </div>
      )}

      {/* Action Buttons */}
      {!isEditing && (
        <div className="flex items-center justify-between pt-3 border-t border-amber-200">
          <button
            onClick={() => setIsEditing(true)}
            disabled={isSending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-neutral-700 bg-white border border-neutral-300 rounded-lg hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Edit
          </button>
          <button
            onClick={handleSend}
            disabled={isSending || isSaving}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 disabled:bg-emerald-400 disabled:cursor-not-allowed"
          >
            {isSending ? (
              <>
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Sending...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                Approve & Send
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
