import type {
  ChatModelAdapter,
  ThreadAssistantMessagePart,
  ThreadMessage,
  ToolCallMessagePart,
} from "@assistant-ui/react";
import type { ReadonlyJSONObject } from "assistant-stream/utils";

type AssistantAdapterOptions = {
  onTasksChanged: () => void | Promise<void>;
};

type AssistantStreamEvent =
  | { type: "text_delta"; text: string }
  | {
      type: "tool_call";
      id: string;
      name: string;
      args: ReadonlyJSONObject;
    }
  | {
      type: "tool_result";
      id: string;
      name: string;
      result: unknown;
      is_error: boolean;
      mutated: boolean;
    }
  | { type: "error"; message: string }
  | { type: "done" };

export function createAssistantAdapter({
  onTasksChanged,
}: AssistantAdapterOptions): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }) {
      const response = await fetch("/api/v1/assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: toRequestMessages(messages) }),
        signal: abortSignal,
      });

      if (!response.ok) {
        throw new Error(await responseErrorMessage(response));
      }
      if (response.body === null) {
        throw new Error("Assistant response did not include a stream.");
      }

      let text = "";
      const toolParts = new Map<
        string,
        ToolCallMessagePart<ReadonlyJSONObject, unknown>
      >();

      for await (const event of readAssistantEvents(response.body)) {
        if (abortSignal.aborted) {
          return;
        }

        switch (event.type) {
          case "text_delta":
            text += event.text;
            yield { content: buildContent(text, toolParts) };
            break;
          case "tool_call":
            toolParts.set(event.id, {
              type: "tool-call",
              toolCallId: event.id,
              toolName: event.name,
              args: event.args,
              argsText: JSON.stringify(event.args),
            });
            yield { content: buildContent(text, toolParts) };
            break;
          case "tool_result": {
            const previous = toolParts.get(event.id) ?? {
              type: "tool-call" as const,
              toolCallId: event.id,
              toolName: event.name,
              args: {},
              argsText: "{}",
            };
            toolParts.set(event.id, {
              ...previous,
              result: event.result,
              isError: event.is_error,
            });
            if (event.mutated) {
              await onTasksChanged();
            }
            yield { content: buildContent(text, toolParts) };
            break;
          }
          case "error":
            throw new Error(event.message);
          case "done":
            yield { content: buildContent(text, toolParts) };
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

function buildContent(
  text: string,
  toolParts: Map<string, ToolCallMessagePart<ReadonlyJSONObject, unknown>>,
): ThreadAssistantMessagePart[] {
  const content: ThreadAssistantMessagePart[] = [];
  if (text.trim() !== "") {
    content.push({ type: "text", text });
  }
  content.push(...toolParts.values());
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

async function responseErrorMessage(response: Response): Promise<string> {
  const text = await response.text();
  if (text === "") {
    return `Assistant request failed with HTTP ${response.status}.`;
  }

  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    return text;
  }

  return text;
}
