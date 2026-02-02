'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { Message } from '@prisma/client';
import { addMessage } from '@/app/dev/messages/actions';

interface Employee {
  employeeId: string;
  firstName: string;
  lastName: string;
  email: string;
}

interface ThreadWithDetails {
  threadId: string;
  subject: string;
  vanpoolId: string;
  caseId: string;
  caseStatus: string;
  workSite: string;
  employees: Employee[];
  messages: Message[];
}

interface MessageThreadFormProps {
  threads: ThreadWithDetails[];
}

function formatDate(date: Date): string {
  return new Date(date).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatStatus(status: string): string {
  if (status === 'hitl_review') return 'HITL Review';
  return status
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function MessageThreadForm({ threads }: MessageThreadFormProps) {
  const router = useRouter();
  const [selectedThreadId, setSelectedThreadId] = useState('');
  const [direction, setDirection] = useState<'inbound' | 'outbound'>('inbound');
  const [fromEmail, setFromEmail] = useState('');
  const [body, setBody] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selectedThread = threads.find((t) => t.threadId === selectedThreadId);

  const handleThreadChange = (threadId: string) => {
    setSelectedThreadId(threadId);
    setError(null);
    setSuccess(null);
    // Pre-fill from email based on first employee if inbound
    const thread = threads.find((t) => t.threadId === threadId);
    if (thread && thread.employees.length > 0) {
      setFromEmail(thread.employees[0].email);
    }
  };

  const handleDirectionChange = (dir: 'inbound' | 'outbound') => {
    setDirection(dir);
    if (dir === 'outbound') {
      setFromEmail('poolpatrol@innovatecorp.com');
    } else if (selectedThread && selectedThread.employees.length > 0) {
      setFromEmail(selectedThread.employees[0].email);
    }
  };

  const handleSubmit = async () => {
    if (!selectedThreadId || !fromEmail || !body.trim()) {
      setError('Please fill in all fields');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const result = await addMessage({
        threadId: selectedThreadId,
        fromEmail,
        body: body.trim(),
        direction,
      });

      if (result.success) {
        setSuccess(`Message ${result.messageId} added successfully`);
        setBody('');
        router.refresh();
      } else {
        setError(result.error || 'Failed to add message');
      }
    } catch {
      setError('An unexpected error occurred');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Thread Selector */}
      <div className="border border-neutral-200 rounded-lg">
        <div className="bg-neutral-50 px-4 py-3 border-b border-neutral-200">
          <h2 className="text-sm font-medium text-neutral-900">Select Thread</h2>
        </div>
        <div className="p-4">
          <select
            value={selectedThreadId}
            onChange={(e) => handleThreadChange(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
          >
            <option value="">Select an email thread...</option>
            {threads.map((thread) => (
              <option key={thread.threadId} value={thread.threadId}>
                {thread.threadId} - {thread.vanpoolId} - {thread.subject.slice(0, 40)}...
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Thread Details */}
      {selectedThread && (
        <>
          {/* Vanpool & Employee Info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="border border-neutral-200 rounded-lg">
              <div className="bg-neutral-50 px-4 py-3 border-b border-neutral-200">
                <h2 className="text-sm font-medium text-neutral-900">Vanpool Info</h2>
              </div>
              <div className="p-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-neutral-500">Vanpool</span>
                  <span className="font-mono text-neutral-900">{selectedThread.vanpoolId}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Work Site</span>
                  <span className="text-neutral-900">{selectedThread.workSite}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Case</span>
                  <span className="font-mono text-neutral-900">{selectedThread.caseId}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Status</span>
                  <span className="text-neutral-900">{formatStatus(selectedThread.caseStatus)}</span>
                </div>
              </div>
            </div>

            <div className="border border-neutral-200 rounded-lg">
              <div className="bg-neutral-50 px-4 py-3 border-b border-neutral-200">
                <h2 className="text-sm font-medium text-neutral-900">
                  Employees ({selectedThread.employees.length})
                </h2>
              </div>
              <div className="p-4 max-h-40 overflow-y-auto">
                {selectedThread.employees.length > 0 ? (
                  <ul className="space-y-2">
                    {selectedThread.employees.map((emp) => (
                      <li key={emp.employeeId} className="text-sm">
                        <div className="font-medium text-neutral-900">
                          {emp.firstName} {emp.lastName}
                        </div>
                        <div className="text-xs text-neutral-500">{emp.email}</div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-neutral-500">No employees in this vanpool</p>
                )}
              </div>
            </div>
          </div>

          {/* Message History */}
          <div className="border border-neutral-200 rounded-lg">
            <div className="bg-neutral-50 px-4 py-3 border-b border-neutral-200">
              <h2 className="text-sm font-medium text-neutral-900">
                Message History ({selectedThread.messages.length})
              </h2>
            </div>
            <div className="divide-y divide-neutral-100 max-h-80 overflow-y-auto">
              {selectedThread.messages.length > 0 ? (
                selectedThread.messages.map((msg) => (
                  <div key={msg.messageId} className="p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded ${
                          msg.direction === 'outbound'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-neutral-100 text-neutral-700'
                        }`}
                      >
                        {msg.direction === 'outbound' ? '← OUT' : '→ IN'}
                      </span>
                      <span className="text-sm font-medium text-neutral-900">{msg.fromEmail}</span>
                      <span className="text-xs text-neutral-400">{formatDate(msg.sentAt)}</span>
                    </div>
                    <p className="text-sm text-neutral-700 whitespace-pre-wrap line-clamp-4">
                      {msg.body}
                    </p>
                  </div>
                ))
              ) : (
                <div className="p-4 text-sm text-neutral-500">No messages in this thread</div>
              )}
            </div>
          </div>

          {/* Add New Message */}
          <div className="border border-neutral-200 rounded-lg">
            <div className="bg-neutral-50 px-4 py-3 border-b border-neutral-200">
              <h2 className="text-sm font-medium text-neutral-900">Add New Message</h2>
            </div>
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">
                    Direction
                  </label>
                  <select
                    value={direction}
                    onChange={(e) => handleDirectionChange(e.target.value as 'inbound' | 'outbound')}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
                  >
                    <option value="inbound">Inbound (from employee)</option>
                    <option value="outbound">Outbound (from Pool Patrol)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-600 mb-1">
                    From Email
                  </label>
                  <input
                    type="email"
                    value={fromEmail}
                    onChange={(e) => setFromEmail(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
                    placeholder="sender@example.com"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-neutral-600 mb-1">
                  Message Body
                </label>
                <textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent resize-none"
                  placeholder="Type your message here..."
                />
              </div>
              <div className="flex justify-end">
                <button
                  onClick={handleSubmit}
                  disabled={isSubmitting || !body.trim()}
                  className="px-6 py-2.5 text-sm font-medium bg-neutral-900 text-white rounded-lg hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isSubmitting ? 'Adding...' : 'Add Message'}
                </button>
              </div>
              {/* Error/Success messages */}
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg overflow-hidden">
                  <p className="text-sm text-red-800 break-words whitespace-pre-wrap">{error}</p>
                </div>
              )}
              {success && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg overflow-hidden">
                  <p className="text-sm text-emerald-800 break-words">{success}</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
