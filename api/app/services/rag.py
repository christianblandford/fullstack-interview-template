import os
import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

KNOWLEDGE_DIR = Path(__file__).parent.parent.parent.parent / "knowledge"
CHROMA_PATH = Path(__file__).parent.parent.parent / ".chroma"

CHUNK_SIZE = 600
CHUNK_OVERLAP = 80
EMBEDDING_MODEL = "text-embedding-3-small"
COLLECTION_NAME = "knowledge_base"

HEADER_SPLITS = [
    ("#",   "h1"),
    ("##",  "h2"),
    ("###", "h3"),
]




class RAGService:
    """
    Handles ingestion and retrieval for the knowledge base.

    Usage:
        rag = RAGService()

        # build the index once
        rag.ingest()

        # query at runtime
        results = await rag.retrieve("How does token refresh work?")
    """

    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self._embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=api_key,
        )

        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, reset: bool = False) -> int:
        """
        Ingest all markdown files from the knowledge/ folder into ChromaDB.
        Returns the total number of chunks stored.

        Args:
            reset: wipe the existing collection before ingesting
        """
        if reset:
            existing = [c.name for c in self._client.list_collections()]
            if COLLECTION_NAME in existing:
                self._client.delete_collection(COLLECTION_NAME)
                logger.info("Deleted existing collection '%s'", COLLECTION_NAME)

        collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        md_files = list(KNOWLEDGE_DIR.glob("*.md"))
        if not md_files:
            raise FileNotFoundError(f"No markdown files found in {KNOWLEDGE_DIR}")

        all_chunks = []
        for md_file in sorted(md_files):
            chunks = self._load_and_chunk(md_file)
            logger.info("  %s → %d chunks", md_file.name, len(chunks))
            all_chunks.extend(chunks)

        logger.info("Total chunks to embed: %d", len(all_chunks))

        BATCH_SIZE = 100
        total_stored = 0

        for i in range(0, len(all_chunks), BATCH_SIZE):
            batch = all_chunks[i : i + BATCH_SIZE]
            texts = [c["text"] for c in batch]
            metadatas = [c["metadata"] for c in batch]
            ids = [
                f"{m['source_file']}::chunk_{m['chunk_index']}"
                for m in metadatas
            ]

            vectors = self._embeddings.embed_documents(texts)
            collection.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
            total_stored += len(batch)

        logger.info("Ingestion complete. %d chunks stored.", total_stored)
        return total_stored

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Semantic search over the knowledge base.

        Returns:
            [
                {
                    "text": str,
                    "source_file": str,   # e.g. "authentication.md"
                    "header_path": str,   # e.g. "Authentication > Known Issues"
                    "score": float,       # cosine distance — lower is better
                }
            ]
        """
        collection = self._client.get_collection(COLLECTION_NAME)

        query_vector = self._embeddings.embed_query(query)

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "text": doc,
                "source_file": meta.get("source_file", "unknown"),
                "header_path": meta.get("header_path", ""),
                "score": round(dist, 4),
            })

        return output

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_and_chunk(self, md_path: Path) -> list[dict]:
        """Split a single markdown file into chunks with metadata."""
        raw = md_path.read_text(encoding="utf-8")

        # Stage 1: split on markdown headers
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADER_SPLITS,
            strip_headers=False,
        )
        header_chunks = header_splitter.split_text(raw)

        # Stage 2: further split oversized sections
        char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        result = []
        chunk_index = 0

        for hchunk in header_chunks:
            content = hchunk.page_content.strip()
            meta = hchunk.metadata  # {"h1": ..., "h2": ..., "h3": ...}

            if not content:
                continue

            for sub in char_splitter.split_text(content):
                sub = sub.strip()
                if not sub:
                    continue

                result.append({
                    "text": self._prepend_header(sub, meta),
                    "metadata": {
                        "source_file": md_path.name,
                        "header_path": self._header_path(meta),
                        "chunk_index": chunk_index,
                    },
                })
                chunk_index += 1

        return result

    @staticmethod
    def _header_path(meta: dict) -> str:
        """e.g. {"h1": "Auth", "h2": "Known Issues"} → "Auth > Known Issues" """
        parts = [meta[k] for k in ("h1", "h2", "h3") if meta.get(k)]
        return " > ".join(parts) if parts else "top-level"

    @staticmethod
    def _prepend_header(content: str, meta: dict) -> str:
        """Prepend section breadcrumb so every sub-chunk carries its context."""
        parts = [meta[k] for k in ("h1", "h2", "h3") if meta.get(k)]
        header_path = " > ".join(parts) if parts else "top-level"
        return f"[Section: {header_path}]\n\n{content}"




rag_service = RAGService()