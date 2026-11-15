"""Deterministic seeding for every random source the pipeline uses."""

from __future__ import annotations

import os
import random

import numpy as np


def set_seeds(seed: int) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
