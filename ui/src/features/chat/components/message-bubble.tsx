import { Bot, Coins, User, Wrench } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import type { Message } from "../types";
import { Markdown } from "@/components/markdown";

type MessageBubbleProps = {
  message: Message;
};

function CitationsList({ 
  sources, 
  toolCalls 
}: { 
  sources: Message["sources"], 
  toolCalls: Message["tool_calls"] 
}) {
  const hasSources = sources && sources.length > 0;
  const hasTools = toolCalls && toolCalls.length > 0;

  if (!hasSources && !hasTools) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {hasTools && toolCalls.map((tool, i) => (
        <span
          key={`tool-${i}`}
          className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-1 text-[0.65rem] font-medium text-primary border border-primary/20"
        >
          <Wrench className="size-2.5" />
          {tool.name}
          {tool.args.query && (
            <span className="opacity-70 font-normal">: {tool.args.query}</span>
          )}
        </span>
      ))}
      {hasSources && sources.map((source, i) => (
        <span
          key={`src-${i}`}
          className="inline-flex items-center rounded-md bg-muted px-2 py-1 text-[0.65rem] text-muted-foreground border border-muted-foreground/20"
        >
          {source.document}
        </span>
      ))}
    </div>
  );
}

function UsageBanner({ usage }: { usage?: Message["usage"] }) {
  if (!usage) return null;

  return (
    <div className="mt-2.5 flex items-center gap-3 text-[10px] text-muted-foreground/60 border-t border-muted-foreground/5 pt-2">
      <div className="flex items-center gap-1">
        <Coins className="size-2.5" />
        <span className="font-medium uppercase tracking-wider">Usage</span>
      </div>
      <div className="flex gap-2.5">
        <span>Prompt: <span className="text-muted-foreground">{usage.prompt_tokens}</span></span>
        <span>Completion: <span className="text-muted-foreground">{usage.completion_tokens}</span></span>
        <span className="font-medium">Total: <span className="text-muted-foreground">{usage.total_tokens}</span></span>
      </div>
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
    >
      <Avatar className="mt-0.5 size-7 shrink-0">
        <AvatarFallback
          className={cn(
            "text-xs",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground",
          )}
        >
          {isUser ? <User className="size-3.5" /> : <Bot className="size-3.5" />}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-xs border",
          isUser
            ? "bg-linear-to-br from-primary to-primary/80 text-primary-foreground border-primary/20"
            : "bg-background text-foreground border-border/50",
        )}
      >
        <Markdown content={message.content} isUser={isUser} />
        {!isUser && (
          <CitationsList 
            sources={message.sources} 
            toolCalls={message.tool_calls} 
          />
        )}
        {!isUser && <UsageBanner usage={message.usage} />}
      </div>
    </div>
  );
}
