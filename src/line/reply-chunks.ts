import type { messagingApi } from "@line/bot-sdk";

export type LineReplyMessage = messagingApi.TextMessage;

export type SendLineReplyChunksParams = {
  to: string;
  chunks: string[];
  quickReplies?: string[];
  replyToken?: string | null;
  replyTokenUsed?: boolean;
  accountId?: string;
  replyMessageLine: (
    replyToken: string,
    messages: messagingApi.Message[],
    opts?: { accountId?: string },
  ) => Promise<unknown>;
  pushMessagesLine: (
    to: string,
    messages: messagingApi.Message[],
    opts?: { accountId?: string },
  ) => Promise<unknown>;
  pushMessageLine: (to: string, text: string, opts?: { accountId?: string }) => Promise<unknown>;
  pushTextMessageWithQuickReplies: (
    to: string,
    text: string,
    quickReplies: string[],
    opts?: { accountId?: string },
  ) => Promise<unknown>;
  createTextMessageWithQuickReplies: (text: string, quickReplies: string[]) => LineReplyMessage;
  onReplyError?: (err: unknown) => void;
};

export async function sendLineReplyChunks(
  params: SendLineReplyChunksParams,
): Promise<{ replyTokenUsed: boolean }> {
  const hasQuickReplies = Boolean(params.quickReplies?.length);
  let replyTokenUsed = Boolean(params.replyTokenUsed);

  const pushChunkBatch = async (chunks: string[]): Promise<void> => {
    if (chunks.length === 0) {
      return;
    }
    const messages = chunks.map((chunk) => ({
      type: "text" as const,
      text: chunk,
    }));
    await params.pushMessagesLine(params.to, messages, {
      accountId: params.accountId,
    });
  };

  const pushRemainingChunks = async (chunks: string[]): Promise<void> => {
    if (chunks.length === 0) {
      return;
    }

    const lastIndex = chunks.length - 1;
    const quickReplyBatchStart = hasQuickReplies ? Math.max(0, lastIndex - 4) : chunks.length;

    for (let i = 0; i < quickReplyBatchStart; i += 5) {
      await pushChunkBatch(chunks.slice(i, Math.min(i + 5, quickReplyBatchStart)));
    }

    if (!hasQuickReplies) {
      await pushChunkBatch(chunks.slice(quickReplyBatchStart));
      return;
    }

    const finalBatch = chunks.slice(quickReplyBatchStart).map((chunk) => ({
      type: "text" as const,
      text: chunk,
    }));
    if (finalBatch.length > 0) {
      finalBatch[finalBatch.length - 1] = params.createTextMessageWithQuickReplies(
        chunks[lastIndex],
        params.quickReplies!,
      );
      await params.pushMessagesLine(params.to, finalBatch, {
        accountId: params.accountId,
      });
    }
  };

  if (params.chunks.length === 0) {
    return { replyTokenUsed };
  }

  if (params.replyToken && !replyTokenUsed) {
    try {
      const replyBatch = params.chunks.slice(0, 5);
      const remaining = params.chunks.slice(replyBatch.length);

      const replyMessages: LineReplyMessage[] = replyBatch.map((chunk) => ({
        type: "text",
        text: chunk,
      }));

      if (hasQuickReplies && remaining.length === 0 && replyMessages.length > 0) {
        const lastIndex = replyMessages.length - 1;
        replyMessages[lastIndex] = params.createTextMessageWithQuickReplies(
          replyBatch[lastIndex],
          params.quickReplies!,
        );
      }

      await params.replyMessageLine(params.replyToken, replyMessages, {
        accountId: params.accountId,
      });
      replyTokenUsed = true;

      await pushRemainingChunks(remaining);

      return { replyTokenUsed };
    } catch (err) {
      params.onReplyError?.(err);
      replyTokenUsed = true;
    }
  }

  await pushRemainingChunks(params.chunks);

  return { replyTokenUsed };
}
