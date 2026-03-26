import { useEffect, useRef } from "react";
import { Bot, Coins, Wrench } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useMessages, type StreamingState } from "../hooks/use-messages";
import { MessageBubble } from "./message-bubble";
import { Markdown } from "@/components/markdown";

type MessageListProps = {
  conversationId: string | null;
  streaming: StreamingState;
};

function MessageListSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className={`flex gap-3 ${i % 2 === 0 ? "flex-row" : "flex-row-reverse"}`}
        >
          <Skeleton className="size-7 shrink-0 rounded-full" />
          <Skeleton
            className={`h-16 ${i % 2 === 0 ? "w-3/5" : "w-2/5"} rounded-xl`}
          />
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
      <p className="text-lg font-medium">Start a conversation</p>
      <p className="text-sm">
        Send a message to begin chatting with the AI assistant.
      </p>
    </div>
  );
}

function StreamingBubble({
  content,
  activeTool,
  sources = [],
  toolCalls = [],
  usage,
}: {
  content: string;
  activeTool?: { name: string; args: Record<string, any> };
  sources?: StreamingState["streamingSources"];
  toolCalls?: StreamingState["streamingToolCalls"];
  usage?: StreamingState["streamingUsage"];
}) {
  const hasSources = Array.isArray(sources) && sources.length > 0;
  const hasTools = (Array.isArray(toolCalls) && toolCalls.length > 0) || !!activeTool;

  return (
    <div className="flex gap-3">
      <Avatar className="mt-0.5 size-7 shrink-0">
        <AvatarFallback className="bg-muted text-xs text-muted-foreground border border-muted-foreground/10">
          <Bot className="size-3.5" />
        </AvatarFallback>
      </Avatar>
      <div className="max-w-[85%] space-y-2">
        <div className={cn(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed border bg-background text-foreground border-border/50 shadow-xs",
          !content && "bg-muted/50"
        )}>
          {content ? (
            <Markdown content={content} />
          ) : (
            <div className="flex gap-1 py-1">
              <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:0ms]" />
              <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:150ms]" />
              <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/50 [animation-delay:300ms]" />
            </div>
          )}
        </div>

        {(hasTools || hasSources) && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {toolCalls.map((tool, i) => (
              <span
                key={`streaming-tool-${i}`}
                className="inline-flex items-center gap-1 rounded-md bg-primary/5 px-2 py-1 text-[0.65rem] font-medium text-primary border border-primary/10"
              >
                <Wrench className="size-2.5" />
                {tool.name}
                {tool.args.query && (
                  <span className="opacity-70 font-normal">: {tool.args.query}</span>
                )}
              </span>
            ))}
            {activeTool && (
               <span
                key="active-tool"
                className="inline-flex items-center gap-1 rounded-md bg-primary/20 px-2 py-1 text-[0.65rem] font-medium text-primary border border-primary/30 animate-pulse"
              >
                <Wrench className="size-2.5" />
                Running {activeTool.name}...
              </span>
            )}
            {sources.map((source, i) => (
              <span
                key={`streaming-src-${i}`}
                className="inline-flex items-center rounded-md bg-muted px-2 py-1 text-[0.65rem] text-muted-foreground border border-muted-foreground/10"
              >
                {source.document}
              </span>
            ))}
          </div>
        )}

        {usage && (
          <div className="flex items-center gap-2 px-1 text-[10px] text-muted-foreground/60 animate-in fade-in">
            <Coins className="size-2.5" />
            <span>Tokens: {usage.total_tokens}</span>
            <span className="opacity-50">(P: {usage.prompt_tokens} + C: {usage.completion_tokens})</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function MessageList({ conversationId, streaming }: MessageListProps) {
  const { data: messages, isLoading } = useMessages(conversationId);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming.streamingContent]);

  if (!conversationId) {
    return <EmptyState />;
  }

  if (isLoading) {
    return <MessageListSkeleton />;
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4">
        {messages?.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {streaming.isStreaming && (
          <StreamingBubble
            content={streaming.streamingContent}
            activeTool={streaming.activeTool}
            sources={streaming.streamingSources}
            toolCalls={streaming.streamingToolCalls}
            usage={streaming.streamingUsage}
          />
        )}

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
