---
date: 2026-11-18
status: accepted
tags: [decision, rag, supabase]
---
# ADR-028 Cross-run chat with pgvector and grounded summaries

## Context
"Ask Foresight" answered about one run only. With a run registry, questions across runs become possible ("How did the PR-AUC differ between runs?").

## Options considered
- Re-embed every run's documents into a new store
- **Store each run's existing chunks and embeddings in pgvector when the run is recorded** (chosen)
- Search the run folders only

## Decision
- **Storage:** `foresight.chunks` (`vector(384)`, HNSW cosine index, same private schema and RLS) holds every successful run's chat chunks with the embeddings already computed for its own index. Nothing is embedded twice.
- **All runs mode:**
  - takes the 40 nearest chunks across runs and re-ranks them with the same section-title bonus as one run
  - answers from the best 6, with the same refusal threshold and citation checks
  - citations name the run (`[source: <run id>/<file> § <section>]`), and the prompt lists each run's start time and data
- **Without Supabase:** the successful runs' own indexes are merged.
- **Grounded summaries:** a comparison across runs naturally ends with an uncited summary of the cited lines. On `dev`, the single-run rule ("every paragraph cites") withheld every real answer. In All runs mode, an uncited paragraph is allowed only if every number in it appears in the retrieved excerpts or run ids.

## Consequences
- Live on `dev`: SECOM runs at PR-AUC 0.085 compared with an uploaded run at 0.104, each statement cited with its run; an off-topic question was refused without an LLM call.
- Limitation: a summary sentence without numbers can still generalize more than its cited lines ("Yes, in every run").
