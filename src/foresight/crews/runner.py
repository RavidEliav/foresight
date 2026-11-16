"""Build and run the four crews from their YAML configs."""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task
from pydantic import BaseModel, Field

from foresight.crews.facts import all_facts
from foresight.crews.mock_llm import MockLLM
from foresight.llm import get_llm
from foresight.settings import Settings
from foresight.tools.run_tools import build_tools
from foresight.utils.logging import get_logger

# CrewAI's optional cloud tracing waits on timeouts (about 5 s per task) and prints banners.
# Foresight keeps its own logs and run manifest, so tracing and telemetry are off unless set.
for _name, _value in (("CREWAI_TRACING_ENABLED", "false"), ("CREWAI_DISABLE_TELEMETRY", "true"),
                      ("OTEL_SDK_DISABLED", "true")):
    os.environ.setdefault(_name, _value)

log = get_logger("crews")
CONFIG_DIR = Path(__file__).parent / "config"
CREWS = ("analyst", "scientist", "investigation", "report")

RULES = """
Rules (engineering safety):
- Use only numbers that appear in the facts above, the context, or tool results. Never
  estimate, round differently or invent numbers.
- After each factual statement, cite the file it came from as [source: <file>].
- Label anything that is not a measured result as an assumption or a hypothesis.
- Never claim a root cause. Say "is associated with", not "causes".
- Sensor names (f_000 to f_589) are anonymized; do not guess what they physically measure.
- A z-score from a sensor that barely varied during training can be huge for a small change;
  treat such values with caution.
- Return plain markdown, without code fences.
"""


class CrewRunResult(BaseModel):
    crew: str
    outputs: dict[str, str] = Field(default_factory=dict)
    usage: dict[str, int] = Field(default_factory=dict)
    seconds: float = 0.0
    mock: bool = False


def load_config(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def build_crew(name: str, run_dir: Path, llm, inputs: dict[str, str]):
    """Returns the Crew and its tasks keyed by name (with their output file names)."""
    config = load_config(name)
    tools = build_tools(run_dir)
    values = defaultdict(str, inputs)
    agents = {
        key: Agent(role=spec["role"], goal=spec["goal"], backstory=spec["backstory"].strip(),
                   tools=[tools[t] for t in spec.get("tools", [])], llm=llm,
                   allow_delegation=False, verbose=False, max_iter=6)
        for key, spec in config["agents"].items()
    }
    tasks: dict[str, Task] = {}
    outputs: dict[str, str] = {}
    for spec in config["tasks"]:
        description = spec["description"].format_map(values).strip() + "\n" + RULES
        tasks[spec["name"]] = Task(
            name=spec["name"], description=description,
            expected_output=spec["expected_output"], agent=agents[spec["agent"]],
            context=[tasks[c] for c in spec.get("context", [])])
        if "output" in spec:
            outputs[spec["name"]] = spec["output"]
    crew = Crew(agents=list(agents.values()), tasks=list(tasks.values()),
                process=Process.sequential, memory=False, verbose=False, tracing=False)
    return crew, tasks, outputs


def clean_markdown(text: str) -> str:
    text = text.strip()
    fenced = re.fullmatch(r"```(?:markdown|md)?\s*\n(.*)\n```", text, re.DOTALL)
    return (fenced.group(1) if fenced else text).strip() + "\n"


def run_crew(name: str, settings: Settings, run_dir: Path,
             extra_inputs: dict[str, str] | None = None) -> CrewRunResult:
    inputs = {**all_facts(run_dir), **(extra_inputs or {})}
    llm = MockLLM(model="mock", run_dir=run_dir, inputs=inputs) if settings.mock_llm \
        else get_llm(settings)
    crew, tasks, outputs = build_crew(name, run_dir, llm, inputs)
    start = time.perf_counter()
    crew.kickoff()
    written = {}
    for task_name, file_name in outputs.items():
        path = run_dir / file_name
        path.write_text(clean_markdown(tasks[task_name].output.raw), encoding="utf-8")
        written[file_name] = str(path)
    # One LLM instance is shared by the crew's agents (and created per run), so its own counter
    # is the crew's usage; CrewOutput.token_usage would add it once per agent.
    usage = llm.get_token_usage_summary().model_dump()
    log.info("crew %s finished in %.1fs (%s tokens)", name, time.perf_counter() - start,
             usage.get("total_tokens", 0))
    return CrewRunResult(crew=name, outputs=written,
                         usage={k: int(v) for k, v in usage.items() if isinstance(v, int)},
                         seconds=round(time.perf_counter() - start, 2), mock=settings.mock_llm)
