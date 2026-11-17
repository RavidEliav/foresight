"""Plain-language explanations of why a run stopped and of expected Data Contract warnings.
The technical check names and messages stay available in a collapsed section."""

from __future__ import annotations

import re

from foresight.progress import RunProgress

CONTRACT = {
    "raw_feature_count": "The file does not have the 590 sensor columns that SECOM uses.",
    "raw_feature_dtypes": "Some sensor columns contain text instead of numbers.",
    "raw_label_values": "Some labels are not -1 (pass) or 1 (fail).",
    "label_values": "Some labels are not -1 (pass) or 1 (fail).",
    "raw_timestamps": "Some timestamps are missing or are not readable dates.",
    "timestamps": "Some timestamps are missing.",
    "raw_row_count": "The file has too few runs to analyze.",
    "row_count": "The file has too few runs to analyze.",
    "required_columns": "Columns that the Data Contract requires are missing.",
    "feature_dtypes": "Some sensor columns contain text instead of numbers.",
    "unique_ids": "Some runs appear more than once.",
}
COUNT = re.compile(r"(\d+) failing runs .*\(minimum (\d+)\)")
HINTS = {
    "data_contract": "Fix the file and upload it again; the template on this page shows the "
                     "expected format.",
    "features_present": "Upload a longer period, so that both parts have enough failing runs.",
}
# Warnings that are expected for every uploaded file, with the reason.
EXPECTED_FOR_UPLOADS = {
    "data_checksums": "Expected for uploads: the checksums identify the original SECOM files, "
                      "so an uploaded file never matches them.",
}


def plain(gate: str, check: str, detail: str, test_fraction: float) -> str:
    if gate == "features_present" and (found := COUNT.search(detail)):
        part = (f"the newest {test_fraction:.0%} of the runs (used to test the model)"
                if check == "test_fails" else
                f"the older {1 - test_fraction:.0%} of the runs (used to train the model)")
        return (f"Not enough failing runs in {part}: found {found.group(1)}, "
                f"need {found.group(2)}.")
    return CONTRACT.get(check, f"{check.replace('_', ' ').capitalize()}: {detail}")


def explain_failure(progress: RunProgress, test_fraction: float) -> tuple[list[str], str | None]:
    """Why a run stopped, in plain words, and what to do about it."""
    reasons: list[str] = []
    hint = None
    for gate in progress.gates:
        if gate["status"] != "ERROR":
            continue
        hint = hint or HINTS.get(gate["gate"])
        for message in gate["messages"]:
            check, _, detail = message.partition(": ")
            reason = plain(gate["gate"], check, detail, test_fraction)
            if reason not in reasons:
                reasons.append(reason)
    if reasons:
        return reasons, hint
    status, reason = progress.effective_status(), progress.failure_reason or ""
    if status == "timeout":
        return ["The run took longer than the time limit and was stopped."], \
            "Start it again; if it keeps happening, the LLM service may be slow."
    if status == "interrupted":
        return ["The run was interrupted because the app restarted."], "Start a new run."
    if stage := re.match(r"(\w+) stage error", reason):
        return [f"Something went wrong in the {stage.group(1)} step."], \
            "Technical details are below; start a new run to try again."
    return [reason or "The run stopped."], None
