"""Fixed local embedding model: all-MiniLM-L6-v2 through ONNX Runtime (via chromadb).

It is downloaded once (about 80 MB) into ``paths.models_dir``; on Railway that folder is on the
runs volume, so it survives redeploys. Vectors are L2-normalised, so a dot product is the
cosine similarity.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"
DIMENSIONS = 384
_LOCK = threading.Lock()


class Embedder:
    name = f"{MODEL_NAME} (ONNX)"

    def __init__(self, models_dir: Path):
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        self._model = ONNXMiniLM_L6_V2()
        self._model.DOWNLOAD_PATH = str(Path(models_dir) / MODEL_NAME)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, DIMENSIONS), dtype=np.float32)
        with _LOCK:  # the ONNX session and the first download are not shared safely
            vectors = np.asarray(self._model(list(texts)), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1, norms)


@lru_cache(maxsize=4)
def get_embedder(models_dir: str) -> Embedder:
    return Embedder(Path(models_dir))
