import type {
  Assistant,
  Session,
  Run,
  RuntimeEvent,
  StateView,
  Comparison,
  Submission,
} from "./types";
import { isActive } from "./types";

export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
  ) {
    super(code.replaceAll("_", " "));
  }
}
export function normalizeUrl(value: string): string {
  const url = new URL(value);
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new Error(
      "Use an HTTP or HTTPS service URL without credentials, query parameters, or fragments.",
    );
  }
  return url.href.replace(/\/+$/, "");
}

// Parse SSE incrementally: a frame or UTF-8 character can span network chunks.
export async function* readEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<RuntimeEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const parse = (frame: string): RuntimeEvent | null => {
    const data = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).replace(/^ /, ""))
      .join("\n");
    if (!data) return null; // comments and heartbeats
    const event = JSON.parse(data) as RuntimeEvent;
    if (
      !Number.isSafeInteger(event.event_id) ||
      typeof event.kind !== "string" ||
      event.durable !== true
    )
      throw new Error("Invalid runtime event.");
    return event;
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done
        ? decoder.decode()
        : decoder.decode(value, { stream: true });
      let match: RegExpExecArray | null;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        const event = parse(frame);
        if (event) yield event;
      }
      if (done) break;
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(signal.reason);
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

export class RuntimeClient {
  readonly base: string;
  constructor(url: string) {
    this.base = normalizeUrl(url);
  }
  async request<T>(
    path: string,
    signal?: AbortSignal,
    body?: unknown,
  ): Promise<T> {
    const response = await fetch(this.base + path, {
      signal,
      credentials: "omit",
      method: body === undefined ? "GET" : "POST",
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const result = await response.json().catch(() => null);
      throw new ApiError(
        result?.error?.code ?? `http_${response.status}`,
        response.status,
      );
    }
    return response.json() as Promise<T>;
  }
  async connect(signal: AbortSignal): Promise<void> {
    const [info] = await Promise.all([
      this.request<{ protocol: string }>("/info", signal),
      this.request("/health", signal),
    ]);
    if (info.protocol !== "stocker-runtime-v1")
      throw new Error("This service does not support the Stocker runtime API.");
  }
  // UUID pagination uses IDs, not timestamps; sort only after all pages arrive.
  async records<T>(
    path: string,
    key: keyof T,
    signal?: AbortSignal,
  ): Promise<T[]> {
    const result: T[] = [];
    let after = "";
    while (true) {
      const page = await this.request<T[]>(
        `${path}?limit=200${after ? `&after=${encodeURIComponent(after)}` : ""}`,
        signal,
      );
      result.push(...page);
      if (page.length < 200) return result;
      const cursor = String(page.at(-1)![key]);
      if (cursor === after)
        throw new Error("The service returned a repeated pagination cursor.");
      after = cursor;
    }
  }
  graphs(signal?: AbortSignal) {
    return this.request<string[]>("/api/graphs", signal);
  }
  assistants(signal?: AbortSignal) {
    return this.records<Assistant>("/api/assistants", "assistant_id", signal);
  }
  sessions(signal?: AbortSignal) {
    return this.records<Session>("/api/sessions", "session_id", signal);
  }
  runs(id: string, signal?: AbortSignal) {
    return this.records<Run>(`/api/sessions/${id}/runs`, "run_id", signal);
  }
  run(id: string, signal?: AbortSignal) {
    return this.request<Run>(`/api/runs/${id}`, signal);
  }
  state(id: string, signal?: AbortSignal) {
    return this.request<StateView>(`/api/sessions/${id}/state`, signal);
  }
  checkpoint(id: string, checkpoint: string, signal?: AbortSignal) {
    return this.request<StateView>(
      `/api/sessions/${id}/checkpoints/${encodeURIComponent(checkpoint)}`,
      signal,
    );
  }
  compare(id: string, left: string, right: string, signal?: AbortSignal) {
    return this.request<Comparison>(
      `/api/sessions/${id}/checkpoints/compare?left=${encodeURIComponent(left)}&right=${encodeURIComponent(right)}`,
      signal,
    );
  }
  async checkpoints(id: string, signal?: AbortSignal): Promise<StateView[]> {
    const result: StateView[] = [];
    let before = "";
    while (true) {
      const page = await this.request<StateView[]>(
        `/api/sessions/${id}/checkpoints?limit=200${before ? `&before=${encodeURIComponent(before)}` : ""}`,
        signal,
      );
      result.push(...page);
      if (page.length < 200) return result;
      const cursor = page.at(-1)?.checkpoint_id;
      if (!cursor || cursor === before)
        throw new Error("The service returned an invalid checkpoint cursor.");
      before = cursor;
    }
  }
  async events(id: string, signal?: AbortSignal): Promise<RuntimeEvent[]> {
    const result: RuntimeEvent[] = [];
    let after = 0;
    while (true) {
      const page = await this.request<RuntimeEvent[]>(
        `/api/sessions/${id}/events?after=${after}&limit=200`,
        signal,
      );
      result.push(...page);
      if (page.length < 200) return result;
      const cursor = page.at(-1)!.event_id;
      if (cursor <= after)
        throw new Error("The service returned an invalid event cursor.");
      after = cursor;
    }
  }
  createAssistant(graph: string) {
    return this.request<Assistant>("/api/assistants", undefined, {
      graph_id: graph,
      name: graph,
    });
  }
  createSession(assistant: string, title: string) {
    return this.request<Session>("/api/sessions", undefined, {
      assistant_id: assistant,
      title,
    });
  }
  submit(id: string, body: Submission) {
    return this.request<Run>(`/api/sessions/${id}/runs`, undefined, body);
  }
  cancel(id: string) {
    return this.request<Run>(`/api/runs/${id}/cancel`, undefined, {});
  }
  async observe(
    id: string,
    after: number,
    signal: AbortSignal,
    onEvent: (event: RuntimeEvent) => void,
    onConnection: (status: string) => void,
  ): Promise<void> {
    let cursor = after;
    let attempts = 0;
    while (!signal.aborted) {
      try {
        const response = await fetch(
          `${this.base}/api/runs/${id}/events/stream?after=${cursor}`,
          {
            signal,
            credentials: "omit",
            headers: { Accept: "text/event-stream" },
          },
        );
        if (!response.ok)
          throw new ApiError(
            (await response.json()).error?.code ?? "stream_failed",
            response.status,
          );
        if (
          !response.body ||
          !response.headers.get("content-type")?.includes("text/event-stream")
        )
          throw new Error("The service returned an invalid event stream.");
        onConnection("Live");
        attempts = 0;
        for await (const event of readEvents(response.body)) {
          if (event.run_id !== id)
            throw new Error("The stream returned an event from another run.");
          if (event.event_id <= cursor) continue;
          onEvent(event);
          cursor = event.event_id;
        }
        if (!isActive(await this.run(id, signal))) {
          onConnection("Saved");
          return;
        }
      } catch (error) {
        if (signal.aborted) return;
        if (
          error instanceof ApiError &&
          error.status >= 400 &&
          error.status < 500
        )
          throw error;
      }
      onConnection("Reconnecting");
      await pause(Math.min(500 * 2 ** attempts++, 5000), signal);
    }
  }
}
