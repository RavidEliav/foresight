"""Retrieval-augmented generation over a run's own artifacts and a small knowledge base (§18).

- ``embedding``: a fixed local embedding model (all-MiniLM-L6-v2, ONNX), no API cost
- ``index``: markdown/JSON chunking, a numpy vector index, retrieval with a refusal threshold
- ``chat``: "Ask Foresight" answers only from retrieved chunks, with citations
"""
