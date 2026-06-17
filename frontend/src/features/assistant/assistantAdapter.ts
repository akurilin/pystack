import type {
  ChatModelAdapter,
  ThreadAssistantMessagePart,
  ThreadMessage,
} from "@assistant-ui/react";

import { chatWithAssistant } from "../../api/generated/sdk.gen";

type AssistantAdapterOptions = {
  onTasksChanged: () => void | Promise<void>;
};

type AssistantStreamEvent =
  | { type: "text_delta"; text: string }
  | { type: "tasks_changed" }
  | { type: "error"; message: string }
  | { type: "done" };

export function createAssistantAdapter({
  onTasksChanged,
}: AssistantAdapterOptions): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }) {
      // Call the generated client with parseAs "stream" so it hands back the raw
      // ReadableStream instead of trying to parse the NDJSON body as JSON. Going
      // through the client (rather than a hand-rolled fetch) means its baseUrl and
      // auth interceptor apply, so the Clerk token is attached for us.
      const { data, error, response } = await chatWithAssistant({
        body: { messages: toRequestMessages(messages) },
        parseAs: "stream",
        signal: abortSignal,
      });

      if (abortSignal.aborted) {
        return;
      }
      if (error !== undefined || !response?.ok) {
        throw new Error(assistantErrorMessage(error, response?.status));
      }

      const stream = data as ReadableStream<Uint8Array> | null;
      if (stream === null) {
        throw new Error("Assistant response did not include a stream.");
      }

      let text = "";
      for await (const event of readAssistantEvents(stream)) {
        if (abortSignal.aborted) {
          return;
        }

        switch (event.type) {
          case "text_delta":
            text += event.text;
            yield { content: buildContent(text) };
            break;
          case "tasks_changed":
            await onTasksChanged();
            break;
          case "error":
            throw new Error(event.message);
          case "done":
            yield { content: buildContent(text) };
            return;
        }
      }
    },
  };
}

function toRequestMessages(messages: readonly ThreadMessage[]) {
  return messages
    .filter(
      (message) => message.role === "user" || message.role === "assistant",
    )
    .map((message) => ({
      role: message.role,
      content: message.content
        .filter((part) => part.type === "text")
        .map((part) => part.text)
        .join("\n")
        .trim(),
    }))
    .filter((message) => message.content !== "");
}

function buildContent(text: string): ThreadAssistantMessagePart[] {
  const content: ThreadAssistantMessagePart[] = [];
  if (text.trim() !== "") {
    content.push({ type: "text", text });
  }
  return content;
}

async function* readAssistantEvents(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<AssistantStreamEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed !== "") {
          yield parseAssistantEvent(trimmed);
        }
      }
    }

    const remaining = buffer.trim();
    if (remaining !== "") {
      yield parseAssistantEvent(remaining);
    }
  } finally {
    reader.releaseLock();
  }
}

function parseAssistantEvent(line: string): AssistantStreamEvent {
  const parsed = JSON.parse(line) as AssistantStreamEvent;
  return parsed;
}

// The client has already read the error body for us (FastAPI returns
// `{ "detail": "..." }`), so pull a message out of that rather than re-reading
// the consumed response.
function assistantErrorMessage(error: unknown, status?: number): string {
  if (typeof error === "string" && error !== "") {
    return error;
  }
  if (error && typeof error === "object" && "detail" in error) {
    const { detail } = error as { detail?: unknown };
    if (typeof detail === "string") {
      return detail;
    }
  }
  return status
    ? `Assistant request failed with HTTP ${status}.`
    : "Assistant request failed.";
}
