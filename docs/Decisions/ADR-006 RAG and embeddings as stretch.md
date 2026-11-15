---
date: 2026-11-15
status: accepted
tags: [decision]
---
# ADR-006 RAG and embeddings as stretch

## Context
SECOM is numeric and anonymized, so RAG adds nothing to the core pipeline.

## Options considered
- Skip RAG
- RAG in the core
- RAG as targeted stretch goals

## Decision
RAG and embeddings are stretch goals: similar-run search, a cited knowledge base, and an artifact-only chat with no question limit.

## Consequences
Built only after the MVP works on main. Background knowledge is never presented as evidence.
