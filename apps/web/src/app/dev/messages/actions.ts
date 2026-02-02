'use server';

import prisma from '@/database/db';

export interface AddMessageInput {
  threadId: string;
  fromEmail: string;
  body: string;
  direction: 'inbound' | 'outbound';
}

export interface AddMessageResult {
  success: boolean;
  messageId?: string;
  error?: string;
}

/**
 * Adds a new message to an existing email thread.
 */
export async function addMessage(data: AddMessageInput): Promise<AddMessageResult> {
  try {
    // Validate thread exists and get vanpool info
    const thread = await prisma.emailThread.findUnique({
      where: { threadId: data.threadId },
      include: {
        vanpool: {
          include: {
            riders: {
              include: {
                employee: true,
              },
            },
          },
        },
        messages: {
          select: { messageId: true },
        },
      },
    });

    if (!thread) {
      return { success: false, error: `Thread ${data.threadId} not found` };
    }

    // Generate message ID (e.g., MSG-001-003)
    // Find the maximum message number across all messages in the thread
    const threadNum = data.threadId.replace('THREAD-', '');
    let maxMsgNum = 0;
    for (const msg of thread.messages) {
      const parts = msg.messageId.split('-');
      if (parts.length >= 3) {
        const num = parseInt(parts[2], 10);
        if (!isNaN(num) && num > maxMsgNum) {
          maxMsgNum = num;
        }
      }
    }
    const nextMsgNum = maxMsgNum + 1;
    const messageId = `MSG-${threadNum}-${String(nextMsgNum).padStart(3, '0')}`;

    // Determine toEmails based on direction
    let toEmails: string[];
    if (data.direction === 'outbound') {
      // Outbound: send to all employees in the vanpool
      toEmails = thread.vanpool.riders.map((r) => r.employee.email);
    } else {
      // Inbound: reply to poolpatrol
      toEmails = ['poolpatrol@innovatecorp.com'];
    }

    // Create the message
    await prisma.message.create({
      data: {
        messageId,
        threadId: data.threadId,
        fromEmail: data.fromEmail,
        toEmails: JSON.stringify(toEmails),
        sentAt: new Date(),
        body: data.body,
        direction: data.direction,
        status: 'sent',
      },
    });

    return { success: true, messageId };
  } catch (error) {
    console.error('Error adding message:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred',
    };
  }
}
