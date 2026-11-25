"""The run report PDF (Phase 8.8): every result page of one run in one file."""

import json
import shutil
from pathlib import Path

import pypdfium2 as pdfium

from foresight import run_report

REFERENCE = Path(__file__).resolve().parents[2] / "artifacts" / "reference"


def _text(pdf: bytes) -> tuple[int, str]:
    document = pdfium.PdfDocument(pdf)
    return len(document), " ".join(document[i].get_textpage().get_text_range()
                                   for i in range(len(document)))


def test_the_reference_run_report_holds_every_result_page():
    pdf = run_report.build(REFERENCE)
    assert pdf.startswith(b"%PDF")
    pages, text = _text(pdf)
    assert pages >= 8
    for section in ("Foresight run report", "At a glance", "1. Data Quality",
                    "2. EDA & Insights", "3. Model", "4. Investigation & Report", "5. Appendix"):
        assert section in text, section
    # the numbers the result pages show, the engineering report and its citations
    assert "Reference run (committed with the app)" in text
    assert "rf_regularized" in text and "5 of 24" in text and "PASS (26 of 26 passed)" in text
    assert "Hypotheses" in text and "[source: eda_summary.json]" in text
    assert "Model comparison" in text and "Cleaning decisions" in text
    assert "SYNTHETIC" not in text


def test_the_same_run_gives_the_same_file():
    assert run_report.build(REFERENCE) == run_report.build(REFERENCE)


def test_a_scenario_run_is_labeled_synthetic_and_a_run_without_some_files_still_reports(
        tmp_path):
    run = tmp_path / "20260105T000000000000Z"
    shutil.copytree(REFERENCE, run)
    (run / "progress.json").write_text(json.dumps({
        "run_id": run.name, "status": "success",
        "dataset": "Scenario (synthetic): planted fault on f_031",
        "started_at": "2026-01-05T00:00:00+00:00", "finished_at": "2026-01-05T00:02:30+00:00"}))
    for name in ("risk_summary.json", "similar_runs.json", "model_card.md"):
        (run / name).unlink()  # a run from before these files existed
    _, text = _text(run_report.build(run))
    assert "SYNTHETIC SCENARIO" in text and "planted fault on f_031" in text
    assert "05 Jan 2026, 00:00 UTC" in text and "2.5 min" in text
    assert "4. Investigation & Report" in text


def test_times_are_in_the_readers_zone_like_the_app():
    """The reference run started at 14:53 UTC; a reader in Israel sees 16:53, as in the app.
    Without the reader's zone (the saved report) the time says UTC."""
    from zoneinfo import ZoneInfo

    _, local = _text(run_report.build(REFERENCE, ZoneInfo("Asia/Jerusalem")))
    assert "17 Nov 2026, 16:53 (Asia/Jerusalem)" in local and "14:53" not in local
    _, utc = _text(run_report.build(REFERENCE))
    assert "17 Nov 2026, 14:53 UTC" in utc


def test_save_writes_the_pdf_into_the_run_folder(tmp_path):
    run = tmp_path / "run"
    shutil.copytree(REFERENCE, run)
    path = run_report.save(run)
    assert path == run / run_report.RUN_REPORT_FILE and path.read_bytes().startswith(b"%PDF")
