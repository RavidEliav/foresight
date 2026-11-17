---
date: 2026-11-17
status: accepted
tags: [decision, rag]
---
# ADR-018 RAG with local embeddings, hybrid retrieval and validated citations

## Context
Phase 5 adds the RAG stretch goals ([[ADR-006 RAG and embeddings as stretch]]): a cited knowledge base and an "Ask Foresight" chat that answers only from the selected run's artifacts. Answers must be traceable, refusals must be cheap, and the app must stay small enough for Railway.

## Options considered
- OpenAI `text-embedding-3-small` + a hosted vector store (Supabase `pgvector`)
- `sentence-transformers` + chromadb as a service
- **Local all-MiniLM-L6-v2 (ONNX) + a NumPy index stored with each run** (chosen)

## Decision
- **Embeddings:** all-MiniLM-L6-v2 through chromadb's ONNX wrapper (no PyTorch). Downloaded once to `models_dir`, warmed in a background thread at app start, guarded by a lock (180 s timeout) and a 60 s watchdog that dumps stacks.
- **Index per run:** run artifacts plus the 12 `knowledge/` documents, chunked by section (800 characters, 120 overlap), saved as `rag_index.npz` + `rag_chunks.json`. Built in the report stage, or lazily on the first question for older runs.
- **Hybrid retrieval:** cosine similarity + 0.3 × share of question words in the section title.
- **Two-layer refusal:** below a 0.25 score the chat refuses with no LLM call; above it the LLM (gpt-4o-mini, temperature 0) may still refuse if the passages do not answer.
- **Citation validation:** every answer needs at least one traceable citation (a retrieved `file § section`, or a source tag quoted in the retrieved text), no untraceable citations, and every block cited. Failing answers are replaced by a refusal.
- **Logging:** every question, the retrieved chunks, scores and the outcome go to `runs/chat_logs/<run>.jsonl`.

## Consequences
- No extra service or API key for embeddings; the reference run ships its own index, so the demo chat works at once.
- Retrieval quality is limited by a small general-purpose model; the title-keyword boost and the threshold were tuned on real questions (7/7 in-scope answered, 3/3 out-of-scope refused).
- The first-use hang on `dev` was never fully explained; the watchdog, lock timeout and warm-up make it visible and unlikely.
