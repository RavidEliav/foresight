"""Mock LLM for MOCK_LLM=true: drives the real CrewAI machinery without any API call.

Each task gets a deterministic draft built from the run's files (see drafts.py), returned in
CrewAI's ReAct final-answer format.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from crewai.llms.base_llm import BaseLLM
from pydantic import Field

from foresight.crews.drafts import draft_for


class MockLLM(BaseLLM):
    run_dir: Path
    inputs: dict[str, str] = Field(default_factory=dict)

    def call(self, messages: Any, tools: Any = None, callbacks: Any = None,
             available_functions: Any = None, from_task: Any = None, from_agent: Any = None,
             response_model: Any = None) -> str:
        name = getattr(from_task, "name", None) or "unknown"
        draft = draft_for(name, self.run_dir, self.inputs)
        return f"Thought: I now know the final answer\nFinal Answer: {draft}"

    def supports_function_calling(self) -> bool:
        return False

    def get_context_window_size(self) -> int:
        return 128_000
