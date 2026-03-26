export type MessageRole = "user" | "assistant";

export type Source = {
  document: string;
  chunk: string;
  score: number;
};

export type Usage = {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
};

export type Message = {
  id: string;
  role: MessageRole;
  content: string;
  sources?: Source[];
  tool_calls?: { name: string; args: Record<string, any> }[];
  usage?: Usage;
  created_at: string;
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type SendMessagePayload = {
  conversation_id: string;
  content: string;
};

export type CreateConversationPayload = {
  title?: string;
};

export type StreamEvents = {
  tool_call: { name: string; args: Record<string, any> };
  token: string;
  sources: Source[];
  usage: Usage;
  done: Message;
  error: string;
};
