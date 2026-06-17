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
import { Bot, Send, Square, Wrench } from "lucide-react";
import { useCallback, useMemo } from "react";

import { listTasksQueryKey } from "../../api/generated/@tanstack/react-query.gen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
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
    <aside
      className="grid h-full min-h-[68vh] grid-rows-[auto_minmax(0,1fr)] overflow-hidden rounded-xl border border-border bg-card/90"
      aria-label="Task assistant"
    >
      <header className="border-b border-border/80 p-4">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
            Board assistant
          </p>
          <h2 className="text-base font-semibold">Ask the agent</h2>
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
    <ThreadPrimitive.Root className="min-h-0">
      <ThreadPrimitive.Viewport className="flex h-full flex-col overflow-y-auto p-4">
        <AssistantEmptyState />
        <div className="grid flex-1 content-end gap-3">
          <ThreadPrimitive.Messages>
            {() => <AssistantMessage />}
          </ThreadPrimitive.Messages>
        </div>
        <ThreadPrimitive.ViewportFooter className="sticky bottom-0 -mx-4 -mb-4 mt-4 border-t border-border/80 bg-card p-4">
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
    <div className="grid min-h-40 place-items-center text-muted-foreground">
      <div className="grid justify-items-center gap-2">
        <Bot className="size-5" />
        <h3 className="text-sm font-semibold">Ready</h3>
      </div>
    </div>
  );
}

function AssistantMessage() {
  const role = useMessage((message) => message.role);

  return (
    <MessagePrimitive.Root
      className={cn(
        "grid max-w-[92%] gap-2 [overflow-wrap:anywhere]",
        role === "user" ? "justify-self-end" : "justify-self-start",
      )}
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
  const role = useMessage((message) => message.role);

  return (
    <p
      className={cn(
        "m-0 whitespace-pre-wrap rounded-lg border px-3 py-2 text-sm leading-6",
        role === "user"
          ? "border-emerald-500/25 bg-emerald-500/10 text-foreground"
          : "border-border bg-muted/50 text-foreground",
      )}
    >
      {text}
    </p>
  );
}

function AssistantToolPart({
  toolName,
  args,
  result,
  isError,
}: ToolCallMessagePartProps<Record<string, unknown>, unknown>) {
  return (
    <div
      className={cn(
        "grid gap-2 rounded-lg border bg-background/50 p-3",
        isError ? "border-destructive/50" : "border-border",
      )}
    >
      <div className="flex items-center justify-between gap-3 text-xs font-semibold uppercase text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Wrench className="size-3" />
          {toolLabel(toolName)}
        </span>
        <Badge variant={isError ? "destructive" : "outline"}>
          {result === undefined ? "Running" : isError ? "Failed" : "Done"}
        </Badge>
      </div>
      <pre className="m-0 max-h-48 overflow-auto whitespace-pre-wrap text-xs leading-5 text-muted-foreground">
        {JSON.stringify(result ?? args, null, 2)}
      </pre>
    </div>
  );
}

function Composer() {
  const isRunning = useAuiState((state) => state.thread.isRunning);

  return (
    <ComposerPrimitive.Root className="grid gap-3">
      <ComposerPrimitive.Input
        aria-label="Message the board assistant"
        className="min-h-20 w-full resize-y rounded-lg border border-input bg-background/70 px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        placeholder="Message the assistant"
        rows={2}
      />
      <div className="flex justify-end">
        {isRunning ? (
          <ComposerPrimitive.Cancel asChild>
            <Button type="button" variant="destructive">
              <Square data-icon="inline-start" />
              Stop
            </Button>
          </ComposerPrimitive.Cancel>
        ) : (
          <ComposerPrimitive.Send asChild>
            <Button type="button">
              <Send data-icon="inline-start" />
              Send
            </Button>
          </ComposerPrimitive.Send>
        )}
      </div>
    </ComposerPrimitive.Root>
  );
}

function toolLabel(toolName: string) {
  return toolName.replaceAll("_", " ");
}
