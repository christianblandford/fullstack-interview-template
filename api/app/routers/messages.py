import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.message import MessageCreate, MessageResponse, Source, Usage
from app.services.openai import aclient as openai_client
from app.services.rag import rag_service
from app.services import github
from app.store import store

router = APIRouter(prefix="/conversations/{conversation_id}/messages", tags=["messages"])

SYSTEM_PROMPT = """You are a helpful assistant for Acme Corp with access to four tools:

1. search_knowledge_base — search internal engineering docs (architecture, auth, 
   rate limiting, data pipeline, deployment, incidents, frontend performance).
   Use this for any question about how Acme's systems work.

2. search_github_repos — search GitHub for open-source libraries and tools.
3. get_github_file_content — read a specific file from a GitHub repository.
4. search_files_in_repo — search for specific code or filenames within a given GitHub repository.

Always cite which document or source your answer came from.
If a question touches both internal docs and open-source tools, use both tools."""

# ---------------------------------------------------------------------------
# Tool schemas (OpenAI function calling format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Semantic search over Acme Corp's internal engineering documentation. "
                "Use for questions about authentication, rate limiting, architecture, "
                "deployments, incidents, data pipelines, and frontend performance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query — phrase it as a question or keywords",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_github_repos",
            "description": (
                "Search GitHub for open-source repositories by keyword. "
                "Use when the user asks about libraries, tools, or OSS alternatives."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search keywords, e.g. 'python rate limiting library'",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Number of results to return (default 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_github_file_content",
            "description": (
                "Read the contents of a specific file in a GitHub repository. "
                "Use this to fetch READMEs or source files after finding repos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner, e.g. 'pallets'",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name, e.g. 'flask'",
                    },
                    "path": {
                        "type": "string",
                        "description": "File path within the repo, e.g. 'README.md'",
                    },
                },
                "required": ["owner", "repo", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files_in_repo",
            "description": (
                "Search for specific code or filenames within a given GitHub repository. "
                "Use this when you know the repo (owner/name) but need to find where "
                "specific logic or files are located."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "Repo owner (e.g. 'openai')"},
                    "repo": {"type": "string", "description": "Repo name (e.g. 'openai-python')"},
                    "query": {"type": "string", "description": "Code or filename keywords"},
                },
                "required": ["owner", "repo", "query"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

async def _execute_tool(name: str, args: dict) -> str:
    """
    Run the requested tool and return its result as a JSON string.
    This is what gets fed back to the LLM as a tool result message.
    """
    try:
        if name == "search_knowledge_base":
            results = await rag_service.retrieve(args["query"])
            formatted = []
            for r in results:
                formatted.append(
                    f"[{r['source_file']} — {r['header_path']}]\n{r['text']}"
                )
            return json.dumps({"results": formatted})

        elif name == "search_github_repos":
            results = await github.search_repos(
                query=args["query"],
                per_page=args.get("per_page", 5),
            )
            return json.dumps({"repos": results})

        elif name == "search_files_in_repo":
            results = await github.search_files(
                owner=args["owner"],
                repo=args["repo"],
                query=args["query"]
            )
            return json.dumps({"found_files": results})

        elif name == "get_github_file_content":
            result = await github.get_file_content(
                owner=args["owner"],
                repo=args["repo"],
                path=args["path"],
            )
            content = result["content"]
            if len(content) > 8000:
                content = content[:8000] + "\n\n[... truncated ...]"
            return json.dumps({"file": result["path"], "content": content})

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[MessageResponse])
async def list_messages(conversation_id: str):
    if not store.get_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return store.list_messages(conversation_id)


@router.post("")
async def send_message(conversation_id: str, payload: MessageCreate):
    """
    Accepts a user message and returns an SSE stream.

    SSE event types:
      - tool_call:  a tool is being executed  (data = {"name": str, "args": dict})
      - token:      partial text chunk         (data = string)
      - done:       final saved message        (data = MessageResponse JSON)
      - error:      something went wrong       (data = string)
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
        agent_messages = list(messages)
        loop_iteration = 0
        all_tool_calls = []
        all_sources = []
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        print("\n" + "="*60)
        print(f"[AGENT] New request: {payload.content!r}")
        print("="*60)

        try:
            # ----------------------------------------------------------
            # Step 1: Agentic loop — resolve all tool calls first
            # ----------------------------------------------------------
            while True:
                loop_iteration += 1
                print(f"\n[AGENT] Loop iteration {loop_iteration}")
                print(f"[AGENT] Sending {len(agent_messages)} messages to LLM")

                response = await openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=agent_messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    stream=False,
                )

                if response.usage:
                    total_usage["prompt_tokens"] += response.usage.prompt_tokens
                    total_usage["completion_tokens"] += response.usage.completion_tokens
                    total_usage["total_tokens"] += response.usage.total_tokens

                assistant_msg = response.choices[0].message
                finish_reason = response.choices[0].finish_reason

                print(f"[AGENT] Finish reason: {finish_reason}")

                # No tool calls — LLM is ready to give the final answer
                if not assistant_msg.tool_calls:
                    print("[AGENT] No tool calls — proceeding to final answer")
                    break

                print(f"[AGENT] LLM wants to call {len(assistant_msg.tool_calls)} tool(s)")

                # Append the assistant's decision to the message history
                agent_messages.append(assistant_msg.to_dict())

                # Execute each tool call
                for tool_call in assistant_msg.tool_calls:
                    name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    print(f"\n[TOOL] Calling: {name}")
                    print(f"[TOOL] Args: {json.dumps(args, indent=2)}")

                    # Tell the frontend which tool is running
                    tool_call_data = {"name": name, "args": args}
                    all_tool_calls.append(tool_call_data)
                    yield _sse("tool_call", json.dumps(tool_call_data))
                    await asyncio.sleep(0)

                    result = await _execute_tool(name, args)
                    result_data = json.loads(result)

                    # Log a summary of the result (not the full content — can be huge)
                    if "results" in result_data:
                        print(f"[TOOL] RAG returned {len(result_data['results'])} chunks")
                        # Also collect sources for the UI
                        sources = await rag_service.retrieve(args["query"])
                        for s in sources:
                            new_source = Source(
                                document=s["source_file"],
                                chunk=s["text"],
                                score=s["score"]
                            )
                            all_sources.append(new_source)
                        
                        yield _sse("sources", json.dumps([s.model_dump() for s in all_sources]))
                        await asyncio.sleep(0)
                    elif "repos" in result_data:
                        repos = [r["full_name"] for r in result_data["repos"]]
                        print(f"[TOOL] GitHub returned repos: {repos}")
                    elif "file" in result_data:
                        content_len = len(result_data.get("content", ""))
                        print(f"[TOOL] File content: {result_data['file']} ({content_len} chars)")
                    elif "error" in result_data:
                        print(f"[TOOL] Error: {result_data['error']}")

                    # Feed result back into the conversation
                    agent_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

                    print(f"[TOOL] Result fed back into context")

            # ----------------------------------------------------------
            # Step 2: Stream the final answer token-by-token
            # ----------------------------------------------------------
            print(f"\n[AGENT] Starting final streaming response")
            print(f"[AGENT] Total messages in context: {len(agent_messages)}")

            stream = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=agent_messages,
                stream=True,
                stream_options={"include_usage": True},
            )

            token_count = 0
            async for chunk in stream:
                # Usage chunk (only for gpt-4o models when stream_options={"include_usage": True})
                if chunk.usage:
                    total_usage["prompt_tokens"] += chunk.usage.prompt_tokens
                    total_usage["completion_tokens"] += chunk.usage.completion_tokens
                    total_usage["total_tokens"] += chunk.usage.total_tokens
                    yield _sse("usage", json.dumps(total_usage))

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                if delta.content:
                    full_content += delta.content
                    token_count += 1
                    yield _sse("token", json.dumps(delta.content))
                    await asyncio.sleep(0)

            print(f"[AGENT] Stream complete — {token_count} chunks, {len(full_content)} chars")

            assistant_message = store.add_message(
                conversation_id,
                role="assistant",
                content=full_content,
                sources=all_sources,
                tool_calls=all_tool_calls,
                usage=total_usage,
            )

            print(f"[AGENT] Message saved to store")
            print("="*60 + "\n")

            yield _sse("done", assistant_message.model_dump_json())

        except Exception as exc:
            print(f"[AGENT] ERROR: {exc}")
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