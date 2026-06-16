import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  type TextMessagePartProps,
  type ToolCallMessagePartProps,
  useAuiState,
  useLocalRuntime,
  useMessage,
} from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";

import { listTasksQueryKey } from "../../api/generated/@tanstack/react-query.gen";
import { createAssistantAdapter } from "./assistantAdapter";

export function AssistantPane() {
  const queryClient = useQueryClient();
  const refreshTasks = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: listTasksQueryKey() });
  }, [queryClient]);
  const adapter = useMemo(
    () => createAssistantAdapter({ onTasksChanged: refreshTasks }),
    [refreshTasks],
  );
  const runtime = useLocalRuntime(adapter);

  return (
    <aside className="assistant-pane" aria-label="Task assistant">
      <header className="assistant-pane__header">
        <div>
          <p className="eyebrow">Board assistant</p>
          <h2>Ask the agent</h2>
        </div>
      </header>
      <AssistantRuntimeProvider runtime={runtime}>
        <AssistantThread />
      </AssistantRuntimeProvider>
    </aside>
  );
}

function AssistantThread() {
  return (
    <ThreadPrimitive.Root className="assistant-thread">
      <ThreadPrimitive.Viewport className="assistant-thread__viewport">
        <AssistantEmptyState />
        <div className="assistant-messages">
          <ThreadPrimitive.Messages>
            {() => <AssistantMessage />}
          </ThreadPrimitive.Messages>
        </div>
        <ThreadPrimitive.ViewportFooter className="assistant-thread__footer">
          <Composer />
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function AssistantEmptyState() {
  const isEmpty = useAuiState((state) => state.thread.isEmpty);
  if (!isEmpty) {
    return null;
  }

  return (
    <div className="assistant-welcome">
      <h3>Ready</h3>
    </div>
  );
}

function AssistantMessage() {
  const role = useMessage((message) => message.role);

  return (
    <MessagePrimitive.Root
      className={`assistant-message assistant-message--${role}`}
    >
      <MessagePrimitive.Parts
        components={{
          Text: AssistantTextPart,
          tools: { Fallback: AssistantToolPart },
        }}
      />
    </MessagePrimitive.Root>
  );
}

function AssistantTextPart({ text }: TextMessagePartProps) {
  return <p>{text}</p>;
}

function AssistantToolPart({
  toolName,
  args,
  result,
  isError,
}: ToolCallMessagePartProps<Record<string, unknown>, unknown>) {
  return (
    <div className={`assistant-tool ${isError ? "assistant-tool--error" : ""}`}>
      <div className="assistant-tool__header">
        <span>{toolLabel(toolName)}</span>
        <span>
          {result === undefined ? "Running" : isError ? "Failed" : "Done"}
        </span>
      </div>
      <pre>{JSON.stringify(result ?? args, null, 2)}</pre>
    </div>
  );
}

function Composer() {
  const isRunning = useAuiState((state) => state.thread.isRunning);

  return (
    <ComposerPrimitive.Root className="assistant-composer">
      <ComposerPrimitive.Input
        aria-label="Message the board assistant"
        className="assistant-composer__input"
        placeholder="Message the assistant"
        rows={2}
      />
      <div className="assistant-composer__actions">
        {isRunning ? (
          <ComposerPrimitive.Cancel asChild>
            <button className="primary-button" type="button">
              Stop
            </button>
          </ComposerPrimitive.Cancel>
        ) : (
          <ComposerPrimitive.Send asChild>
            <button className="primary-button" type="button">
              Send
            </button>
          </ComposerPrimitive.Send>
        )}
      </div>
    </ComposerPrimitive.Root>
  );
}

function toolLabel(toolName: string) {
  return toolName.replaceAll("_", " ");
}
