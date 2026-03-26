import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { cn } from "@/lib/utils";

type MarkdownProps = {
  content: string;
  isUser?: boolean;
};

export function Markdown({ content, isUser }: MarkdownProps) {
  return (
    <div className={cn(
      "prose prose-sm max-w-none dark:prose-invert prose-p:leading-relaxed prose-pre:p-0",
      isUser ? "prose-headings:text-primary-foreground prose-strong:text-primary-foreground prose-code:text-primary-foreground text-primary-foreground" : "text-foreground"
    )}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || "");
            return !inline && match ? (
              <SyntaxHighlighter
                style={oneDark}
                language={match[1]}
                PreTag="div"
                className="rounded-lg !my-2 !bg-zinc-900/90"
                {...props}
              >
                {String(children).replace(/\n$/, "")}
              </SyntaxHighlighter>
            ) : (
              <code
                className={cn(
                  "rounded-md px-1.5 py-0.5 font-mono text-xs font-medium",
                  isUser ? "bg-primary-foreground/20 text-primary-foreground font-semibold" : "bg-muted text-foreground"
                )}
                {...props}
              >
                {children}
              </code>
            );
          },
          table({ children }) {
            return (
              <div className="my-4 overflow-x-auto rounded-lg border border-border/50 shadow-xs">
                <table className="w-full text-left text-xs border-collapse">
                  {children}
                </table>
              </div>
            );
          },
          thead({ children }) {
            return <thead className="bg-muted/50 font-semibold">{children}</thead>;
          },
          th({ children }) {
            return <th className="px-4 py-2 border-b border-border/50">{children}</th>;
          },
          td({ children }) {
            return <td className="px-4 py-2 border-b border-border/50 last:border-0">{children}</td>;
          },
          p({ children }) {
            return <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>;
          },
          ul({ children }) {
            return <ul className="mb-4 ml-4 list-disc space-y-1">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="mb-4 ml-4 list-decimal space-y-1">{children}</ol>;
          },
          li({ children }) {
            return <li className="pl-1 italic:not-prose">{children}</li>;
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-4 border-l-4 border-primary/30 pl-4 italic opacity-80">
                {children}
              </blockquote>
            );
          },
          h1({ children }) { return <h1 className="text-xl font-bold mb-4 mt-2">{children}</h1> },
          h2({ children }) { return <h2 className="text-lg font-bold mb-3 mt-2">{children}</h2> },
          h3({ children }) { return <h3 className="text-md font-bold mb-2 mt-1">{children}</h3> },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
