import { messagingApi } from "@line/bot-sdk";
import { loadConfig, logVerbose, recordChannelActivity, retryAsync } from "openclaw/plugin-sdk";
import type { OpenClawConfig } from "openclaw/plugin-sdk";
import { resolveLineAccount } from "./accounts.js";
import { resolveLineChannelAccessToken } from "./channel-access-token.js";
import type { LineSendResult } from "./types.js";

type Message = messagingApi.Message;
type TextMessage = messagingApi.TextMessage;
type ImageMessage = messagingApi.ImageMessage;
type VideoMessage = messagingApi.VideoMessage & { trackingId?: string };
type AudioMessage = messagingApi.AudioMessage;
type LocationMessage = messagingApi.LocationMessage;
type FlexMessage = messagingApi.FlexMessage;
type FlexContainer = messagingApi.FlexContainer;
type TemplateMessage = messagingApi.TemplateMessage;
type QuickReply = messagingApi.QuickReply;
type QuickReplyItem = messagingApi.QuickReplyItem;

const userProfileCache = new Map<
  string,
  { displayName: string; pictureUrl?: string; fetchedAt: number }
>();
const PROFILE_CACHE_TTL_MS = 5 * 60 * 1000;

// Retry settings for LINE API calls
const LINE_RETRY_ATTEMPTS = 4;
const LINE_RETRY_MIN_DELAY_MS = 300;
const LINE_RETRY_MAX_DELAY_MS = 5000;
const LINE_RETRY_JITTER = 0.2;

// Serialize outbound sends per LINE account to reduce short burst collisions.
const lineOutboundChains = new Map<string, Promise<void>>();

interface LineSendOpts {
  cfg?: OpenClawConfig;
  channelAccessToken?: string;
  accountId?: string;
  verbose?: boolean;
  mediaUrl?: string;
  mediaKind?: "image" | "video" | "audio";
  previewImageUrl?: string;
  durationMs?: number;
  trackingId?: string;
  replyToken?: string;
}

type LineClientOpts = Pick<LineSendOpts, "cfg" | "channelAccessToken" | "accountId">;
type LinePushOpts = Pick<LineSendOpts, "cfg" | "channelAccessToken" | "accountId" | "verbose">;

interface LinePushBehavior {
  errorContext?: string;
  verboseMessage?: (chatId: string, messageCount: number) => string;
}

interface LineReplyBehavior {
  verboseMessage?: (messageCount: number) => string;
}

function normalizeTarget(to: string): string {
  const trimmed = to.trim();
  if (!trimmed) {
    throw new Error("Recipient is required for LINE sends");
  }

  const normalized = trimmed
    .replace(/^line:group:/i, "")
    .replace(/^line:room:/i, "")
    .replace(/^line:user:/i, "")
    .replace(/^line:/i, "");

  if (!normalized) {
    throw new Error("Recipient is required for LINE sends");
  }

  return normalized;
}

function isLineUserChatId(chatId: string): boolean {
  return /^U/i.test(chatId);
}

function unknownToString(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (value instanceof Error) {
    return `${value.name}: ${value.message}`;
  }
  try {
    return JSON.stringify(value);
  } catch {
    return "";
  }
}

function isLineRateLimitError(err: unknown): boolean {
  if (!err || typeof err !== "object") {
    return false;
  }
  const withStatus = err as { status?: unknown; statusCode?: unknown };
  const status =
    typeof withStatus.status === "number"
      ? withStatus.status
      : typeof withStatus.statusCode === "number"
        ? withStatus.statusCode
        : undefined;
  if (status === 429) {
    return true;
  }
  const text = unknownToString(err);
  return /429|too many requests/i.test(text);
}

function resolveRetryAfterMs(err: unknown): number | undefined {
  if (!err || typeof err !== "object") {
    return undefined;
  }
  const response = (err as { response?: { headers?: unknown } }).response;
  const headers = response?.headers;
  if (!headers || typeof headers !== "object") {
    return undefined;
  }
  const retryAfterRaw = (headers as Record<string, unknown>)["retry-after"];
  if (typeof retryAfterRaw === "number" && Number.isFinite(retryAfterRaw)) {
    return Math.max(0, retryAfterRaw * 1000);
  }
  if (typeof retryAfterRaw === "string") {
    const parsed = Number(retryAfterRaw);
    if (Number.isFinite(parsed)) {
      return Math.max(0, parsed * 1000);
    }
  }
  return undefined;
}

async function runWithLineRetry<T>(fn: () => Promise<T>, label: string): Promise<T> {
  return retryAsync(fn, {
    label,
    attempts: LINE_RETRY_ATTEMPTS,
    minDelayMs: LINE_RETRY_MIN_DELAY_MS,
    maxDelayMs: LINE_RETRY_MAX_DELAY_MS,
    jitter: LINE_RETRY_JITTER,
    shouldRetry: (err) => isLineRateLimitError(err),
    retryAfterMs: resolveRetryAfterMs,
    onRetry: (info) => {
      const maxRetries = Math.max(1, info.maxAttempts - 1);
      logVerbose(
        `line: retry ${info.attempt}/${maxRetries} for ${info.label ?? label} in ${info.delayMs}ms: ${String(info.err)}`,
      );
    },
  });
}

async function runLineOutboundSerial<T>(accountId: string, fn: () => Promise<T>): Promise<T> {
  const previous = lineOutboundChains.get(accountId) ?? Promise.resolve();
  const gate = previous.catch(() => undefined);
  let release: () => void = () => undefined;
  const current = new Promise<void>((resolve) => {
    release = resolve;
  });
  const chain = gate.then(() => current);
  lineOutboundChains.set(accountId, chain);
  try {
    await gate;
    return await fn();
  } finally {
    release();
    const latest = lineOutboundChains.get(accountId);
    if (latest && latest === chain) {
      lineOutboundChains.delete(accountId);
    }
  }
}

function createLineMessagingClient(opts: LineClientOpts): {
  account: ReturnType<typeof resolveLineAccount>;
  client: messagingApi.MessagingApiClient;
} {
  const cfg = opts.cfg ?? loadConfig();
  const account = resolveLineAccount({
    cfg,
    accountId: opts.accountId,
  });
  const token = resolveLineChannelAccessToken(opts.channelAccessToken, account);
  const client = new messagingApi.MessagingApiClient({
    channelAccessToken: token,
  });
  return { account, client };
}

function createLinePushContext(
  to: string,
  opts: LineClientOpts,
): {
  account: ReturnType<typeof resolveLineAccount>;
  client: messagingApi.MessagingApiClient;
  chatId: string;
} {
  const { account, client } = createLineMessagingClient(opts);
  const chatId = normalizeTarget(to);
  return { account, client, chatId };
}

function createTextMessage(text: string): TextMessage {
  return { type: "text", text };
}

export function createImageMessage(
  originalContentUrl: string,
  previewImageUrl?: string,
): ImageMessage {
  return {
    type: "image",
    originalContentUrl,
    previewImageUrl: previewImageUrl ?? originalContentUrl,
  };
}

export function createVideoMessage(
  originalContentUrl: string,
  previewImageUrl: string,
  trackingId?: string,
): VideoMessage {
  return {
    type: "video",
    originalContentUrl,
    previewImageUrl,
    ...(trackingId ? { trackingId } : {}),
  };
}

export function createAudioMessage(originalContentUrl: string, durationMs: number): AudioMessage {
  return {
    type: "audio",
    originalContentUrl,
    duration: durationMs,
  };
}

export function createLocationMessage(location: {
  title: string;
  address: string;
  latitude: number;
  longitude: number;
}): LocationMessage {
  return {
    type: "location",
    title: location.title.slice(0, 100),
    address: location.address.slice(0, 100),
    latitude: location.latitude,
    longitude: location.longitude,
  };
}

function logLineHttpError(err: unknown, context: string): void {
  if (!err || typeof err !== "object") {
    return;
  }
  const { status, statusText, body } = err as {
    status?: number;
    statusText?: string;
    body?: string;
  };
  if (typeof body === "string") {
    const summary = status ? `${status} ${statusText ?? ""}`.trim() : "unknown status";
    logVerbose(`line: ${context} failed (${summary}): ${body}`);
  }
}

function recordLineOutboundActivity(accountId: string): void {
  recordChannelActivity({
    channel: "line",
    accountId,
    direction: "outbound",
  });
}

async function pushLineMessages(
  to: string,
  messages: Message[],
  opts: LinePushOpts = {},
  behavior: LinePushBehavior = {},
): Promise<LineSendResult> {
  if (messages.length === 0) {
    throw new Error("Message must be non-empty for LINE sends");
  }

  const { account, client, chatId } = createLinePushContext(to, opts);
  await runLineOutboundSerial(account.accountId, () =>
    runWithLineRetry(async () => {
      const pushRequest = client.pushMessage({
        to: chatId,
        messages,
      });
      if (behavior.errorContext) {
        const errorContext = behavior.errorContext;
        await pushRequest.catch((err) => {
          logLineHttpError(err, errorContext);
          throw err;
        });
      } else {
        await pushRequest;
      }
    }, "line.pushMessage"),
  );

  recordLineOutboundActivity(account.accountId);

  if (opts.verbose) {
    const logMessage =
      behavior.verboseMessage?.(chatId, messages.length) ??
      `line: pushed ${messages.length} messages to ${chatId}`;
    logVerbose(logMessage);
  }

  return {
    messageId: "push",
    chatId,
  };
}

async function replyLineMessages(
  replyToken: string,
  messages: Message[],
  opts: LinePushOpts = {},
  behavior: LineReplyBehavior = {},
): Promise<void> {
  const { account, client } = createLineMessagingClient(opts);
  await runLineOutboundSerial(account.accountId, () =>
    runWithLineRetry(
      () =>
        client.replyMessage({
          replyToken,
          messages,
        }),
      "line.replyMessage",
    ),
  );

  recordLineOutboundActivity(account.accountId);

  if (opts.verbose) {
    logVerbose(
      behavior.verboseMessage?.(messages.length) ??
        `line: replied with ${messages.length} messages`,
    );
  }
}

export async function sendMessageLine(
  to: string,
  text: string,
  opts: LineSendOpts = {},
): Promise<LineSendResult> {
  const chatId = normalizeTarget(to);
  const messages: Message[] = [];

  const mediaUrl = opts.mediaUrl?.trim();
  if (mediaUrl) {
    switch (opts.mediaKind) {
      case "video": {
        const previewImageUrl = opts.previewImageUrl?.trim();
        if (!previewImageUrl) {
          throw new Error("LINE video messages require previewImageUrl to reference an image URL");
        }
        const trackingId = isLineUserChatId(chatId) ? opts.trackingId : undefined;
        messages.push(createVideoMessage(mediaUrl, previewImageUrl, trackingId));
        break;
      }
      case "audio":
        messages.push(createAudioMessage(mediaUrl, opts.durationMs ?? 60000));
        break;
      case "image":
      default:
        // Backward compatibility: keep image as default when media kind is unspecified.
        messages.push(createImageMessage(mediaUrl, opts.previewImageUrl?.trim() || mediaUrl));
        break;
    }
  }

  if (text?.trim()) {
    messages.push(createTextMessage(text.trim()));
  }

  if (messages.length === 0) {
    throw new Error("Message must be non-empty for LINE sends");
  }

  if (opts.replyToken) {
    await replyLineMessages(opts.replyToken, messages, opts, {
      verboseMessage: () => `line: replied to ${chatId}`,
    });

    return {
      messageId: "reply",
      chatId,
    };
  }

  return pushLineMessages(chatId, messages, opts, {
    verboseMessage: (resolvedChatId) => `line: pushed message to ${resolvedChatId}`,
  });
}

export async function pushMessageLine(
  to: string,
  text: string,
  opts: LineSendOpts = {},
): Promise<LineSendResult> {
  return sendMessageLine(to, text, { ...opts, replyToken: undefined });
}

export async function replyMessageLine(
  replyToken: string,
  messages: Message[],
  opts: LinePushOpts = {},
): Promise<void> {
  await replyLineMessages(replyToken, messages, opts);
}

export async function pushMessagesLine(
  to: string,
  messages: Message[],
  opts: LinePushOpts = {},
): Promise<LineSendResult> {
  return pushLineMessages(to, messages, opts, {
    errorContext: "push message",
  });
}

export function createFlexMessage(
  altText: string,
  contents: messagingApi.FlexContainer,
): messagingApi.FlexMessage {
  return {
    type: "flex",
    altText,
    contents,
  };
}

export async function pushImageMessage(
  to: string,
  originalContentUrl: string,
  previewImageUrl?: string,
  opts: LinePushOpts = {},
): Promise<LineSendResult> {
  return pushLineMessages(to, [createImageMessage(originalContentUrl, previewImageUrl)], opts, {
    verboseMessage: (chatId) => `line: pushed image to ${chatId}`,
  });
}

export async function pushLocationMessage(
  to: string,
  location: {
    title: string;
    address: string;
    latitude: number;
    longitude: number;
  },
  opts: LinePushOpts = {},
): Promise<LineSendResult> {
  return pushLineMessages(to, [createLocationMessage(location)], opts, {
    verboseMessage: (chatId) => `line: pushed location to ${chatId}`,
  });
}

export async function pushFlexMessage(
  to: string,
  altText: string,
  contents: FlexContainer,
  opts: LinePushOpts = {},
): Promise<LineSendResult> {
  const flexMessage: FlexMessage = {
    type: "flex",
    altText: altText.slice(0, 400),
    contents,
  };

  return pushLineMessages(to, [flexMessage], opts, {
    errorContext: "push flex message",
    verboseMessage: (chatId) => `line: pushed flex message to ${chatId}`,
  });
}

export async function pushTemplateMessage(
  to: string,
  template: TemplateMessage,
  opts: LinePushOpts = {},
): Promise<LineSendResult> {
  return pushLineMessages(to, [template], opts, {
    verboseMessage: (chatId) => `line: pushed template message to ${chatId}`,
  });
}

export async function pushTextMessageWithQuickReplies(
  to: string,
  text: string,
  quickReplyLabels: string[],
  opts: LinePushOpts = {},
): Promise<LineSendResult> {
  const message = createTextMessageWithQuickReplies(text, quickReplyLabels);

  return pushLineMessages(to, [message], opts, {
    verboseMessage: (chatId) => `line: pushed message with quick replies to ${chatId}`,
  });
}

export function createQuickReplyItems(labels: string[]): QuickReply {
  const items: QuickReplyItem[] = labels.slice(0, 13).map((label) => ({
    type: "action",
    action: {
      type: "message",
      label: label.slice(0, 20),
      text: label,
    },
  }));
  return { items };
}

export function createTextMessageWithQuickReplies(
  text: string,
  quickReplyLabels: string[],
): TextMessage & { quickReply: QuickReply } {
  return {
    type: "text",
    text,
    quickReply: createQuickReplyItems(quickReplyLabels),
  };
}

export async function showLoadingAnimation(
  chatId: string,
  opts: { channelAccessToken?: string; accountId?: string; loadingSeconds?: number } = {},
): Promise<void> {
  const { client } = createLineMessagingClient(opts);

  try {
    await client.showLoadingAnimation({
      chatId: normalizeTarget(chatId),
      loadingSeconds: opts.loadingSeconds ?? 20,
    });
    logVerbose(`line: showing loading animation to ${chatId}`);
  } catch (err) {
    logVerbose(`line: loading animation failed (non-fatal): ${String(err)}`);
  }
}

export async function getUserProfile(
  userId: string,
  opts: { channelAccessToken?: string; accountId?: string; useCache?: boolean } = {},
): Promise<{ displayName: string; pictureUrl?: string } | null> {
  const useCache = opts.useCache ?? true;

  if (useCache) {
    const cached = userProfileCache.get(userId);
    if (cached && Date.now() - cached.fetchedAt < PROFILE_CACHE_TTL_MS) {
      return { displayName: cached.displayName, pictureUrl: cached.pictureUrl };
    }
  }

  const { client } = createLineMessagingClient(opts);

  try {
    const profile = await client.getProfile(userId);
    const result = {
      displayName: profile.displayName,
      pictureUrl: profile.pictureUrl,
    };

    userProfileCache.set(userId, {
      ...result,
      fetchedAt: Date.now(),
    });

    return result;
  } catch (err) {
    logVerbose(`line: failed to fetch profile for ${userId}: ${String(err)}`);
    return null;
  }
}

export async function getUserDisplayName(
  userId: string,
  opts: { channelAccessToken?: string; accountId?: string } = {},
): Promise<string> {
  const profile = await getUserProfile(userId, opts);
  return profile?.displayName ?? userId;
}
