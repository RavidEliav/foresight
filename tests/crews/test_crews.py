import shutil
from pathlib import Path

import pytest

from foresight.analytics import stages
from foresight.analytics.stages import run_analyze, run_investigate, run_model, run_report
from foresight.crews.checks import (
    REQUIRED_SECTIONS,
    check_output,
    check_outputs,
    checkable_numbers,
    confidence_problems,
    known_sensor_names,
    numbered_items,
    section,
    traced,
)
from foresight.crews.facts import all_facts, allowed_numbers
from foresight.crews.mock_llm import MockLLM
from foresight.crews.runner import (
    CREWS,
    CrewRunResult,
    build_crew,
    clean_markdown,
    load_config,
    run_crew,
)
from foresight.data.ingest import run_ingest
from foresight.settings import load_settings
from foresight.tools.run_tools import build_tools
from foresight.validation.gates import GateStatus
from tests.conftest import write_synthetic_secom


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    """One full mocked run (deterministic stages + all four crews) shared by these tests."""
    base = tmp_path_factory.mktemp("crews")
    settings = load_settings(Path(__file__).parents[1] / "fast_settings.yaml")
    settings.mock_llm = True
    settings.paths.data_raw_dir = base / "data"
    settings.paths.contract_path = base / "dataset_contract.json"
    write_synthetic_secom(settings.paths.data_raw_dir)
    run = base / "run"
    run.mkdir()
    for stage in (run_ingest, run_analyze, run_model, run_investigate, run_report):
        stage(settings, run)
    return run


@pytest.mark.parametrize("crew", CREWS)
def test_crew_configs_are_consistent(crew):
    config = load_config(crew)
    tool_names = set(build_tools(Path(".")))
    task_names = [t["name"] for t in config["tasks"]]
    for agent in config["agents"].values():
        assert {"role", "goal", "backstory"} <= set(agent)
        assert set(agent.get("tools", [])) <= tool_names
    for i, task in enumerate(config["tasks"]):
        assert task["agent"] in config["agents"]
        assert set(task.get("context", [])) <= set(task_names[:i])  # only earlier tasks
    outputs = [t for t in config["tasks"] if "output" in t]
    assert len(outputs) == 1 and outputs[0]["output"] in REQUIRED_SECTIONS
    assert "{revision_notes}" in outputs[0]["description"]
    descriptions = " ".join(t["description"] for t in config["tasks"])
    for heading in REQUIRED_SECTIONS[outputs[0]["output"]]:
        assert heading in descriptions


def test_official_crews_have_at_least_three_agents():
    assert len(load_config("analyst")["agents"]) >= 3
    assert len(load_config("scientist")["agents"]) >= 3


def test_build_crew_attaches_tools_and_rules(run_dir):
    llm = MockLLM(model="mock", run_dir=run_dir)
    crew, tasks, outputs = build_crew("investigation", run_dir, llm, all_facts(run_dir))
    assert len(crew.agents) == 3 and list(tasks) == ["anomaly_review", "signal_review",
                                                     "investigation"]
    assert outputs == {"investigation": "investigation.md"}
    assert {t.name for t in crew.agents[0].tools} == {"anomaly_summary", "risk_ranking",
                                                      "run_details"}
    assert "Never claim a root cause" in tasks["investigation"].description
    assert "[source: anomaly_summary.json]" in tasks["anomaly_review"].description


def test_mocked_crews_write_outputs_that_pass_all_checks(run_dir):
    for name in REQUIRED_SECTIONS:
        assert (run_dir / name).exists()
    summary = check_outputs(run_dir, list(REQUIRED_SECTIONS))
    assert summary.status == GateStatus.PASS, [c for c in summary.checks if c.status != "PASS"]
    assert (run_dir / "report_checks.json").exists()


def test_investigation_separates_facts_assumptions_hypotheses(run_dir):
    text = (run_dir / "investigation.md").read_text()
    assert text.index("## Facts") < text.index("## Assumptions") < text.index("## Hypotheses")
    assert "Hypothesis (" in text and "confidence" in text


@pytest.fixture
def context(run_dir):
    return known_sensor_names(run_dir), allowed_numbers(run_dir)


def _status(checks, suffix):
    return next(c.status for c in checks if c.name.endswith(suffix))


def test_missing_section_is_reported(run_dir, context):
    text = (run_dir / "model_card.md").read_text().replace("## Limitations", "## Notes")
    checks = check_output("model_card.md", text, run_dir, *context)
    assert _status(checks, "sections") == GateStatus.WARNING


def test_unknown_sensor_is_reported(run_dir, context):
    text = (run_dir / "insights.md").read_text() + "\nSensor f_999 looks important.\n"
    checks = check_output("insights.md", text, run_dir, *context)
    assert _status(checks, "sensor names") == GateStatus.WARNING


def test_invented_numbers_are_reported(run_dir, context):
    text = (run_dir / "insights.md").read_text()
    text += "\n" + " ".join(f"Yield improved by {n}.37%." for n in range(41, 61)) + "\n"
    checks = check_output("insights.md", text, run_dir, *context)
    assert _status(checks, "traceable numbers") == GateStatus.WARNING


def test_uncited_facts_are_reported(run_dir, context):
    text = (run_dir / "investigation.md").read_text().replace("## Facts\n",
                                                              "## Facts\n- An uncited fact\n")
    checks = check_output("investigation.md", text, run_dir, *context)
    assert _status(checks, "cited facts") == GateStatus.WARNING


def test_confidence_rubric():
    assert confidence_problems([
        "1. **Hypothesis**: f_059 ... Confidence level: high (q-value of 2.5e-08, model "
        "importance).",
        "2. **Hypothesis (medium confidence):** f_103 differs (q = 2.1e-06).",
        "3. Hypothesis: drift. Confidence: **low**.",
    ]) == []
    assert confidence_problems([
        "1. Hypothesis: risky runs fail. Confidence level: high (supported by risk scores).",
        "2. Hypothesis: f_205 differs (q = 0.0027). High confidence.",
        "3. Hypothesis: no level stated.",
    ]) == ["#1 is 'high' without q < 0.001", "#2 is 'high' without q < 0.001",
           "#3 has no confidence level"]


def test_overstated_confidence_is_reported(run_dir, context):
    text = (run_dir / "investigation.md").read_text().replace(
        "## Hypotheses\n",
        "## Hypotheses\n1. **Hypothesis (high confidence):** the riskiest runs share a cause.\n")
    checks = check_output("investigation.md", text, run_dir, *context)
    assert _status(checks, "confidence rubric") == GateStatus.WARNING


def test_crew_revises_once_when_its_checks_warn(run_dir, tmp_path, monkeypatch):
    run = tmp_path / "run"
    shutil.copytree(run_dir, run)
    (run / stages.REVISIONS_FILE).unlink(missing_ok=True)
    good = (run / "engineering_report.md").read_text()
    bad = good.replace("## Hypotheses\n", "## Hypotheses\n1. Hypothesis: risky runs fail. "
                       "Confidence: high (risk scores).\n")
    calls = []

    def fake_run_crew(name, settings, run_dir, extra_inputs=None):
        calls.append(extra_inputs.get("revision_notes", ""))
        path = run_dir / "engineering_report.md"
        path.write_text(bad if len(calls) == 1 else good)
        return CrewRunResult(crew=name, outputs={path.name: str(path)},
                             usage={"total_tokens": 100}, seconds=1.0)

    monkeypatch.setattr(stages, "run_crew", fake_run_crew)
    settings = load_settings(Path(__file__).parents[1] / "fast_settings.yaml")
    result = stages.run_report(settings, run)
    assert len(calls) == 2 and calls[0] == ""
    assert "confidence rubric: #1 is 'high' without q < 0.001" in calls[1]
    assert result.checks.status == GateStatus.PASS
    assert _status(result.checks.checks, "report crew: revision") == GateStatus.PASS
    usage = result.crew_usage["report"]
    assert (usage["total_tokens"], usage["seconds"], usage["revisions"]) == (200, 2.0, 1)


def test_crew_is_not_revised_more_than_configured(run_dir, tmp_path, monkeypatch):
    run = tmp_path / "run"
    shutil.copytree(run_dir, run)
    calls = []

    def always_bad(name, settings, run_dir, extra_inputs=None):
        calls.append(name)
        path = run_dir / "model_card.md"
        path.write_text("# Model card\nNo sections.\n")
        return CrewRunResult(crew=name, outputs={path.name: str(path)})

    monkeypatch.setattr(stages, "run_crew", always_bad)
    settings = load_settings(Path(__file__).parents[1] / "fast_settings.yaml")
    result = stages._with_crew(stages.StageResult(), "scientist", settings, run)
    assert len(calls) == 1 + settings.llm.crew_revisions
    assert result.crew_usage["scientist"]["revisions"] == settings.llm.crew_revisions


def test_checkable_numbers_ignore_dates_ids_and_sensors():
    text = "Run 1254 on 2008-10-02T21:32:00 and f_059 had 6.6% fails, 24 of 392 runs, step 3."
    assert checkable_numbers(text) == ["6.6%", "24", "392"]


def test_checkable_numbers_handle_separators_ranges_and_signs():
    text = "1,567 runs in 2008-07; effect -0.73 and -12.5; CI 0.031-0.212; 12.5-14.25; 4–35%."
    assert checkable_numbers(text) == ["1,567", "-0.73", "-12.5", "0.031", "0.212", "12.5",
                                       "14.25", "35%"]
    assert traced("1,567", {"1567"}) and traced("6.6%", {"6.6"})
    assert not traced("-0.38", {"0.38"})


def test_rubric_reads_q_value_spellings_and_sub_headings():
    assert confidence_problems(["1. Hypothesis (q_value = 2.5e-08). Confidence: high (two "
                                "signals).", "2. Hypothesis (q ≤ 1e-6). Confidence: high."]) == []
    text = ("## Hypotheses (AI-generated)\n### Hypothesis 1\nf_059 differs. Confidence: low\n"
            "### Hypothesis 2\nDrift. Confidence: medium\n## Suggested verification\n- logs\n")
    assert numbered_items(section(text, "Hypotheses")) == [
        "### Hypothesis 1 f_059 differs. Confidence: low",
        "### Hypothesis 2 Drift. Confidence: medium"]


def test_crew_usage_counts_each_llm_call_once(run_dir, tmp_path):
    run = tmp_path / "run"
    shutil.copytree(run_dir, run)
    settings = load_settings(Path(__file__).parents[1] / "fast_settings.yaml")
    settings.mock_llm = True
    inputs = {Path(n).stem: (run / n).read_text() for n in stages.REPORT_INPUTS}
    usage = run_crew("report", settings, run, inputs).usage
    assert usage["successful_requests"] == 2  # two agents, one call each
    assert usage["total_tokens"] > 0


def test_clean_markdown_strips_code_fences():
    assert clean_markdown("```markdown\n# Title\ntext\n```") == "# Title\ntext\n"
    assert clean_markdown("# Title\n") == "# Title\n"


def test_facts_cite_their_source_files(run_dir):
    for text in all_facts(run_dir).values():
        lines = [line for line in text.splitlines() if line.startswith("- ")]
        assert lines and all("[source:" in line for line in lines)
