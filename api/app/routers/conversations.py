from fastapi import APIRouter, HTTPException

from app.models.conversation import ConversationCreate, ConversationResponse
from app.store import store

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationResponse])
async def list_conversations():
    return store.list_conversations()


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(payload: ConversationCreate | None = None):
    title = payload.title if payload else None
    return store.create_conversation(title=title)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str):
    conversation = store.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str):
    if not store.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
