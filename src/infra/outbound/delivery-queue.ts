import fs from "node:fs";
import path from "node:path";
import type { ReplyPayload } from "../../auto-reply/types.js";
import type { OpenClawConfig } from "../../config/config.js";
import { resolveStateDir } from "../../config/paths.js";
import { generateSecureUuid } from "../secure-random.js";
import type { OutboundChannel } from "./targets.js";

const QUEUE_DIRNAME = "delivery-queue";
const FAILED_DIRNAME = "failed";
const MAX_RETRIES = 5;
const DEFAULT_MAX_RECOVERY_MS = 300_000; // 5m: prevents large backlog deferral after restarts.
const RECOVERY_FAST_DRAIN_THRESHOLD = 50;
const RECOVERY_BACKOFF_CAP_MS = 2_000;
/** Purge delivery entries older than this age (ms) on recovery to prevent retry storms. */
const MAX_ENTRY_AGE_MS = 2 * 60 * 60 * 1000; // 2h

/** Backoff delays in milliseconds indexed by retry count (1-based). */
const BACKOFF_MS: readonly number[] = [
  5_000, // retry 1: 5s
  25_000, // retry 2: 25s
  120_000, // retry 3: 2m
  600_000, // retry 4: 10m
];

type DeliveryMirrorPayload = {
  sessionKey: string;
  agentId?: string;
  text?: string;
  mediaUrls?: string[];
};

export interface QueuedDelivery {
  id: string;
  enqueuedAt: number;
  channel: Exclude<OutboundChannel, "none">;
  to: string;
  accountId?: string;
  /**
   * Original payloads before plugin hooks. On recovery, hooks re-run on these
   * payloads — this is intentional since hooks are stateless transforms and
   * should produce the same result on replay.
   */
  payloads: ReplyPayload[];
  threadId?: string | number | null;
  replyToId?: string | null;
  bestEffort?: boolean;
  gifPlayback?: boolean;
  silent?: boolean;
  mirror?: DeliveryMirrorPayload;
  retryCount: number;
  lastError?: string;
}

function resolveQueueDir(stateDir?: string): string {
  const base = stateDir ?? resolveStateDir();
  return path.join(base, QUEUE_DIRNAME);
}

function resolveFailedDir(stateDir?: string): string {
  return path.join(resolveQueueDir(stateDir), FAILED_DIRNAME);
}

/** Ensure the queue directory (and failed/ subdirectory) exist. */
export async function ensureQueueDir(stateDir?: string): Promise<string> {
  const queueDir = resolveQueueDir(stateDir);
  await fs.promises.mkdir(queueDir, { recursive: true, mode: 0o700 });
  await fs.promises.mkdir(resolveFailedDir(stateDir), { recursive: true, mode: 0o700 });
  return queueDir;
}

/** Persist a delivery entry to disk before attempting send. Returns the entry ID. */
type QueuedDeliveryParams = {
  channel: Exclude<OutboundChannel, "none">;
  to: string;
  accountId?: string;
  payloads: ReplyPayload[];
  threadId?: string | number | null;
  replyToId?: string | null;
  bestEffort?: boolean;
  gifPlayback?: boolean;
  silent?: boolean;
  mirror?: DeliveryMirrorPayload;
};

export async function enqueueDelivery(
  params: QueuedDeliveryParams,
  stateDir?: string,
): Promise<string> {
  const queueDir = await ensureQueueDir(stateDir);
  const id = generateSecureUuid();
  const entry: QueuedDelivery = {
    id,
    enqueuedAt: Date.now(),
    channel: params.channel,
    to: params.to,
    accountId: params.accountId,
    payloads: params.payloads,
    threadId: params.threadId,
    replyToId: params.replyToId,
    bestEffort: params.bestEffort,
    gifPlayback: params.gifPlayback,
    silent: params.silent,
    mirror: params.mirror,
    retryCount: 0,
  };
  const filePath = path.join(queueDir, `${id}.json`);
  const tmp = `${filePath}.${process.pid}.tmp`;
  const json = JSON.stringify(entry, null, 2);
  await fs.promises.writeFile(tmp, json, { encoding: "utf-8", mode: 0o600 });
  await fs.promises.rename(tmp, filePath);
  return id;
}

/** Remove a successfully delivered entry from the queue. */
export async function ackDelivery(id: string, stateDir?: string): Promise<void> {
  const filePath = path.join(resolveQueueDir(stateDir), `${id}.json`);
  try {
    await fs.promises.unlink(filePath);
  } catch (err) {
    const code =
      err && typeof err === "object" && "code" in err
        ? String((err as { code?: unknown }).code)
        : null;
    if (code !== "ENOENT") {
      throw err;
    }
    // Already removed — no-op.
  }
}

/** Update a queue entry after a failed delivery attempt. */
export async function failDelivery(id: string, error: string, stateDir?: string): Promise<void> {
  const filePath = path.join(resolveQueueDir(stateDir), `${id}.json`);
  const raw = await fs.promises.readFile(filePath, "utf-8");
  const entry: QueuedDelivery = JSON.parse(raw);
  entry.retryCount += 1;
  entry.lastError = error;
  const tmp = `${filePath}.${process.pid}.tmp`;
  await fs.promises.writeFile(tmp, JSON.stringify(entry, null, 2), {
    encoding: "utf-8",
    mode: 0o600,
  });
  await fs.promises.rename(tmp, filePath);
}

/** Load all pending delivery entries from the queue directory. */
export async function loadPendingDeliveries(stateDir?: string): Promise<QueuedDelivery[]> {
  const queueDir = resolveQueueDir(stateDir);
  let files: string[];
  try {
    files = await fs.promises.readdir(queueDir);
  } catch (err) {
    const code =
      err && typeof err === "object" && "code" in err
        ? String((err as { code?: unknown }).code)
        : null;
    if (code === "ENOENT") {
      return [];
    }
    throw err;
  }
  const entries: QueuedDelivery[] = [];
  for (const file of files) {
    if (!file.endsWith(".json")) {
      continue;
    }
    const filePath = path.join(queueDir, file);
    try {
      const stat = await fs.promises.stat(filePath);
      if (!stat.isFile()) {
        continue;
      }
      const raw = await fs.promises.readFile(filePath, "utf-8");
      entries.push(JSON.parse(raw));
    } catch {
      // Skip malformed or inaccessible entries.
    }
  }
  return entries;
}

/** Move a queue entry to the failed/ subdirectory. */
export async function moveToFailed(id: string, stateDir?: string): Promise<void> {
  const queueDir = resolveQueueDir(stateDir);
  const failedDir = resolveFailedDir(stateDir);
  await fs.promises.mkdir(failedDir, { recursive: true, mode: 0o700 });
  const src = path.join(queueDir, `${id}.json`);
  const dest = path.join(failedDir, `${id}.json`);
  await fs.promises.rename(src, dest);
}

/** Compute the backoff delay in ms for a given retry count. */
export function computeBackoffMs(retryCount: number): number {
  if (retryCount <= 0) {
    return 0;
  }
  return BACKOFF_MS[Math.min(retryCount - 1, BACKOFF_MS.length - 1)] ?? BACKOFF_MS.at(-1) ?? 0;
}

export type DeliverFn = (
  params: {
    cfg: OpenClawConfig;
  } & QueuedDeliveryParams & {
      skipQueue?: boolean;
    },
) => Promise<unknown>;

export interface RecoveryLogger {
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
}

/**
 * On gateway startup, scan the delivery queue and retry any pending entries.
 * Uses exponential backoff and moves entries that exceed MAX_RETRIES to failed/.
 */
export async function recoverPendingDeliveries(opts: {
  deliver: DeliverFn;
  log: RecoveryLogger;
  cfg: OpenClawConfig;
  stateDir?: string;
  /** Override for testing — resolves instead of using real setTimeout. */
  delay?: (ms: number) => Promise<void>;
  /** Maximum wall-clock time for recovery in ms. Remaining entries are deferred to next restart. Default: 300 000. */
  maxRecoveryMs?: number;
}): Promise<{ recovered: number; failed: number; skipped: number }> {
  const pending = await loadPendingDeliveries(opts.stateDir);
  if (pending.length === 0) {
    return { recovered: 0, failed: 0, skipped: 0 };
  }

  // Process oldest first.
  pending.sort((a, b) => a.enqueuedAt - b.enqueuedAt);

  // Purge stale entries before recovery to prevent retry storms from old backlog.
  const purgeNow = Date.now();
  let purgeIdx = 0;
  while (purgeIdx < pending.length && purgeNow - pending[purgeIdx].enqueuedAt > MAX_ENTRY_AGE_MS) {
    purgeIdx++;
  }
  if (purgeIdx > 0) {
    const staleEntries = pending.splice(0, purgeIdx);
    let purged = 0;
    for (const entry of staleEntries) {
      try {
        await moveToFailed(entry.id, opts.stateDir);
        purged++;
      } catch {
        // Best effort — entry may already be moved or deleted.
      }
    }
    opts.log.info(
      `Purged ${purged} stale delivery entries (age > ${MAX_ENTRY_AGE_MS / 60_000}m)`,
    );
  }

  if (pending.length === 0) {
    return { recovered: 0, failed: 0, skipped: purgeIdx };
  }

  opts.log.info(`Found ${pending.length} pending delivery entries — starting recovery`);

  const delayFn = opts.delay ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  const deadline = Date.now() + (opts.maxRecoveryMs ?? DEFAULT_MAX_RECOVERY_MS);

  let recovered = 0;
  let failed = 0;
  let skipped = 0;
  let deferred = 0;
  const fastDrainMode = pending.length >= RECOVERY_FAST_DRAIN_THRESHOLD;

  if (fastDrainMode) {
    opts.log.info(
      `Recovery fast-drain mode enabled for ${pending.length} entries (startup backlog)` +
        ` — per-entry backoff waits are skipped`,
    );
  }

  for (let idx = 0; idx < pending.length; idx += 1) {
    const entry = pending[idx];
    const now = Date.now();
    if (now >= deadline) {
      deferred = pending.length - idx;
      opts.log.warn(`Recovery time budget exceeded — ${deferred} entries deferred to next restart`);
      break;
    }
    if (entry.retryCount >= MAX_RETRIES) {
      opts.log.warn(
        `Delivery ${entry.id} exceeded max retries (${entry.retryCount}/${MAX_RETRIES}) — moving to failed/`,
      );
      try {
        await moveToFailed(entry.id, opts.stateDir);
      } catch (err) {
        opts.log.error(`Failed to move entry ${entry.id} to failed/: ${String(err)}`);
      }
      skipped += 1;
      continue;
    }

    const backoff = computeBackoffMs(entry.retryCount + 1);
    const cappedBackoff = fastDrainMode ? 0 : Math.min(backoff, RECOVERY_BACKOFF_CAP_MS);
    if (cappedBackoff > 0) {
      if (now + cappedBackoff >= deadline) {
        deferred = pending.length - idx;
        opts.log.warn(
          `Recovery time budget exceeded — ${deferred} entries deferred to next restart`,
        );
        break;
      }
      opts.log.info(`Waiting ${cappedBackoff}ms before retrying delivery ${entry.id}`);
      await delayFn(cappedBackoff);
    }

    try {
      await opts.deliver({
        cfg: opts.cfg,
        channel: entry.channel,
        to: entry.to,
        accountId: entry.accountId,
        payloads: entry.payloads,
        threadId: entry.threadId,
        replyToId: entry.replyToId,
        bestEffort: entry.bestEffort,
        gifPlayback: entry.gifPlayback,
        silent: entry.silent,
        mirror: entry.mirror,
        skipQueue: true, // Prevent re-enqueueing during recovery
      });
      await ackDelivery(entry.id, opts.stateDir);
      recovered += 1;
      opts.log.info(`Recovered delivery ${entry.id} to ${entry.channel}:${entry.to}`);
    } catch (err) {
      try {
        await failDelivery(
          entry.id,
          err instanceof Error ? err.message : String(err),
          opts.stateDir,
        );
      } catch {
        // Best-effort update.
      }
      failed += 1;
      opts.log.warn(
        `Retry failed for delivery ${entry.id}: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  }

  opts.log.info(
    `Delivery recovery complete: ${recovered} recovered, ${failed} failed, ${skipped} skipped (max retries), ${deferred} deferred`,
  );
  return { recovered, failed, skipped };
}

export { MAX_RETRIES };
