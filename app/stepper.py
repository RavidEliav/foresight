"""The Run Pipeline stepper: one glass tile per stage, coloured by status (green done, red
failed, gray skipped, cyan running), with a small animation of what the stage does while it
runs. Connectors between tiles are the gates, coloured by their result.

HTML and CSS (tile styles in app/ui.py); each drawing is an SVG image (st.html drops inline
<svg>) that carries its own colour and animation. The HTML has no ticking values, so the
2-second refresh does not restart the animations.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from html import escape

from foresight.progress import ACTIVE, RunProgress, StageProgress

# What each stage does, drawn small: data rows being scanned, chart bars growing, model
# nodes lighting up, a lens sweeping a wafer, report lines being written.
ART = {
    "ingest": """<rect class="frame" x="6" y="4" width="60" height="36" rx="4"/>
<rect class="fill row" x="12" y="10" width="48" height="4" rx="1"/>
<rect class="fill row" x="12" y="18" width="40" height="4" rx="1"/>
<rect class="fill row" x="12" y="26" width="44" height="4" rx="1"/>
<rect class="scan" x="8" y="6" width="56" height="2" rx="1"/>""",
    "analyze": """<path class="frame" d="M8 38H66M8 6V38"/>
<rect class="fill bar b1" x="14" y="22" width="8" height="16" rx="1"/>
<rect class="fill bar b2" x="26" y="14" width="8" height="24" rx="1"/>
<rect class="fill bar b3" x="38" y="26" width="8" height="12" rx="1"/>
<rect class="fill bar b4" x="50" y="10" width="8" height="28" rx="1"/>""",
    "model": """<path class="frame" d="M36 8L20 22M36 8L52 22M20 22L12 36M20 22L28 36"/>
<path class="frame" d="M52 22L44 36M52 22L60 36"/>
<circle class="fill node n1" cx="36" cy="8" r="4"/>
<circle class="fill node n2" cx="20" cy="22" r="3.5"/>
<circle class="fill node n3" cx="52" cy="22" r="3.5"/>
<circle class="fill node n4" cx="12" cy="36" r="3"/>
<circle class="fill node n5" cx="28" cy="36" r="3"/>
<circle class="fill node n6" cx="44" cy="36" r="3"/>
<circle class="fill node n7" cx="60" cy="36" r="3"/>""",
    "investigate": """<circle class="frame" cx="30" cy="22" r="17"/>
<path class="grid" d="M14 16H46M13 22H47M14 28H46M24 6V38M30 5V39M36 6V38"/>
<rect class="die" x="31" y="17" width="5" height="5"/>
<g class="lens"><circle class="frame" cx="48" cy="15" r="7"/>
<path class="frame" d="M53 20L60 27"/></g>""",
    "report": """<path class="frame" d="M20 4H44L52 12V40H20Z"/>
<path class="frame" d="M44 4V12H52"/>
<rect class="fill line l1" x="25" y="15" width="20" height="3" rx="1"/>
<rect class="fill line l2" x="25" y="21" width="22" height="3" rx="1"/>
<rect class="fill line l3" x="25" y="27" width="16" height="3" rx="1"/>
<rect class="fill line l4" x="25" y="33" width="20" height="3" rx="1"/>""",
}
GATE_AFTER = {"ingest": ("data_contract", "Data Contract gate"),
              "analyze": ("features_present", "Features gate"),
              "investigate": ("evidence_present", "Evidence gate")}
BADGE = {"done": "&#10003;", "failed": "&#10005;", "skipped": "&ndash;", "interrupted": "!"}
CREW_TEXT = {"running": "working", "done": "done", "skipped": "skipped (not needed)",
             "failed": "failed", "interrupted": "interrupted"}
# What a stage still does after its crew finished
FINISHING = {"report": "checking + indexing for chat", "investigate": "checking the evidence"}


COLORS = {"done": "#34D399", "failed": "#F87171", "running": "#22D3EE", "skipped": "#64748B",
          "pending": "#475569", "interrupted": "#FBBF24"}
BASE_CSS = """*{fill:none;stroke:%s;stroke-width:1.6;stroke-linecap:round}
.fill,.die{fill:%s;stroke:none;opacity:.85}.grid{stroke-opacity:.35;stroke-width:1}
.scan{fill:#22D3EE;stroke:none;opacity:0}"""
DONE_CSS = ".die{fill:#FBBF24}"
RUNNING_CSS = """.scan{opacity:1;animation:scan 1.4s ease-in-out infinite alternate}
.bar,.line{transform-box:fill-box}
.bar{transform-origin:bottom;animation:grow 1.3s ease-in-out infinite}
.b2{animation-delay:.2s}.b3{animation-delay:.4s}.b4{animation-delay:.6s}
.node{animation:blink 1.6s ease-in-out infinite}.n2{animation-delay:.2s}.n3{animation-delay:.3s}
.n4{animation-delay:.5s}.n5{animation-delay:.6s}.n6{animation-delay:.7s}.n7{animation-delay:.8s}
.lens{animation:sweep 3.2s ease-in-out infinite}
.die{fill:#FBBF24;animation:blink 1.2s ease-in-out infinite}
.line{transform-origin:left;animation:write 2.6s ease-in-out infinite}
.l2{animation-delay:.35s}.l3{animation-delay:.7s}.l4{animation-delay:1.05s}
@keyframes scan{from{transform:translateY(0)}to{transform:translateY(31px)}}
@keyframes grow{0%,100%{transform:scaleY(.3)}50%{transform:scaleY(1)}}
@keyframes blink{0%,100%{opacity:.25}50%{opacity:1}}
@keyframes sweep{0%,100%{transform:translate(0,0)}30%{transform:translate(-16px,4px)}
60%{transform:translate(-22px,14px)}80%{transform:translate(-8px,12px)}}
@keyframes write{0%{transform:scaleX(0)}55%,100%{transform:scaleX(1)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}"""


@lru_cache(maxsize=64)
def art(name: str, status: str) -> str:
    """The stage's drawing as an SVG data URI, coloured by status and animated while
    running."""
    color = COLORS.get(status, COLORS["pending"])
    css = BASE_CSS % (color, color) + (RUNNING_CSS if status == "running" else "") + (
        DONE_CSS if status == "done" else "")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 44"><style>{css}</style>'
           f'{ART.get(name, "")}</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _status_text(stage: StageProgress) -> str:
    if stage.status == "done":
        seconds = None if stage.seconds is None else stage.seconds + (stage.crew_seconds or 0)
        return f"done · {seconds:.0f} s" if seconds is not None else "done"
    if stage.status == "running":
        if stage.crew_status == "running":
            return "crew working"
        if stage.crew_status == "done":
            return FINISHING.get(stage.name, "finishing")
        return "running"
    return {"pending": "waiting"}.get(stage.status, stage.status)


def _shown(stage: StageProgress) -> StageProgress:
    """A stage whose own work is done but whose crew still works in the background (Phase 7)
    shows as running until the crew is done, so the tile and its crew line agree."""
    if stage.status == "done" and stage.crew_status == "running":
        return stage.model_copy(update={"status": "running"})
    return stage


def _frozen(stage: StageProgress) -> StageProgress:
    """A run that stopped while a stage was running (e.g. the app restarted): that stage and
    its crew show as interrupted, not as still running."""
    crew = "interrupted" if stage.crew_status == "running" else stage.crew_status
    status = "interrupted" if "running" in (stage.status, stage.crew_status) else stage.status
    return stage.model_copy(update={"status": status, "crew_status": crew})


def _tile(stage: StageProgress) -> str:
    if stage.crew:
        state = CREW_TEXT.get(stage.crew_status or "", "")
        crew = (f'<span class="fs-dot fs-{stage.crew_status or "none"}"></span>'
                f"{escape(stage.crew)}" + (f" · {state}" if state else ""))
    else:
        crew = '<span class="fs-dot fs-none"></span>deterministic only'
    return (f'<div class="fs-stage fs-{stage.status}">'
            f'<div class="fs-badge">{BADGE.get(stage.status, "")}</div>'
            f'<img class="fs-art" alt="" src="{art(stage.name, stage.status)}">'
            f'<div class="fs-stage-title">{escape(stage.label)}</div>'
            f'<div class="fs-stage-crew">{crew}</div>'
            f'<div class="fs-stage-meta">{_status_text(stage)}</div></div>')


def _link(stage: StageProgress, gates: dict[str, str]) -> str:
    gate = GATE_AFTER.get(stage.name)
    if gate is None:
        return '<div class="fs-link"></div>'
    status = gates.get(gate[0])
    title = f"{gate[1]}: {status}" if status else f"{gate[1]}: not reached"
    return (f'<div class="fs-link fs-gate fs-gate-{(status or "none").lower()}" '
            f'title="{title}"></div>')


def stepper_html(progress: RunProgress) -> str:
    gates = {g["gate"]: g["status"] for g in progress.gates}
    parts = []
    live = progress.effective_status() in ACTIVE
    for i, stage in enumerate(progress.stages):
        parts.append(_tile(_shown(stage) if live else _frozen(stage)))
        if i < len(progress.stages) - 1:
            parts.append(_link(stage, gates))
    return f'<div class="fs-stepper">{"".join(parts)}</div>'
