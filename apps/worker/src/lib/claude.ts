import Anthropic from "@anthropic-ai/sdk";
import type { WorkerEnv } from "./env";

export const STEP_TIMEOUT_MS = 10 * 60 * 1000; // 10 min por step, conforme spec

export function createAnthropicClient(env: WorkerEnv): Anthropic {
  return new Anthropic({
    apiKey: env.ANTHROPIC_API_KEY,
    timeout: STEP_TIMEOUT_MS,
  });
}

export type ClaudeMessage = { role: "user" | "assistant"; content: string };

/** Chama o Claude e retorna o texto concatenado da resposta. */
export async function callClaude(
  client: Anthropic,
  env: WorkerEnv,
  options: {
    system: string;
    messages: ClaudeMessage[];
    maxTokens?: number;
  },
): Promise<string> {
  const response = await client.messages.create({
    model: env.ANTHROPIC_MODEL,
    max_tokens: options.maxTokens ?? 8192,
    system: options.system,
    messages: options.messages,
  });

  const text = response.content
    .filter((block): block is Anthropic.TextBlock => block.type === "text")
    .map((block) => block.text)
    .join("\n")
    .trim();

  if (!text) {
    throw new Error("O modelo retornou resposta vazia.");
  }
  return text;
}

/** Retry com backoff exponencial — 2 tentativas extras por step, conforme spec. */
export async function withRetries<T>(
  fn: () => Promise<T>,
  retries = 2,
  baseDelayMs = 2000,
): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt < retries) {
        const delay = baseDelayMs * 2 ** attempt;
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }
  throw lastError;
}
