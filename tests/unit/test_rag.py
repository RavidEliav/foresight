"""RAG unit tests: chunking, retrieval, the refusal threshold, citations and logging (§18.4).

The tiny fixed index uses the real embedding model (downloaded once into the test model cache).
"""

import json
from pathlib import Path

import pytest

from foresight.rag import chat
from foresight.rag.index import (
    Chunk,
    VectorIndex,
    build_run_index,
    chunk_file,
    knowledge_index,
    retrieve,
    run_index,
    sections,
    split_text,
)
from foresight.settings import load_settings

REPORT = """# Engineering report

## What was detected
104 of 1567 runs failed (fail rate 6.6%) [source: data_profile.json].

## Supporting statistical evidence
The model's test PR-AUC was 0.085 versus 0.061 for random guessing [source: model_metrics.json].

## Recommended next steps
Review maintenance records for the tools that ran the flagged runs.
"""


@pytest.fixture
def settings(tmp_path):
    s = load_settings()
    s.mock_llm = True
    s.paths.runs_dir = tmp_path / "runs"
    return s


@pytest.fixture
def run_dir(tmp_path, settings):
    run = tmp_path / "runs" / "20260101T000000000000Z"
    run.mkdir(parents=True)
    (run / "engineering_report.md").write_text(REPORT, encoding="utf-8")
    (run / "validation_summary.json").write_text(json.dumps({
        "status": "PASS", "counts": {"PASS": 16, "WARNING": 0, "ERROR": 0},
        "checks": [{"name": "raw_label_values", "status": "PASS",
                    "message": "labels are -1 (pass) or 1 (fail)"}]}))
    build_run_index(run, settings)
    return run


def test_sections_use_headings_and_the_title():
    found = sections(REPORT, "default")
    assert [title for title, _ in found] == ["What was detected",
                                             "Supporting statistical evidence",
                                             "Recommended next steps"]


def test_split_text_keeps_sentences_whole_and_overlaps():
    text = " ".join(f"Sentence number {i} is here." for i in range(30))
    chunks = split_text(text, size=120, overlap=40)
    assert len(chunks) > 3
    assert all(len(c) <= 120 for c in chunks)
    assert all(c.endswith(".") for c in chunks)
    assert chunks[1].split(".")[0] in chunks[0]  # the next chunk repeats the last sentence


def test_json_artifacts_become_readable_text(run_dir):
    chunks = chunk_file(run_dir / "validation_summary.json", 800, 120)
    assert chunks[0].section == "Validation checks"
    assert "16 checks passed" in chunks[0].text and "raw_label_values: PASS" in chunks[0].text


def test_run_index_is_saved_with_its_parameters(run_dir, settings):
    params = json.loads((run_dir / "rag_chunks.json").read_text())["params"]
    assert params["embedding_model"] == "all-MiniLM-L6-v2"
    assert params["files"] == ["engineering_report.md", "validation_summary.json"]
    index = run_index(run_dir, settings)
    assert index.vectors.shape == (params["chunks"], 384)


def test_retrieval_finds_the_right_section_and_refuses_unrelated_questions(run_dir, settings):
    index = VectorIndex.load(run_dir)
    hits = retrieve(index, "What was the model's PR-AUC?", settings)
    assert hits[0].chunk.citation == "engineering_report.md § Supporting statistical evidence"
    assert retrieve(index, "What is the capital of France?", settings) == []


def test_chat_answers_with_a_citation_and_logs_it(run_dir, settings):
    result = chat.ask("What was the model's PR-AUC?", run_dir, settings)
    assert not result.refused
    assert "0.085" in result.answer
    assert "[source: engineering_report.md § Supporting statistical evidence]" in result.answer
    chat.log_answer(settings, run_dir, result)
    logged = json.loads(chat.log_path(settings, run_dir).read_text().splitlines()[-1])
    assert logged["question"] == "What was the model's PR-AUC?" and logged["sources"]


def test_chat_refuses_out_of_scope_questions_without_an_llm_call(run_dir, settings,
                                                                monkeypatch):
    monkeypatch.setattr(chat, "mock_answer", lambda *a: pytest.fail("no answer expected"))
    result = chat.ask("What is the capital of France?", run_dir, settings)
    assert result.refused and result.answer == chat.REFUSAL
    assert "similarity" in result.reason


def test_uncited_or_refusing_llm_answers_become_the_refusal(run_dir, settings, monkeypatch):
    monkeypatch.setattr(chat, "mock_answer", lambda *a: "The PR-AUC was great.")
    assert chat.ask("What was the model's PR-AUC?", run_dir, settings).reason \
        == "answer withheld: it cited no retrieved excerpt"
    monkeypatch.setattr(chat, "mock_answer", lambda *a: "Not found in this run's artifacts")
    assert chat.ask("What was the model's PR-AUC?", run_dir, settings).refused


def test_citations_must_name_retrieved_sections_and_cover_every_paragraph():
    from foresight.rag.index import Hit

    hits = [Hit(Chunk("insights.md", "Notable sensors",
                      "f_059 differs [source: eda_summary.json]."), 0.6)]
    ok = "f_059 differs between failing and passing runs [source: insights.md § Notable sensors]"
    assert chat.citation_problem(ok, hits) is None
    quoted = ok + " [source: eda_summary.json]"  # a source tag quoted inside the excerpt
    assert chat.citation_problem(quoted, hits) is None
    invented = "f_059 measures pressure. [source: insights.md § Anything]"
    assert "cited no retrieved excerpt" in chat.citation_problem(invented, hits)
    mixed = ok + " It causes failures [source: insights.md § Anything]"
    assert "not retrieved" in chat.citation_problem(mixed, hits)
    assert "not retrieved" in chat.citation_problem(ok + " [source: other.json]", hits)
    uncited = ok + "\n\nIt also causes failures."
    assert chat.citation_problem(uncited, hits) == "part of it has no citation"
    listed = ("The sensors are:\n\n1. f_059 differs\n\n2. f_103 differs "
              "[source: insights.md § Notable sensors]")
    assert chat.citation_problem(listed, hits) is None
    trailing = ("Next steps are:\n\n1. Check logs.\n2. Run a test.\n\n"
                "[source: insights.md § Notable sensors]")
    assert chat.citation_problem(trailing, hits) is None


def test_cited_sources_only_count_retrieved_files():
    from foresight.rag.index import Hit

    hits = [Hit(Chunk("model_card.md", "Metrics", "x"), 0.5)]
    assert chat.cited_sources("PR-AUC 0.085 [source: model_card.md § Metrics]", hits) == {
        "model_card.md"}
    assert chat.cited_sources("[source: invented.md § X]", hits) == set()


def test_knowledge_index_is_cached_by_content(settings, tmp_path):
    settings.paths.models_dir = Path(load_settings().paths.models_dir)
    first = knowledge_index(settings)
    assert len(first.chunks) > 20
    assert {c.source for c in first.chunks} >= {"spc_control_charts.md", "secom_dataset.md"}
    assert "SOURCES.md" not in {c.source for c in first.chunks}
