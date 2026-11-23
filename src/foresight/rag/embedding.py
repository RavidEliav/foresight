"""Fixed local embedding model: all-MiniLM-L6-v2 through ONNX Runtime (via chromadb).

It is downloaded once (about 80 MB) into ``paths.models_dir``; on Railway that is the container's
own disk (/tmp), so the runs volume keeps its space for runs, and each deploy downloads it again.
Vectors are L2-normalised, so a dot product is the cosine similarity.

Calls are serialised with a lock (with a timeout, so a waiting request fails clearly instead of
hanging), and a watchdog writes every thread's stack to the log if one call takes too long.
"""

from __future__ import annotations

import faulthandler
import os
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

from foresight.utils.logging import get_logger

# Hugging Face tokenizers can deadlock with their own thread pool inside threaded servers
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

MODEL_NAME = "all-MiniLM-L6-v2"
DIMENSIONS = 384
LOCK_TIMEOUT_S = 180
WATCHDOG_S = 60
BATCH = 8
_LOCK = threading.Lock()
log = get_logger("embedding")


class EmbeddingBusyError(RuntimeError):
    """The embedding model is busy (or stuck) in another request."""


def _dump_stacks(what: str) -> None:
    log.warning("embedding still running after %s s (%s); thread stacks follow", WATCHDOG_S,
                what)
    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)


class Embedder:
    name = f"{MODEL_NAME} (ONNX)"

    def __init__(self, models_dir: Path):
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

        self._model = ONNXMiniLM_L6_V2()
        self._model.DOWNLOAD_PATH = str(Path(models_dir) / MODEL_NAME)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, DIMENSIONS), dtype=np.float32)
        if not _LOCK.acquire(timeout=LOCK_TIMEOUT_S):
            raise EmbeddingBusyError("the embedding model is busy; please try again shortly")
        watchdog = threading.Timer(WATCHDOG_S, _dump_stacks, args=(f"{len(texts)} texts",))
        watchdog.daemon = True
        start = time.perf_counter()
        try:
            watchdog.start()
            # small batches: ONNX Runtime keeps memory for the largest batch it has seen
            # (100 chunks at once cost about 430 MB more than batches of 8, for 0.8 s saved)
            vectors = np.vstack([np.asarray(self._model(list(texts[i:i + BATCH])),
                                            dtype=np.float32)
                                 for i in range(0, len(texts), BATCH)])
        finally:
            watchdog.cancel()
            _LOCK.release()
        seconds = time.perf_counter() - start
        if seconds > 5:
            log.info("embedded %d texts in %.1f s", len(texts), seconds)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1, norms)


@lru_cache(maxsize=4)
def get_embedder(models_dir: str) -> Embedder:
    return Embedder(Path(models_dir))


def warm_up(models_dir: str) -> threading.Thread:
    """Download (first time only) and load the model in the background, so no user request
    has to wait for it; requests that arrive meanwhile wait on the lock."""

    def work() -> None:
        try:
            get_embedder(models_dir).embed(["warm up"])
            log.info("embedding model ready")
        except Exception:  # the chat reports problems when it is used
            log.exception("embedding model warm-up failed")

    thread = threading.Thread(target=work, name="embedding-warm-up", daemon=True)
    thread.start()
    return thread
