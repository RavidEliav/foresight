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
    "data_checksums": "Expected for uploads and synthetic scenarios: the checksums identify "
                      "the original SECOM files, so any other data never matches them.",
}


def plain(gate: str, check: str, detail: str, test_fraction: float) -> str:
    if gate == "features_present" and (found := COUNT.search(detail)):
        part = (f"the newest {test_fraction:.0%} of the runs (used to test the model)"
                if check == "test_fails" else
                f"the older {1 - test_fraction:.0%} of the runs (used to train the model)")
        return (f"Not enough failing runs in {part}: found {found.group(1)}, "
                f"need {found.group(2)}.")
    return CONTRACT.get(check, f"{check.replace('_', ' ').capitalize()}: {detail}")


def explain_reason(status: str, reason: str | None, test_fraction: float) -> str:
    """A stopped run's recorded failure reason ("gate: check: detail; ...") in plain words."""
    reason = reason if isinstance(reason, str) else ""  # a missing reason may arrive as NaN
    gate, _, rest = reason.partition(": ")
    if gate in HINTS:
        plain_parts = []
        for message in rest.split("; "):
            check, _, detail = message.partition(": ")
            text = plain(gate, check, detail, test_fraction)
            if text not in plain_parts:
                plain_parts.append(text)
        return " ".join(plain_parts)
    if status == "timeout":
        return "Took longer than the time limit and was stopped."
    if status == "interrupted" and not reason:
        return "Stopped sending updates; the cause was not recorded."
    if status == "stopped":
        return "Stopped from the New analysis page."
    if stage := re.match(r"(\w+) (stage|crew) error", reason):
        what = "step" if stage.group(2) == "stage" else "step's AI"
        return f"Something went wrong in the {stage.group(1)} {what}."
    return reason or "Stopped."


def explain_failure(progress: RunProgress, test_fraction: float,
                    cause: tuple[str, str] | None = None) -> tuple[list[str], str | None]:
    """Why a run stopped, in plain words, and what to do about it. ``cause`` is why an
    interrupted run stopped sending updates (jobs.interruption_cause), when known."""
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
        return ["The analysis took longer than the time limit and was stopped."], \
            "Resume it with Resume analysis above; if it keeps happening, the AI service may " \
            "be slow."
    if status == "interrupted":
        if cause is not None:
            return [cause[0]], cause[1]
        return [reason or "The analysis stopped sending updates; the cause was not "
                          "recorded."], \
            "Resume it with Resume analysis above: the steps it had finished are reused."
    if status == "stopped":
        return ["The analysis was stopped from this page."], \
            "Resume it above (the steps it had finished are reused), or start a different one."
    if stage := re.match(r"(\w+) (stage|crew) error", reason):
        what = "step" if stage.group(2) == "stage" else "step's AI"
        return [f"Something went wrong in the {stage.group(1)} {what}."], \
            "Resume the analysis to try that step again."
    return [reason or "The analysis stopped."], None
