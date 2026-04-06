import fs from "node:fs";
import type { OpenClawConfig } from "openclaw/plugin-sdk";
import {
  DEFAULT_ACCOUNT_ID,
  normalizeAccountId as normalizeSharedAccountId,
} from "openclaw/plugin-sdk/account-id";
import type {
  LineAccountConfig,
  LineConfig,
  LineTokenSource,
  ResolvedLineAccount,
} from "./types.js";

export { DEFAULT_ACCOUNT_ID } from "openclaw/plugin-sdk/account-id";

function readFileIfExists(filePath: string | undefined): string | undefined {
  if (!filePath) {
    return undefined;
  }
  try {
    return fs.readFileSync(filePath, "utf-8").trim();
  } catch {
    return undefined;
  }
}

function resolveToken(params: {
  accountId: string;
  baseConfig?: LineConfig;
  accountConfig?: LineAccountConfig;
}): { token: string; tokenSource: LineTokenSource } {
  const { accountId, baseConfig, accountConfig } = params;

  if (accountConfig?.channelAccessToken?.trim()) {
    return { token: accountConfig.channelAccessToken.trim(), tokenSource: "config" };
  }

  const accountFileToken = readFileIfExists(accountConfig?.tokenFile);
  if (accountFileToken) {
    return { token: accountFileToken, tokenSource: "file" };
  }

  if (accountId === DEFAULT_ACCOUNT_ID) {
    if (baseConfig?.channelAccessToken?.trim()) {
      return { token: baseConfig.channelAccessToken.trim(), tokenSource: "config" };
    }

    const baseFileToken = readFileIfExists(baseConfig?.tokenFile);
    if (baseFileToken) {
      return { token: baseFileToken, tokenSource: "file" };
    }

    const envToken = process.env.LINE_CHANNEL_ACCESS_TOKEN?.trim();
    if (envToken) {
      return { token: envToken, tokenSource: "env" };
    }
  }

  return { token: "", tokenSource: "none" };
}

function resolveSecret(params: {
  accountId: string;
  baseConfig?: LineConfig;
  accountConfig?: LineAccountConfig;
}): string {
  const { accountId, baseConfig, accountConfig } = params;

  if (accountConfig?.channelSecret?.trim()) {
    return accountConfig.channelSecret.trim();
  }

  const accountFileSecret = readFileIfExists(accountConfig?.secretFile);
  if (accountFileSecret) {
    return accountFileSecret;
  }

  if (accountId === DEFAULT_ACCOUNT_ID) {
    if (baseConfig?.channelSecret?.trim()) {
      return baseConfig.channelSecret.trim();
    }

    const baseFileSecret = readFileIfExists(baseConfig?.secretFile);
    if (baseFileSecret) {
      return baseFileSecret;
    }

    const envSecret = process.env.LINE_CHANNEL_SECRET?.trim();
    if (envSecret) {
      return envSecret;
    }
  }

  return "";
}

export function resolveLineAccount(params: {
  cfg: OpenClawConfig;
  accountId?: string;
}): ResolvedLineAccount {
  const { cfg, accountId = DEFAULT_ACCOUNT_ID } = params;
  const lineConfig = cfg.channels?.line as LineConfig | undefined;
  const accounts = lineConfig?.accounts;
  const accountConfig = accountId !== DEFAULT_ACCOUNT_ID ? accounts?.[accountId] : undefined;

  const { token, tokenSource } = resolveToken({
    accountId,
    baseConfig: lineConfig,
    accountConfig,
  });

  const secret = resolveSecret({
    accountId,
    baseConfig: lineConfig,
    accountConfig,
  });

  const mergedConfig: LineConfig & LineAccountConfig = {
    ...lineConfig,
    ...accountConfig,
  };

  const enabled =
    accountConfig?.enabled ??
    (accountId === DEFAULT_ACCOUNT_ID ? (lineConfig?.enabled ?? true) : false);

  const name =
    accountConfig?.name ?? (accountId === DEFAULT_ACCOUNT_ID ? lineConfig?.name : undefined);

  return {
    accountId,
    name,
    enabled,
    channelAccessToken: token,
    channelSecret: secret,
    tokenSource,
    config: mergedConfig,
  };
}

export function listLineAccountIds(cfg: OpenClawConfig): string[] {
  const lineConfig = cfg.channels?.line as LineConfig | undefined;
  const accounts = lineConfig?.accounts;
  const ids = new Set<string>();

  if (
    lineConfig?.channelAccessToken?.trim() ||
    lineConfig?.tokenFile ||
    process.env.LINE_CHANNEL_ACCESS_TOKEN?.trim()
  ) {
    ids.add(DEFAULT_ACCOUNT_ID);
  }

  if (accounts) {
    for (const id of Object.keys(accounts)) {
      ids.add(id);
    }
  }

  return Array.from(ids);
}

export function resolveDefaultLineAccountId(cfg: OpenClawConfig): string {
  const ids = listLineAccountIds(cfg);
  if (ids.includes(DEFAULT_ACCOUNT_ID)) {
    return DEFAULT_ACCOUNT_ID;
  }
  return ids[0] ?? DEFAULT_ACCOUNT_ID;
}

export function normalizeAccountId(accountId: string | undefined): string {
  return normalizeSharedAccountId(accountId);
}
