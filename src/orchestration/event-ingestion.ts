export interface NormalizedGitHubEvent {
  deliveryId: string;
  eventType: string;
  action: string;
  repository?: string;
  issueNumber?: number;
  pullNumber?: number;
}

export function normalizeGitHubEvent(params: {
  headers: Record<string, string | string[] | undefined>;
  payload: Record<string, unknown>;
}): NormalizedGitHubEvent {
  const headerLookup = Object.fromEntries(
    Object.entries(params.headers).map(([k, v]) => [k.toLowerCase(), Array.isArray(v) ? v[0] : v]),
  );

  return {
    deliveryId: String(headerLookup["x-github-delivery"] ?? ""),
    eventType: String(headerLookup["x-github-event"] ?? "unknown"),
    action: String(params.payload.action ?? "unknown"),
    repository: (params.payload.repository as { full_name?: string } | undefined)?.full_name,
    issueNumber: (params.payload.issue as { number?: number } | undefined)?.number,
    pullNumber: (params.payload.pull_request as { number?: number } | undefined)?.number,
  };
}

export function shouldProcessDelivery(deliveryId: string, seenDeliveryIds: Set<string>): boolean {
  if (!deliveryId) {
    return true;
  }
  if (seenDeliveryIds.has(deliveryId)) {
    return false;
  }
  seenDeliveryIds.add(deliveryId);
  return true;
}
