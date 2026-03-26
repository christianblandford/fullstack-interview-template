"""
In-memory store for conversations and messages.

TODO (candidate): Replace with a real database (e.g. SQLite, Postgres).
"""

import uuid
from datetime import datetime, timezone

from app.models.conversation import ConversationResponse
from app.models.message import MessageResponse, Source


class Store:
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationResponse] = {}
        self._messages: dict[str, list[MessageResponse]] = {}

    def create_conversation(self, title: str | None = None) -> ConversationResponse:
        now = datetime.now(timezone.utc)
        conversation = ConversationResponse(
            id=str(uuid.uuid4()),
            title=title or "New Chat",
            created_at=now,
            updated_at=now,
        )
        self._conversations[conversation.id] = conversation
        self._messages[conversation.id] = []
        return conversation

    def list_conversations(self) -> list[ConversationResponse]:
        return sorted(
            self._conversations.values(),
            key=lambda c: c.updated_at,
            reverse=True,
        )

    def get_conversation(self, conversation_id: str) -> ConversationResponse | None:
        return self._conversations.get(conversation_id)

    def delete_conversation(self, conversation_id: str) -> bool:
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            self._messages.pop(conversation_id, None)
            return True
        return False

    def list_messages(self, conversation_id: str) -> list[MessageResponse]:
        return self._messages.get(conversation_id, [])

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: list[Source] | None = None,
        tool_calls: list | None = None,
        usage: dict | None = None,
    ) -> MessageResponse:
        message = MessageResponse(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            sources=sources or [],
            tool_calls=tool_calls or [],
            usage=usage,
            created_at=datetime.now(timezone.utc),
        )
        self._messages.setdefault(conversation_id, []).append(message)

        if conv := self._conversations.get(conversation_id):
            self._conversations[conversation_id] = conv.model_copy(
                update={"updated_at": message.created_at}
            )

            if conv.title == "New Chat" and role == "user":
                self._conversations[conversation_id] = self._conversations[
                    conversation_id
                ].model_copy(update={"title": content[:50]})

        return message


store = Store()
