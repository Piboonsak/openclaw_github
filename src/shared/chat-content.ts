function resolveTextLikeBlockValue(block: Record<string, unknown>): string | null {
  const directText = block.text;
  if (typeof directText === "string") {
    return directText;
  }

  if (directText && typeof directText === "object") {
    const nestedValue = (directText as { value?: unknown }).value;
    if (typeof nestedValue === "string") {
      return nestedValue;
    }
  }

  const inputText = block.input_text;
  if (typeof inputText === "string") {
    return inputText;
  }

  const outputText = block.output_text;
  if (typeof outputText === "string") {
    return outputText;
  }

  return null;
}

export function extractTextFromChatContent(
  content: unknown,
  opts?: {
    sanitizeText?: (text: string) => string;
    joinWith?: string;
    normalizeText?: (text: string) => string;
  },
): string | null {
  const normalize = opts?.normalizeText ?? ((text: string) => text.replace(/\s+/g, " ").trim());
  const joinWith = opts?.joinWith ?? " ";

  if (typeof content === "string") {
    const value = opts?.sanitizeText ? opts.sanitizeText(content) : content;
    const normalized = normalize(value);
    return normalized ? normalized : null;
  }

  if (!Array.isArray(content)) {
    return null;
  }

  const chunks: string[] = [];
  for (const block of content) {
    if (!block || typeof block !== "object") {
      continue;
    }
    const record = block as Record<string, unknown>;
    const type = record.type;
    if (type !== "text" && type !== "input_text" && type !== "output_text") {
      continue;
    }
    const text = resolveTextLikeBlockValue(record);
    if (typeof text !== "string") {
      continue;
    }
    const value = opts?.sanitizeText ? opts.sanitizeText(text) : text;
    if (value.trim()) {
      chunks.push(value);
    }
  }

  const joined = normalize(chunks.join(joinWith));
  return joined ? joined : null;
}
