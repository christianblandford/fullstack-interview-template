# Fullstack GenAI Interview Case

A chat application with a **React + Vite** frontend and a **FastAPI** backend, connected via **Server-Sent Events (SSE)** for real-time streaming. The app currently works as a simple ChatGPT-style wrapper around OpenAI — your task is to extend it with **RAG** and **tool calling**.

---

## Prerequisites

- **Node.js** >= 20 (recommend [nvm](https://github.com/nvm-sh/nvm))
- **Yarn** >= 4 (`corepack enable && yarn set version stable`)
- **Python** >= 3.12
- **Poetry** >= 2 ([install guide](https://python-poetry.org/docs/#installation))
- **OpenAI API key** — get one at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **GitHub PAT** — create one at [github.com/settings/tokens](https://github.com/settings/tokens) (needs `public_repo` scope)

Add both to `api/.env`:

```
OPENAI_API_KEY="sk-..."
GITHUB_ACCESS_TOKEN="ghp_..."
```

## Quick Start

```bash
# Install dependencies
cd ui && yarn install
cd ../api && poetry install

# Run both services (from repo root)
./dev.sh
```

| Service            | URL                        |
| ------------------ | -------------------------- |
| UI (Vite)          | http://localhost:5173      |
| API (FastAPI)      | http://localhost:8000      |
| API Docs (Swagger) | http://localhost:8000/docs |

Or run individually:

```bash
cd ui && yarn serve          # Frontend only
cd api && poetry run uvicorn app.main:app --reload  # Backend only
```

---

## Architecture Overview

```
├── ui/                          # React frontend
│   └── src/
│       ├── features/chat/       # Chat feature (bulletproof-react style)
│       │   ├── api.ts           # API calls + SSE streaming
│       │   ├── types.ts         # Shared TypeScript types
│       │   ├── hooks/           # React Query hooks
│       │   └── components/      # Chat UI components
│       ├── lib/api-client.ts    # Generic fetch + SSE client
│       ├── providers/           # React Query + Theme providers
│       └── components/ui/       # shadcn component library
│
├── api/                         # FastAPI backend
│   └── app/
│       ├── main.py              # App entrypoint + CORS
│       ├── store.py             # In-memory data store
│       ├── models/              # Pydantic schemas
│       ├── routers/             # API route handlers
│       └── services/
│           ├── openai.py        # OpenAI client setup
│           └── github.py        # GitHub API client
│
├── knowledge/                   # Engineering spec documents (for RAG)
│   ├── architecture-overview.md
│   ├── authentication.md
│   ├── data-pipeline.md
│   ├── deployment-guide.md
│   ├── frontend-performance.md
│   ├── incident-response.md
│   └── rate-limiting.md
│
└── dev.sh                       # Runs both services concurrently
```

---

## Backend (FastAPI)

### API Routes

All routes are defined in `api/app/routers/`:

| Method   | Endpoint                      | Router             | Description                       |
| -------- | ----------------------------- | ------------------ | --------------------------------- |
| `GET`    | `/health`                     | `health.py`        | Health check                      |
| `GET`    | `/conversations`              | `conversations.py` | List all conversations            |
| `POST`   | `/conversations`              | `conversations.py` | Create a conversation             |
| `GET`    | `/conversations/:id`          | `conversations.py` | Get a conversation                |
| `DELETE` | `/conversations/:id`          | `conversations.py` | Delete a conversation             |
| `GET`    | `/conversations/:id/messages` | `messages.py`      | List messages                     |
| `POST`   | `/conversations/:id/messages` | `messages.py`      | Send message (returns SSE stream) |

### OpenAI Client

`api/app/services/openai.py` initializes the OpenAI client. It reads `OPENAI_API_KEY` from `api/.env` via `python-dotenv` and exits with a clear error if the key is missing. The client instance is imported directly by the messages router:

```python
from app.services.openai import client as openai_client
```

### GitHub Client

`api/app/services/github.py` provides three async functions for interacting with the GitHub API:

| Function                                          | Purpose                                                                                         |
| ------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `search_repos(query, per_page=10)`                | Search repositories by keyword. Returns `full_name`, `description`, `url`, `stars`, `language`. |
| `search_files(owner, repo, query, per_page=10)`   | Search for files within a specific repo. Returns `name`, `path`, `url`.                         |
| `get_file_content(owner, repo, path, ref="main")` | Read the contents of a single file. Returns decoded text content.                               |

All functions use `httpx.AsyncClient` with the GitHub PAT for authentication.

### In-Memory Store

`api/app/store.py` provides a simple in-memory store for conversations and messages. Data resets on server restart. It's a singleton (`store = Store()`) imported by the routers.

### Knowledge Base

The `knowledge/` folder contains 7 engineering spec documents for a fictional company ("Acme Corp"). These are the documents you'll use for RAG:

| Document                   | Topics                                                                    |
| -------------------------- | ------------------------------------------------------------------------- |
| `architecture-overview.md` | System architecture, services, infrastructure, deployment overview        |
| `authentication.md`        | JWT auth flow, RBAC roles/permissions, API keys, MFA, sessions            |
| `data-pipeline.md`         | CDC, Kafka, Flink, Redshift, event schemas, retention policies            |
| `deployment-guide.md`      | CI/CD pipeline, environments, database migrations, rollback procedures    |
| `frontend-performance.md`  | Core Web Vitals, code splitting, React Query patterns, monitoring         |
| `incident-response.md`     | Severity levels, on-call rotation, alert thresholds, runbooks             |
| `rate-limiting.md`         | Sliding window algorithm, per-plan limits, token bucket, response headers |

The documents intentionally cross-reference each other and share overlapping topics (e.g., the same bug ticket `ACME-5102` appears in both `authentication.md` and `rate-limiting.md`).

### SSE Streaming (Server → Client)

The `POST /conversations/:id/messages` endpoint returns a `text/event-stream` response. Here's how it works:

1. The user's message is saved to the store
2. Full conversation history is sent to OpenAI's Chat Completions API with `stream=True`
3. Each token from OpenAI is forwarded to the client as an SSE event
4. When the stream finishes, the full assistant message is saved and a `done` event is sent

**SSE event format:**

```
event: <event_type>
data: <json_payload>

```

**Event types:**

| Event   | Payload                                    | When                    |
| ------- | ------------------------------------------ | ----------------------- |
| `token` | `string` — a text chunk                    | Each token from the LLM |
| `done`  | `MessageResponse` — the full saved message | Stream complete         |
| `error` | `string` — error description               | Something went wrong    |

The SSE helper function in `messages.py`:

```python
def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"
```

---

## Frontend (React + Vite)

### Tech Stack

| Library                    | Purpose                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| **React 19**               | UI framework                                                         |
| **Vite 7**                 | Dev server and bundler                                               |
| **TypeScript 5.9**         | Type safety                                                          |
| **TanStack React Query**   | Server state management — caching, optimistic updates, invalidation  |
| **Tailwind CSS 4**         | Utility-first styling                                                |
| **shadcn/ui** (Radix Nova) | Pre-built accessible components (sidebar, scroll-area, avatar, etc.) |
| **Lucide React**           | Icons                                                                |

There is **no client-side router** — the app is a single-page chat interface. If you need routing, add `react-router-dom` or `@tanstack/react-router`.

### Project Structure (Bulletproof React)

The frontend follows the [bulletproof-react](https://github.com/alan2207/bulletproof-react) pattern where code is organized by **feature**, not by type:

```
src/
├── features/
│   └── chat/                    # Everything for the chat feature lives here
│       ├── api.ts               # API layer — all fetch calls for this feature
│       ├── types.ts             # TypeScript types for this feature
│       ├── index.ts             # Public barrel export
│       ├── hooks/
│       │   ├── use-conversations.ts  # CRUD hooks for conversations
│       │   └── use-messages.ts       # Message fetching + SSE streaming hook
│       └── components/
│           ├── chat-layout.tsx       # Main layout (sidebar + chat area)
│           ├── chat-sidebar.tsx      # Conversation list
│           ├── message-list.tsx      # Scrollable message list
│           ├── message-bubble.tsx    # Individual message display
│           └── message-input.tsx     # Text input + send button
├── lib/
│   ├── api-client.ts            # Generic fetch wrapper + SSE streaming client
│   └── utils.ts                 # Tailwind cn() helper
├── providers/
│   ├── app-provider.tsx         # Composes all providers
│   └── query-provider.tsx       # React Query client config
├── components/
│   ├── ui/                      # shadcn components (don't edit these directly)
│   └── theme-provider.tsx       # Dark/light mode
├── hooks/
│   └── use-mobile.ts            # Responsive breakpoint hook
├── App.tsx                      # Root component
└── main.tsx                     # Entry point
```

### SSE Streaming (Client Side)

The frontend consumes SSE streams using a generic `streamSSE()` helper in `lib/api-client.ts`. It uses the native `fetch` API with `ReadableStream` — no polyfills or libraries needed.

**How it works:**

1. `streamSSE()` makes a `POST` request and reads the response body as a stream
2. It parses `event:` and `data:` lines from the SSE protocol
3. It dispatches typed callbacks based on the event name
4. Supports `AbortController` for cancellation

The chat feature uses this through a custom hook (`useStreamMessage`) that:

- Optimistically adds the user's message to the React Query cache
- Accumulates streamed tokens into React state for live rendering
- On `done`, replaces the optimistic message with the real one from the server
- Invalidates the conversations query to update the sidebar

### React Query Hooks

All data fetching is done through custom hooks in `features/chat/hooks/`:

- **`useConversations()`** — fetches the conversation list
- **`useCreateConversation()`** — creates a conversation, invalidates the list
- **`useDeleteConversation()`** — deletes a conversation, invalidates the list
- **`useMessages(conversationId)`** — fetches messages for a conversation (disabled when `null`)
- **`useStreamMessage()`** — sends a message and streams the response via SSE

---

## Your Task

The chat app currently works as a plain ChatGPT wrapper — it sends the conversation history to OpenAI and streams back the response. Your job is to make it smarter by adding **RAG** (Retrieval-Augmented Generation) and **tool calling**.

### Part 1: RAG — Knowledge Base Search

The `knowledge/` folder contains engineering spec documents for a fictional company. Make the assistant able to answer questions about these documents accurately.

**What to build:**

- Ingest the markdown files into a vector store (e.g., ChromaDB, FAISS, or any embedding-based store)
- When a user asks a question, retrieve relevant document chunks and include them as context in the LLM prompt
- The assistant should cite which documents it used in its response

**Example queries it should handle well:**

- "What's the rate limit for the Professional plan?"
- "How does the authentication flow work?"
- "What's the status of bug ACME-5102?"
- "Walk me through what happens during a SEV-1 incident"

### Part 2: Tool Calling — GitHub Search

The GitHub API client is already built (`api/app/services/github.py`). Make the assistant able to search GitHub when the user asks about open-source tools or libraries.

**What to build:**

- Define OpenAI-compatible tool schemas for the GitHub functions
- Implement the tool-calling loop: LLM decides to call a tool → you execute it → feed the result back to the LLM → LLM responds
- The assistant should be able to search repos, find files, and read READMEs

**Example queries it should handle well:**

- "Find me a good Python library for rate limiting"
- "What does the README for pallets/flask say?"
- "Are there any open-source CDC tools similar to what's described in our data pipeline spec?"

### Part 3: Putting It Together

The real test is combining both capabilities. The assistant should be able to:

1. Answer a question using the knowledge base
2. Then search GitHub for related tools
3. Combine both into a coherent response

**Example:**

> "Our data pipeline spec mentions we use Debezium for CDC. Are there any newer alternatives? Compare them."

The assistant should retrieve the data pipeline doc (RAG), search GitHub for CDC tools (tool calling), and synthesize a comparison.

### Bonus (if time allows)

- Add a new SSE event type (e.g., `tool_call`) so the frontend can show what tool is being used while it executes
- Show retrieved sources in the UI (the `Source` type and `SourcesList` component already exist in the frontend)
- Add error handling for GitHub API rate limits
- Ensure the response still streams token-by-token after tool execution (don't block on the full response)
- Add some flair. Make it look nice. Animations, custom components, change the theme or custom CSS/tailwind. This is your time to show off.

### Evaluation Criteria

| Area              | What we're looking for                                                       |
| ----------------- | ---------------------------------------------------------------------------- |
| **RAG quality**   | Chunking strategy, embedding choice, retrieval accuracy, prompt construction |
| **Tool calling**  | Correct implementation of the tool loop, schema design, error handling       |
| **Code quality**  | Clean, well-structured code that fits the existing patterns                  |
| **System design** | Thoughtful decisions about when to use RAG vs. tools vs. both                |
| **Frontend**      | Any UI improvements to surface tool usage or sources (bonus)                 |

---

## Rules & Submission

### During the Interview (Live Session)

You will have a live coding session with us where you begin working on the task. During this session:

- **No AI agents** — do not use agentic tools like Cursor Agent, Claude Code, Copilot Workspace, etc.
- **AI chat is fine** — you may use ChatGPT, Claude, Copilot Chat, or similar conversational AI tools. Treat it like an open-book exam.
- **Google is fine** — search for docs, Stack Overflow, whatever you need.

We want to see how _you_ think through problems, not how well you can prompt an agent to do it for you.

### After the Interview (Take-Home)

After the live session, you have **24 hours** to finish and submit your work. During this time, you may use any tools you like — Cursor, Claude Code, Copilot, whatever helps you ship.

### How to Submit

1. **Fork** this repository
2. Complete your implementation
3. Add a short **`SOLUTION.md`** to the repo root covering:
   - How to run your version (any new dependencies, env vars, setup steps)
   - What you changed and added
   - Key decisions and trade-offs (why you chose a particular vector store, chunking strategy, etc.)
   - Anything you'd do differently with more time
   - Anythign else you would like us to know
4. Send us a link to your fork

The `SOLUTION.md` doesn't need to be long — a few paragraphs is fine. We just want to understand your thought process and be able to run your code without guessing.
