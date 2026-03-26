import { useCallback, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { chatApi } from "../api";
import type { Message, Source, Usage } from "../types";

const messagesKey = (conversationId: string) =>
  ["conversations", conversationId, "messages"] as const;

export function useMessages(conversationId: string | null) {
  return useQuery({
    queryKey: messagesKey(conversationId!),
    queryFn: () => chatApi.getMessages(conversationId!),
    enabled: !!conversationId,
  });
}

export type StreamingState = {
  isStreaming: boolean;
  streamingContent: string;
  streamingSources: Source[];
  activeTool?: { name: string; args: Record<string, any> };
  streamingToolCalls: { name: string; args: Record<string, any> }[];
  streamingUsage?: Usage;
};

export function useStreamMessage() {
  const queryClient = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);

  const [streamingState, setStreamingState] = useState<StreamingState>({
    isStreaming: false,
    streamingContent: "",
    streamingSources: [],
    streamingToolCalls: [],
    streamingUsage: undefined,
  });

  const send = useCallback(
    async (conversationId: string, content: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const key = messagesKey(conversationId);

      const optimisticUserMessage: Message = {
        id: `temp-user-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };

      queryClient.setQueryData<Message[]>(key, (old) => [
        ...(old ?? []),
        optimisticUserMessage,
      ]);

      setStreamingState({
        isStreaming: true,
        streamingContent: "",
        streamingSources: [],
        activeTool: undefined,
        streamingToolCalls: [],
        streamingUsage: undefined,
      });

      let accumulated = "";

      await chatApi.streamMessage(
        conversationId,
        content,
        {
          token: (char) => {
            console.log("SSE token:", char);
            accumulated += char;
            setStreamingState((prev) => ({
              ...prev,
              streamingContent: accumulated,
              activeTool: undefined,
            }));
          },
          sources: (sources) => {
            console.log("SSE sources:", sources);
            setStreamingState((prev) => ({
              ...prev,
              streamingSources: sources,
            }));
          },
          usage: (usage) => {
            console.log("SSE usage:", usage);
            setStreamingState((prev) => ({
              ...prev,
              streamingUsage: usage,
            }));
          },
          tool_call: (toolCall) => {
            console.log("SSE tool_call:", toolCall);
            setStreamingState((prev) => ({
              ...prev,
              activeTool: toolCall,
              streamingToolCalls: [...prev.streamingToolCalls, toolCall],
            }));
          },
          error: (errorMessage) => {
            console.error("Backend error:", errorMessage);
            setStreamingState((prev) => ({
              ...prev,
              isStreaming: false,
              activeTool: undefined,
            }));
            // Optionally handle this better (e.g. show toast)
          },
          done: (finalMessage) => {
            queryClient.setQueryData<Message[]>(key, (old) => {
              const withoutTemp = (old ?? []).filter(
                (m) => !m.id.startsWith("temp-"),
              );
              return [...withoutTemp, finalMessage];
            });
            setStreamingState({
              isStreaming: false,
              streamingContent: "",
              streamingSources: [],
              activeTool: undefined,
              streamingToolCalls: [],
              streamingUsage: undefined,
            });
            queryClient.invalidateQueries({ queryKey: ["conversations"] });
          },
          onError: (error) => {
            console.error("Stream error:", error);
            setStreamingState({
              isStreaming: false,
              streamingContent: "",
              streamingSources: [],
              streamingToolCalls: [],
              streamingUsage: undefined,
            });
          },
        },
        controller.signal,
      );
    },
    [queryClient],
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
    setStreamingState({
      isStreaming: false,
      streamingContent: "",
      streamingSources: [],
      streamingToolCalls: [],
      streamingUsage: undefined,
    });
  }, []);

  return { send, abort, ...streamingState };
}
