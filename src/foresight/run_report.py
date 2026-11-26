"""The run report (Phase 8.8): every result page of one run in one PDF.

Cover with the run's facts and the numbers at a glance, then Data Quality, EDA & Insights,
Model, Investigation & Report (the engineering report in full, with its citations), and an
appendix with the report's safety checks, the cited files and the run's facts. Built only
from the run's own files, so a run that ended before this existed gets the same report; a new
run saves it as ``run_report.pdf`` (the PDF's date is the run's, so the same run gives the
same file).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, tzinfo
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

RUN_REPORT_FILE = "run_report.pdf"
FONT = "DejaVu"
INK, MUTED, ACCENT, AMBER, LINE = (15, 23, 42), (100, 116, 139), (8, 145, 178), (180, 83, 9), \
    (203, 213, 225)
CITATION = re.compile(r"\[(?:source|background):[^\]]*\]")
SECTIONS = ["Data quality", "Data insights", "Model", "Findings", "Appendix"]


def _json(run_dir: Path, name: str) -> dict | None:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _text(run_dir: Path, name: str) -> str | None:
    path = run_dir / name
    return path.read_text(encoding="utf-8") if path.exists() else None


def _when(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value).astimezone(UTC) if value else None
    except ValueError:
        return None


def _shown(moment: datetime, zone: tzinfo, with_zone: bool = False) -> str:
    """A time in the reader's zone, like the app shows it; UTC says so. ``with_zone`` names
    the zone, so a forwarded report stays clear."""
    local = moment.astimezone(zone)
    text = local.strftime("%d %b %Y, %H:%M")
    if zone is UTC:
        return text + " UTC"
    return f"{text} ({getattr(zone, 'key', None) or local.strftime('%Z')})" if with_zone \
        else text


def _run_time(run_id: str) -> datetime | None:
    """A run id is its start time: 20261125T152828218892Z."""
    try:
        return datetime.strptime(run_id[:15], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


class _Report(FPDF):
    def __init__(self, run_label: str) -> None:
        super().__init__(format="A4")
        self.run_label = run_label
        self.set_margins(18, 16, 18)
        self.set_auto_page_break(True, margin=18)
        fonts = Path(__import__("matplotlib").get_data_path()) / "fonts" / "ttf"
        self.add_font(FONT, "", str(fonts / "DejaVuSans.ttf"))
        self.add_font(FONT, "B", str(fonts / "DejaVuSans-Bold.ttf"))
        self.add_font(FONT, "I", str(fonts / "DejaVuSans-Oblique.ttf"))
        self.add_font(FONT, "BI", str(fonts / "DejaVuSans-BoldOblique.ttf"))
        self.set_title("Foresight analysis report")
        self.set_author("Foresight")
        self.set_creator("Foresight")

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font(FONT, "", 7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"Foresight · {self.run_label}", align="L")
        self.set_x(self.l_margin)
        self.cell(0, 5, f"page {self.page_no()} of {{nb}}", align="R")

    # --- building blocks -----------------------------------------------------------------

    @property
    def width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def section(self, title: str, subtitle: str = "") -> None:
        self.add_page()
        self.set_font(FONT, "B", 19)
        self.set_text_color(*INK)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.7)
        self.line(self.l_margin, self.get_y(), self.l_margin + 28, self.get_y())
        self.ln(2.5)
        if subtitle:
            self.small(subtitle)
        self.ln(1.5)

    def heading(self, text: str) -> None:
        if self.get_y() > self.h - 50:
            self.add_page()
        self.ln(2)
        self.set_font(FONT, "B", 11.5)
        self.set_text_color(*ACCENT)
        self.cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*INK)

    def small(self, text: str) -> None:
        self.set_font(FONT, "", 8)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 4.2, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*INK)

    def prose(self, text: str, size: float = 9.5, indent: float = 0) -> None:
        """A paragraph with **bold** and `code`, and its citations kept in small grey type
        (every number stays traceable to its file)."""
        self.set_x(self.l_margin + indent)
        left = self.l_margin
        self.set_left_margin(left + indent)
        pos = 0
        for match in CITATION.finditer(text):
            before = text[pos:match.start()]
            self._styled(before.rstrip(" "), size)
            self.set_font(FONT, "", size - 2)
            self.set_text_color(*MUTED)
            # the space goes with the tag, so a line breaks before it, not inside it
            self.write(5, (" " if before.endswith(" ") else "") + match.group(0))
            self.set_text_color(*INK)
            pos = match.end()
        self._styled(text[pos:], size)
        self.set_left_margin(left)
        self.ln(6.5)

    def _styled(self, text: str, size: float) -> None:
        for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
            for j, piece in enumerate(re.split(r"`([^`]+)`", part)):
                self.set_font(FONT, "B" if i % 2 else "", size)
                if j % 2:
                    self.set_text_color(*ACCENT)
                self.write(5, piece)
                self.set_text_color(*INK)

    def markdown(self, text: str, skip_title: bool = True,
                 only: list[str] | None = None) -> None:
        """The crews' markdown: ## headings, paragraphs, numbered and bulleted items.
        ``only`` keeps just the named ## sections."""
        keep = only is None
        for block in re.split(r"\n\s*\n", text.strip()):
            block = block.strip()
            if not block:
                continue
            if block.startswith("# ") and skip_title:
                block = "\n".join(block.splitlines()[1:]).strip()
                if not block:
                    continue
            if block.startswith("## "):
                title, _, rest = block.partition("\n")
                title = title[3:].strip()
                keep = only is None or title in only
                if keep:
                    self.heading(title)
                block = rest.strip()
                if not block:
                    continue
            if not keep:
                continue
            for item in re.split(r"\n(?=\s*(?:\d+[.)]|[-*])\s)", block):
                item = " ".join(line.strip() for line in item.splitlines())
                if m := re.match(r"(\d+[.)]|[-*])\s+(.*)", item):
                    marker = "•" if m.group(1) in "-*" else m.group(1)
                    self.set_font(FONT, "B", 9.5)
                    self.set_text_color(*ACCENT)
                    self.cell(6, 5, marker)
                    self.set_text_color(*INK)
                    self.prose(m.group(2), indent=6)
                else:
                    self.prose(item)

    def _lines(self) -> None:
        self.set_draw_color(*LINE)
        self.set_line_width(0.2)

    def numbers(self, rows: list[tuple[str, str, str]]) -> None:
        """Headline numbers as a table: what, value, compared with."""
        self._lines()
        self.set_font(FONT, "", 9)
        with self.table(col_widths=(48, 30, 96), text_align=("LEFT", "RIGHT", "LEFT"),
                        borders_layout="HORIZONTAL_LINES", line_height=5.6,
                        headings_style=_heading_style()) as table:
            table.row(["", "Value", "Compared with"])
            for label, value, note in rows:
                table.row([label, value, note])
        self.ln(2)

    def grid(self, header: list[str] | None, rows: list[list[str]],
             widths: tuple[float, ...], size: float = 8) -> None:
        """A table; ``header`` None: a list of facts without a heading row."""
        self._lines()
        self.set_font(FONT, "", size)
        with self.table(col_widths=widths, borders_layout="HORIZONTAL_LINES",
                        line_height=4.6, text_align="LEFT", first_row_as_headings=bool(header),
                        headings_style=_heading_style(size)) as table:
            if header:
                table.row(header)
            for row in rows:
                table.row([str(v) for v in row])
        self.ln(2)

    def figure(self, path: Path, caption: str, width: float | None = None) -> None:
        if not path.exists():
            return
        from PIL import Image

        with Image.open(path) as image:
            ratio = image.height / image.width
        w = width or self.width
        h = w * ratio
        if self.get_y() + h + 8 > self.h - self.b_margin:
            self.add_page()
        self.image(str(path), x=self.l_margin + (self.width - w) / 2, w=w)
        self.small(caption)
        self.ln(1)


def _heading_style(size: float = 8.5):
    from fpdf.fonts import FontFace

    return FontFace(family=FONT, emphasis="BOLD", color=MUTED, size_pt=size)


def _f(value, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


# --- the sections ---------------------------------------------------------------------------

def _cover(pdf: _Report, run_dir: Path, facts: dict) -> None:
    pdf.add_page()
    pdf.set_font(FONT, "B", 26)
    pdf.set_text_color(*INK)
    pdf.cell(0, 13, "Foresight analysis report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(FONT, "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "Semiconductor yield intelligence on the SECOM manufacturing data",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.9)
    pdf.line(pdf.l_margin, pdf.get_y() + 2, pdf.l_margin + 40, pdf.get_y() + 2)
    pdf.ln(7)
    if facts["synthetic"]:
        pdf.set_fill_color(254, 243, 199)
        pdf.set_text_color(*AMBER)
        pdf.set_font(FONT, "B", 9.5)
        pdf.multi_cell(0, 6, "SYNTHETIC SCENARIO: the training period was changed on purpose; "
                       "every metric is computed on the original SECOM test period.",
                       fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*INK)
        pdf.ln(3)
    pdf.set_font(FONT, "", 9.5)
    with pdf.table(col_widths=(42, 132), borders_layout="NONE", line_height=6,
                   text_align="LEFT", first_row_as_headings=False) as table:
        for label, value in facts["rows"]:
            table.row([label, value])
    pdf.ln(4)
    pdf.heading("Contents")
    pdf.set_font(FONT, "", 9.5)
    for number, name in enumerate(SECTIONS, start=1):
        pdf.cell(0, 5.6, f"{number}.  {name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if facts["glance"]:
        pdf.heading("At a glance")
        pdf.numbers(facts["glance"])
    pdf.small("Every statement in the crews' texts cites the run file it comes from "
              "([source: ...]); background knowledge is cited as [background: ...]. "
              "Associations are not causes.")


def _data_quality(pdf: _Report, run_dir: Path) -> None:
    pdf.section("1. Data quality", "The Data Contract checks on the run's data, and how the "
                "data was cleaned.")
    summary = _json(run_dir, "validation_summary.json")
    profile = _json(run_dir, "data_profile.json")
    cleaning = _json(run_dir, "cleaning_report.json")
    if summary:
        counts = summary["counts"]
        pdf.prose(f"Data Contract validation: **{summary['status']}** · {counts['PASS']} "
                  f"passed, {counts['WARNING']} warnings, {counts['ERROR']} errors.")
        issues = [c for c in summary["checks"] if c["status"] != "PASS"]
        if issues:
            pdf.heading("Warnings and errors")
            pdf.grid(["Status", "Check", "Message"],
                     [[c["status"], c["name"], c["message"]] for c in issues], (20, 50, 104))
    if profile and cleaning:
        pdf.heading("The data")
        pdf.numbers([
            ("Runs", f"{profile['rows']:,}", ""),
            ("Failing runs", f"{profile['label_counts'].get('1', 0):,}", ""),
            ("Fail rate", f"{profile['fail_rate']:.1%}", ""),
            ("Sensors kept", str(cleaning["features_out"]), f"of {cleaning['features_in']}"),
            ("Missing cells", f"{profile['missing_cells_ratio']:.2%}",
             "kept, imputed on the training period only"),
        ])
        pdf.heading("Cleaning decisions")
        for decision in cleaning.get("decisions", []):
            pdf.markdown(f"- {decision}")


def _eda(pdf: _Report, run_dir: Path) -> None:
    pdf.section("2. Data insights", "Descriptive statistics over the whole dataset, and the "
                "Data Analyst crew's insights.")
    eda = _json(run_dir, "eda_summary.json")
    if eda:
        overview = eda["overview"]
        pdf.numbers([
            ("Runs", f"{overview['rows']:,}", ""),
            ("Sensors", str(overview["features"]), ""),
            ("Fail rate", f"{overview['fail_rate']:.1%}", "over the whole dataset"),
            ("Sensors that differ", str(eda["significant_features_q_below_0.05"]),
             "q < 0.05, Mann-Whitney U, Benjamini-Hochberg"),
        ])
    insights = _text(run_dir, "insights.md")
    if insights:
        pdf.markdown(insights)
    if eda:
        pdf.figure(run_dir / eda["figures"].get("fail_rate_over_time", ""),
                   "Fail rate over time (weekly).", width=150)
        top = eda["top_discriminating_features"][:10]
        if top:
            pdf.heading("Sensors that differ most between failing and passing runs")
            pdf.grid(["Sensor", "Direction", "Effect", "q-value", "Median pass", "Median fail"],
                     [[t["feature"], t["direction"], _f(t["effect"]), f"{t['q_value']:.2e}",
                       f"{t['median_pass']:.4g}", f"{t['median_fail']:.4g}"] for t in top],
                     (24, 34, 24, 26, 33, 33))
            pdf.small("A difference is a correlation, not a cause. Sensor names are anonymized.")


def _model(pdf: _Report, run_dir: Path) -> None:
    pdf.section("3. Model", "The model that ranks runs by risk, tested on the latest runs it "
                "never saw.")
    metrics = _json(run_dir, "model_metrics.json")
    if not metrics:
        pdf.prose("This run has no model results.")
        return
    op, cm, ci = metrics["operating_point"], metrics["confusion_matrix"], \
        metrics["test_metrics_ci95"]
    split = metrics["split"]
    pdf.prose(f"**Selected model:** `{metrics['selected_model']}` · {op['rule']}. Trained on "
              f"{split['train']['runs']} runs ({split['train']['fails']} fails), tested on the "
              f"next {split['test']['runs']} runs ({split['test']['fails']} fails).")
    pdf.prose(f"On the test period it raised **{op['alarms_in_test']}** alarms: **{cm['tp']}** "
              f"failing runs caught, **{cm['fn']}** missed, **{cm['fp']}** false alarms.")

    def row(key: str, label: str) -> tuple[str, str, str]:
        low, high = ci.get(key, [None, None])
        return label, _f(metrics["test_metrics"].get(key)), f"95% CI {_f(low)} to {_f(high)}"

    pdf.heading("Test metrics")
    pdf.numbers([("PR-AUC", _f(metrics["test_metrics"]["pr_auc"]),
                  f"random {metrics['baseline_pr_auc']:.3f}; 95% CI {_f(ci['pr_auc'][0])} to "
                  f"{_f(ci['pr_auc'][1])}"),
                 row("recall_fail", "Fail recall"), row("precision_fail", "Precision"),
                 row("balanced_accuracy", "Balanced accuracy"), row("roc_auc", "ROC-AUC")])
    fixed = metrics.get("test_metrics_fixed_threshold") or {}
    if "recall_fail" in fixed:
        pdf.small(f"A fixed threshold ({metrics['threshold']:.3f}, tuned on older runs) caught "
                  f"{fixed['recall_fail']:.0%} of failing runs: drift moves the scores, the "
                  "alarm budget adapts.")
    pdf.heading("Model comparison")
    pdf.grid(["Model", "Time CV PR-AUC", "Stratified CV", "Test PR-AUC", "Test ROC-AUC",
              "Description"],
             [[name, _f(c["cv_pr_auc_mean"]), _f(c.get("stratified_cv_pr_auc_mean")),
               _f(c["test_pr_auc"]), _f(c["test_roc_auc"]), c["description"]]
              for name, c in metrics["comparison"].items()], (36, 18, 18, 17, 18, 67), 7.5)
    pdf.small(f"{metrics['selection_rule'][:1].upper()}{metrics['selection_rule'][1:]}.")
    figures = metrics.get("figures", {})
    for key, caption in [("scores_over_time", "Risk score of each test-period run, with the "
                          "alarm cutoff."),
                         ("confusion_matrix", "Alarms against outcomes on the test period."),
                         ("pr_curve", "Precision against recall, with random guessing."),
                         ("feature_importance", "The sensors the model relies on most.")]:
        if key in figures:
            pdf.figure(run_dir / figures[key], caption, width=132)
    card = _text(run_dir, "model_card.md")
    if card:
        pdf.heading("From the model card")
        pdf.markdown(card, only=["Model purpose", "Limitations", "Intended use"])


def _investigation(pdf: _Report, run_dir: Path) -> None:
    pdf.section("4. Findings", "Anomalies, risk ranking, similar past runs and "
                "the engineering report.")
    anomaly = _json(run_dir, "anomaly_summary.json")
    risk = _json(run_dir, "risk_summary.json")
    similar = _json(run_dir, "similar_runs.json")
    rows = []
    if risk:
        test = risk["test"][risk["recommended_ranking"]]
        if "fails_found" in test:
            rows.append(("Failing runs caught", f"{test['fails_found']} of "
                         f"{test['fails_total']}", f"with {test['alarms']} alarms "
                         f"(the riskiest {risk['alarm_budget']:.0%} of the test period)"))
        rows.append(("Alarm precision", f"{test['precision_at_budget']:.1%}",
                     "share of the alarms that were failing runs"))
    if anomaly:
        rows.append(("Anomaly flag lift", f"{anomaly['flag_lift']}x",
                     f"{anomaly['flag_rate_fail']:.1%} of failing vs "
                     f"{anomaly['flag_rate_pass']:.1%} of passing runs flagged"))
        if "mean_out_of_limit_fail" in anomaly:
            rows.append(("Sensors out of limits", str(anomaly["mean_out_of_limit_fail"]),
                         f"{anomaly['mean_out_of_limit_pass']} in passing runs"))
    if similar and similar.get("neighbour_fail_share_for_failing_test_runs") is not None:
        rows.append(("Similar runs that failed",
                     f"{similar['neighbour_fail_share_for_failing_test_runs']:.1%}",
                     f"{similar['neighbour_fail_share_for_passing_test_runs']:.1%} for passing "
                     "runs"))
    if rows:
        pdf.numbers(rows)
    report = _text(run_dir, "engineering_report.md")
    if report:
        pdf.markdown(report)
    else:
        pdf.prose("This run has no engineering report.")
    if anomaly and "anomaly_scores" in anomaly.get("figures", {}):
        pdf.figure(run_dir / anomaly["figures"]["anomaly_scores"],
                   "Anomaly score of each run over time.", width=140)


def _appendix(pdf: _Report, run_dir: Path, manifest: dict | None) -> None:
    pdf.section("5. Appendix", "The report's safety checks, the files cited and the run's "
                "facts.")
    checks = _json(run_dir, "report_checks.json")
    if checks:
        counts = checks["counts"]
        pdf.heading(f"Report safety checks: {checks['status']} ({counts.get('PASS', 0)} of "
                    f"{sum(counts.values())} passed)")
        pdf.grid(["Status", "Check", "Result"],
                 [[c["status"], c["name"], c["message"]] for c in checks["checks"]],
                 (18, 64, 92), 7.5)
    cited = sorted({m.group(0)[1:-1].split(":", 1)[1].strip()
                    for name in ("engineering_report.md", "insights.md", "model_card.md")
                    for m in CITATION.finditer(_text(run_dir, name) or "")})
    if cited:
        pdf.heading("Files and sections cited")
        pdf.set_font(FONT, "", 8)
        for source in cited:
            pdf.multi_cell(0, 4.2, f"• {source}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if manifest:
        pdf.heading("The run")
        packages = manifest.get("packages") or {}
        usage = manifest.get("crew_usage") or {}
        tokens = sum((u or {}).get("total_tokens", 0) for u in usage.values()
                     if isinstance(u, dict))
        rows = [["Run id", manifest.get("run_id", "")],
                ["Code version", str(manifest.get("git_commit") or "n/a")[:12]],
                ["Python", str(manifest.get("python", ""))],
                ["Seed", str(manifest.get("seed", ""))],
                ["LLM", str((manifest.get("llm") or {}).get("model", "n/a"))
                 if isinstance(manifest.get("llm"), dict) else str(manifest.get("llm"))],
                ["LLM tokens", f"{tokens:,}" if tokens else "n/a"],
                ["Stage times", ", ".join(f"{k} {v:.0f} s" for k, v in
                                          (manifest.get("durations_s") or {}).items())],
                ["Packages", ", ".join(f"{k} {v}" for k, v in list(packages.items())[:8])]]
        pdf.grid(None, rows, (32, 142), 8)


def _facts(run_dir: Path, manifest: dict | None, progress: dict | None,
           zone: tzinfo = UTC, name: str | None = None) -> dict:
    """The cover's facts and the numbers at a glance."""
    run_id = run_dir.name
    dataset = (progress or {}).get("dataset") or "SECOM (UCI)"
    started = (_when((progress or {}).get("started_at")) or _run_time(run_id)
               or _when((manifest or {}).get("created_at")))
    finished = _when((progress or {}).get("finished_at"))
    metrics = _json(run_dir, "model_metrics.json")
    checks = _json(run_dir, "report_checks.json")
    # the app names it ("Analysis 12", Phase 8.10); a report saved by the run has its id
    name = name or ("Reference analysis" if not _run_time(run_id) else run_id)
    rows = [["Analysis", name],
            ["Dataset", dataset],
            ["Started", _shown(started, zone, with_zone=True) if started else "n/a"]]
    if started and finished:
        rows.append(["Took", f"{(finished - started).total_seconds() / 60:.1f} min"])
    if metrics:
        rows.append(["Model", f"{metrics['selected_model']} · "
                              f"{metrics['operating_point']['rule']}"])
    if checks:
        counts = checks["counts"]
        rows.append(["Report safety checks", f"{checks['status']} ({counts.get('PASS', 0)} of "
                                             f"{sum(counts.values())} passed)"])
    glance = []
    profile, eda = _json(run_dir, "data_profile.json"), _json(run_dir, "eda_summary.json")
    summary = _json(run_dir, "validation_summary.json")
    if summary:
        glance.append(("Data Contract", summary["status"],
                       f"{summary['counts']['PASS']} checks passed"))
    if profile:
        glance.append(("Runs analysed", f"{profile['rows']:,}",
                       f"fail rate {profile['fail_rate']:.1%}"))
    if eda:
        glance.append(("Sensors that differ", str(eda["significant_features_q_below_0.05"]),
                       "failing vs passing runs, q < 0.05"))
    if metrics:
        low, high = metrics["test_metrics_ci95"]["pr_auc"]
        glance.append(("Model PR-AUC", _f(metrics["test_metrics"]["pr_auc"]),
                       f"random {metrics['baseline_pr_auc']:.3f}; 95% CI {_f(low)} to "
                       f"{_f(high)}"))
    risk = _json(run_dir, "risk_summary.json")
    if risk:
        test = risk["test"][risk["recommended_ranking"]]
        if "fails_found" in test:
            glance.append(("Failing runs caught", f"{test['fails_found']} of "
                           f"{test['fails_total']}", f"with {test['alarms']} alarms"))
    label = " · ".join([name, dataset] + ([_shown(started, zone)] if started else []))
    return {"rows": rows, "glance": glance, "synthetic": dataset.startswith("Scenario"),
            "created": finished or started, "label": label}


def build(run_dir: Path, zone: tzinfo = UTC, name: str | None = None) -> bytes:
    """The run report of ``run_dir`` as PDF bytes, with its times in ``zone`` (the reader's,
    as in the app; the saved report uses UTC) and the analysis's ``name`` ("Analysis 12")."""
    run_dir = Path(run_dir)
    manifest = _json(run_dir, "run_manifest.json")
    progress = _json(run_dir, "progress.json")
    facts = _facts(run_dir, manifest, progress, zone, name)
    pdf = _Report(facts["label"])
    if facts["created"]:
        pdf.set_creation_date(facts["created"])  # the same run gives the same file
    _cover(pdf, run_dir, facts)
    _data_quality(pdf, run_dir)
    _eda(pdf, run_dir)
    _model(pdf, run_dir)
    _investigation(pdf, run_dir)
    _appendix(pdf, run_dir, manifest)
    return bytes(pdf.output())


def save(run_dir: Path) -> Path:
    """Build the run report and save it in the run's folder."""
    path = Path(run_dir) / RUN_REPORT_FILE
    path.write_bytes(build(run_dir))
    return path
