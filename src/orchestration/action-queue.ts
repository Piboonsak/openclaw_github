import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";

export type OutboundActionStatus = "PENDING" | "SENT" | "FAILED";

export interface OutboundAction {
  actionId: string;
  jobId: string;
  type: "WORKFLOW_DISPATCH" | "ISSUE_ASSIGN" | "PR_REVIEW" | "PR_MERGE";
  status: OutboundActionStatus;
  persistedAt: string;
  sentAt?: string;
  payload: Record<string, unknown>;
}

export class FileActionQueue {
  private readonly outboundDir: string;

  constructor(baseDir: string) {
    this.outboundDir = path.join(baseDir, "outbound");
  }

  async ensureReady(): Promise<void> {
    await mkdir(this.outboundDir, { recursive: true });
  }

  async persistPending(action: OutboundAction): Promise<void> {
    await this.ensureReady();
    const basePath = this.getPath(action.actionId);
    const tempPath = `${basePath}.tmp`;
    const payload = {
      ...action,
      status: "PENDING" as const,
      persistedAt: action.persistedAt,
      sentAt: undefined,
    };
    await writeFile(tempPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    await rename(tempPath, basePath);
  }

  async markSent(actionId: string, sentAt: string): Promise<void> {
    const current = await this.get(actionId);
    if (!current) {
      return;
    }
    current.status = "SENT";
    current.sentAt = sentAt;
    await this.write(current);
  }

  async markFailed(actionId: string): Promise<void> {
    const current = await this.get(actionId);
    if (!current) {
      return;
    }
    current.status = "FAILED";
    await this.write(current);
  }

  async get(actionId: string): Promise<OutboundAction | undefined> {
    try {
      const raw = await readFile(this.getPath(actionId), "utf8");
      return JSON.parse(raw) as OutboundAction;
    } catch {
      return undefined;
    }
  }

  private async write(action: OutboundAction): Promise<void> {
    const basePath = this.getPath(action.actionId);
    const tempPath = `${basePath}.tmp`;
    await writeFile(tempPath, `${JSON.stringify(action, null, 2)}\n`, "utf8");
    await rename(tempPath, basePath);
  }

  private getPath(actionId: string): string {
    return path.join(this.outboundDir, `${actionId}.json`);
  }
}
