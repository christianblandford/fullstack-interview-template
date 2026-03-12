import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.message import MessageCreate, MessageResponse
from app.services.openai import client as openai_client
from app.store import store

router = APIRouter(prefix="/conversations/{conversation_id}/messages", tags=["messages"])

SYSTEM_PROMPT = "You are a helpful assistant. Be concise and clear."


@router.get("", response_model=list[MessageResponse])
async def list_messages(conversation_id: str):
    if not store.get_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return store.list_messages(conversation_id)


@router.post("")
async def send_message(conversation_id: str, payload: MessageCreate):
    """
    Accepts a user message, stores it, and returns an SSE stream
    with the assistant's response via OpenAI.

    SSE event types:
      - token:   partial text chunk  (data = string)
      - done:    final message       (data = MessageResponse)
      - error:   something went wrong (data = string)
    """
    if not store.get_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    store.add_message(conversation_id, role="user", content=payload.content)

    history = store.list_messages(conversation_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [
        {"role": m.role, "content": m.content} for m in history
    ]

    async def event_stream():
        full_content = ""
        try:
            stream = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_content += delta.content
                    yield _sse("token", json.dumps(delta.content))

            assistant_message = store.add_message(
                conversation_id,
                role="assistant",
                content=full_content,
            )
            yield _sse("done", assistant_message.model_dump_json())

        except Exception as exc:
            yield _sse("error", json.dumps(str(exc)))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"
