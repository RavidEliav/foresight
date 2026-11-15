"""Data Quality page: validation results, cleaning decisions and the Data Contract of a run."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

STATUS_ICON = {"PASS": ":material/check_circle:", "WARNING": ":material/warning:",
               "ERROR": ":material/cancel:"}


def latest_run_dir(runs_dir: Path) -> Path | None:
    """Newest run folder that has a validation summary (run ids sort by time)."""
    if not runs_dir.exists():
        return None
    runs = sorted(p for p in runs_dir.iterdir() if (p / "validation_summary.json").exists())
    return runs[-1] if runs else None


def _read(run_dir: Path, name: str) -> dict | None:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def render(run_dir: Path | None) -> None:
    st.title("Data Quality")
    if run_dir is None:
        st.info("No run yet. Start one on the Run Pipeline page to validate the SECOM data.")
        return

    summary = _read(run_dir, "validation_summary.json")
    st.caption(f"Run `{run_dir.name}`")
    status = summary["status"]
    counts = summary["counts"]
    message = (f"Data Contract validation: **{status}** · {counts['PASS']} passed, "
               f"{counts['WARNING']} warnings, {counts['ERROR']} errors")
    {"PASS": st.success, "WARNING": st.warning, "ERROR": st.error}[status](
        message, icon=STATUS_ICON[status])

    checks = pd.DataFrame(summary["checks"])[["status", "name", "message"]]
    st.dataframe(checks, hide_index=True, width="stretch", height=35 * (len(checks) + 1) + 3)

    profile = _read(run_dir, "data_profile.json")
    report = _read(run_dir, "cleaning_report.json")
    if profile and report:
        st.subheader("Cleaned dataset")
        cols = st.columns(4)
        cols[0].metric("Runs", f"{profile['rows']:,}")
        cols[1].metric("Features kept", f"{report['features_out']} / {report['features_in']}")
        cols[2].metric("Fail rate", f"{profile['fail_rate']:.1%}")
        cols[3].metric("Missing cells", f"{profile['missing_cells_ratio']:.2%}")
        st.markdown("**Cleaning decisions**")
        st.markdown("\n".join(f"- {d}" for d in report["decisions"]))

    contract = _read(run_dir, "dataset_contract.json")
    if contract:
        with st.expander("Data Contract"):
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
