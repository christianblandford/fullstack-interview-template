import { useState } from "react";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { ChatSidebar } from "./chat-sidebar";
import { MessageInput } from "./message-input";
import { MessageList } from "./message-list";
import { useStreamMessage } from "../hooks/use-messages";
import { useCreateConversation } from "../hooks/use-conversations";

export function ChatLayout() {
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);

  const { send, isStreaming, streamingContent, streamingSources, streamingToolCalls, activeTool, streamingUsage } =
    useStreamMessage();
  const createConversation = useCreateConversation();

  const handleSend = async (content: string) => {
    let conversationId = activeConversationId;

    if (!conversationId) {
      const conversation = await createConversation.mutateAsync({
        title: content.slice(0, 50),
      });
      conversationId = conversation.id;
      setActiveConversationId(conversationId);
    }

    send(conversationId, content);
  };

  return (
    <SidebarProvider>
      <ChatSidebar
        activeConversationId={activeConversationId}
        onSelectConversation={setActiveConversationId}
      />
      <SidebarInset>
        <div className="flex h-svh flex-col">
          <MessageList
            conversationId={activeConversationId}
            streaming={{ isStreaming, streamingContent, streamingSources, streamingToolCalls, activeTool, streamingUsage }}
          />
          <MessageInput
            onSend={handleSend}
            disabled={isStreaming || createConversation.isPending}
          />
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
