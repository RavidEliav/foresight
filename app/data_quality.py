"""Data Quality page: validation results, cleaning decisions and the Data Contract of a run."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from app import ui
from app.messages import EXPECTED_FOR_UPLOADS
from app.runs import is_scenario, is_upload, run_label
from app.store import read_json

STATUS_ICON = {"PASS": ":material/check_circle:", "WARNING": ":material/warning:",
               "ERROR": ":material/cancel:"}


def render(run_dir: Path | None) -> None:
    ui.page_header("Data Quality")
    if run_dir is None:
        st.info("No run yet. Start one on the Run Pipeline page to validate the SECOM data.")
        return

    summary = read_json(run_dir, "validation_summary.json")
    st.caption(run_label(run_dir))
    _status(summary, is_upload(run_dir) or is_scenario(run_dir))

    profile = read_json(run_dir, "data_profile.json")
    report = read_json(run_dir, "cleaning_report.json")
    if profile and report:
        ui.kpis([
            ("Runs", f"{profile['rows']:,}", None, None),
            ("Failing runs", f"{profile['label_counts'].get('1', 0):,}", None, None),
            ("Fail rate", f"{profile['fail_rate']:.1%}", None, None),
            ("Features kept", f"{report['features_out']}",
             f"of {report['features_in']} sensors",
             "Sensors removed while cleaning are listed in the cleaning decisions"),
            ("Missing cells", f"{profile['missing_cells_ratio']:.2%}", None,
             "Missing values are kept and imputed on the training period only"),
        ])
        with st.container(key="card-cleaning"):
            ui.label("Cleaning decisions")
            st.markdown("\n".join(f"- {d}" for d in report["decisions"]))

    if not ui.developer():  # Extended data is part of the developer view (Phase 8.6)
        return
    ui.section_label("Extended data")
    checks, contract_tab = st.tabs(["All validation checks", "Data Contract"])
    with checks:
        ui.table(pd.DataFrame(summary["checks"])[["status", "name", "message"]], max_rows=30)
    with contract_tab:
        _render_contract(read_json(run_dir, "dataset_contract.json"))


def _status(summary: dict, upload: bool) -> None:
    """The Data Contract result. For an uploaded file, the warnings every upload gets are
    explained instead of alarming; for the built-in data they stay real warnings."""
    status, counts = summary["status"], summary["counts"]
    warnings = [c for c in summary["checks"] if c["status"] == "WARNING"]
    expected = [c for c in warnings if upload and c["name"] in EXPECTED_FOR_UPLOADS]
    message = (f"Data Contract validation: **{status}** · {counts['PASS']} passed, "
               f"{counts['WARNING']} warnings, {counts['ERROR']} errors")
    if status == "WARNING" and len(expected) == len(warnings):
        st.success(message + " (expected for an uploaded file, see below)",
                   icon=STATUS_ICON["PASS"])
    else:
        {"PASS": st.success, "WARNING": st.warning, "ERROR": st.error}[status](
            message, icon=STATUS_ICON[status])
    for check in expected:
        st.info(EXPECTED_FOR_UPLOADS[check["name"]], icon=":material/info:")
    for check in warnings:
        if check not in expected:
            st.markdown(f":orange-badge[{check['name']}] {check['message']}")


def _render_contract(contract: dict | None) -> None:
    if not contract:
        st.info("No Data Contract in this run.")
        return
    st.markdown(
        f"- Version **{contract['contract_version']}**, source "
        f"[{contract['dataset']}]({contract['source']['page']})\n"
        f"- {len(contract['features']['required'])} required features, "
        f"max {contract['features']['max_missing_ratio']:.0%} missing each\n"
        f"- Label `{contract['target']['name']}` in "
        f"{contract['target']['allowed_values']} (mapping "
        f"{contract['target']['mapping']})"
    )
    st.markdown("**Assumptions**\n" + "\n".join(f"- {a}" for a in contract["assumptions"]))
    st.download_button("Download dataset_contract.json", json.dumps(contract, indent=2),
                       file_name="dataset_contract.json", mime="application/json")
