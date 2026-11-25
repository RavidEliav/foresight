"""Line Replay page (Phase 8.4): the run's test period played back run by run, in time order,
as the line would have seen it: the risk score of each run, the alarms as they are raised, the
running totals and a simulated wafer of the newest run.

Nothing is re-scored. Every number comes from the run's risk ranking (risk_scores.csv), and
the alarms are the run's own alarm budget (the riskiest share of the test period), so the
totals at the end are the ones on the Investigation & Report page.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app import charts, store, ui
from app.runs import no_run, run_label
from app.wafer import NOTE, simulate

RISK_FILE = "risk_scores.csv"
COLUMNS = ("run_id", "timestamp", "label", "risk_score", "flagged", "top_signals")
SPEEDS = {"1 run/s": 1, "3 runs/s": 3, "10 runs/s": 10, "30 runs/s": 30}
POS, PLAYING, SPEED, SCRUB, SHOWN_RUN = ("replay_pos", "replay_playing", "replay_speed",
                                         "replay_scrub", "replay_run")
TICK_S = 1.0


def load(run_dir: Path) -> pd.DataFrame | None:
    """The test-period runs in time order (None for a run made before the risk ranking)."""
    frame = store.read_csv(run_dir, RISK_FILE, COLUMNS)
    if frame is None:
        return None
    frame = frame.assign(timestamp=pd.to_datetime(frame.timestamp))
    return frame.sort_values(["timestamp", "run_id"], kind="mergesort").reset_index(drop=True)


def alarm_cutoff(frame: pd.DataFrame) -> float:
    """The lowest risk score that raised an alarm."""
    flagged = frame.loc[frame.flagged == 1, "risk_score"]
    return float(flagged.min()) if not flagged.empty else 1.0


def totals(frame: pd.DataFrame, shown: int) -> dict:
    """Running totals after the first ``shown`` runs."""
    seen = frame.iloc[:shown]
    alarms = int(seen.flagged.sum())
    caught = int(((seen.flagged == 1) & (seen.label == 1)).sum())
    fails = int(seen.label.sum())
    return {"runs": shown, "alarms": alarms, "caught": caught, "fails": fails,
            "missed": fails - caught, "false_alarms": alarms - caught,
            "precision": caught / alarms if alarms else None}


def render(run_dir: Path | None) -> None:
    ui.page_header("Line Replay")
    frame = load(run_dir) if run_dir else None
    if frame is None or frame.empty:
        if run_dir is None:
            no_run("replay")
        else:
            st.info("The replay needs the risk ranking, which was added after this run was "
                    "made. Choose the reference run in the sidebar, or start a new run.",
                    icon=":material/history:")
        return

    st.caption(run_label(run_dir),
               help="The test period run by run, with this run's own alarms: nothing is "
                    "re-scored. Alarms are the riskiest share of the test period (the run's "
                    "alarm budget), so the totals at the end match Investigation & Report.")
    state = st.session_state
    if state.get(SHOWN_RUN) != str(run_dir):  # another run: start from the beginning
        state[SHOWN_RUN], state[POS], state[PLAYING] = str(run_dir), 0, False
    # The controls and the view are one fragment, playing or not, and only its timer changes:
    # Play and Pause redraw the same elements in the same places, so the page does not jump.
    ticking = bool(state[PLAYING])
    st.fragment(_replay, run_every=TICK_S if ticking else None)(str(run_dir), ticking)


def _replay(run_dir: str, ticking: bool) -> None:
    """The controls and the view. While playing, each tick advances by the chosen speed."""
    state = st.session_state
    frame = load(Path(run_dir))
    if frame is None:
        return
    n = len(frame)
    if ticking and state[PLAYING]:
        state[POS] = min(state[POS] + SPEEDS.get(state.get(SPEED) or "", 3), n)
        if state[POS] >= n:
            state[PLAYING] = False
    if bool(state[PLAYING]) != ticking:  # Play, Pause or the end: start or stop the timer
        st.rerun(scope="app")
    _controls(n)
    _view(frame, state[POS])


def _controls(n: int) -> None:
    state = st.session_state
    with st.container(key="card-replay-controls"):
        play, restart, step, end, speed = st.columns([1.2, 1, 1, 1, 3],
                                                     vertical_alignment="bottom")
        # one button whose label changes (the key is its identity): swapping two buttons
        # showed both for a moment and moved the page
        playing = bool(state[PLAYING])
        play.button("Pause" if playing else "Play", key="replay-toggle",
                    icon=":material/pause:" if playing else ":material/play_arrow:",
                    type="primary", on_click=_toggle, args=(n,), width="stretch")
        restart.button("Restart", key="replay-restart", icon=":material/replay:",
                       on_click=lambda: state.update({POS: 0, PLAYING: False}),
                       width="stretch")
        step.button("Next run", key="replay-step", icon=":material/skip_next:",
                    on_click=lambda: state.update({POS: min(state[POS] + 1, n),
                                                   PLAYING: False}), width="stretch")
        end.button("End", key="replay-end", icon=":material/last_page:",
                   on_click=lambda: state.update({POS: n, PLAYING: False}), width="stretch")
        speed.segmented_control("Speed", list(SPEEDS), key=SPEED, default="3 runs/s",
                                label_visibility="collapsed")
        state[SCRUB] = state[POS]  # always shown (follows the line while playing): no jump
        st.slider("Position in the test period", 0, n, key=SCRUB, disabled=state[PLAYING],
                  label_visibility="collapsed",
                  on_change=lambda: state.update({POS: state[SCRUB]}))


def _toggle(n: int) -> None:
    """Play or Pause."""
    state = st.session_state
    if state[PLAYING]:
        state[PLAYING] = False
        return
    if state[POS] >= n:
        state[POS] = 0
    state[PLAYING] = True


def _view(frame: pd.DataFrame, shown: int) -> None:
    n = len(frame)
    t = totals(frame, shown)
    current = frame.iloc[shown - 1] if shown else None
    ui.kpis([
        ("Runs replayed", f"{shown} of {n}",
         current.timestamp.strftime("%d %b %Y %H:%M") if current is not None else "not started",
         "Test-period runs in time order."),
        ("Alarms raised", str(t["alarms"]),
         f"{t['false_alarms']} false alarm{'' if t['false_alarms'] == 1 else 's'}",
         "Runs at or above the alarm cutoff so far."),
        ("Failing runs caught", f"{t['caught']} of {t['fails']}", f"{t['missed']} missed",
         "Failing runs so far that raised an alarm."),
        ("Alarm precision", "n/a" if t["precision"] is None else f"{t['precision']:.1%}",
         "true alarms", "Share of the alarms so far that were failing runs."),
    ])
    if shown == n:
        st.success(f"Replay finished: {t['alarms']} alarms caught {t['caught']} of "
                   f"{t['fails']} failing runs, the same totals as the Investigation & Report "
                   "page.", icon=":material/flag:")

    alarms = frame.iloc[:shown]
    alarms = alarms[alarms.flagged == 1].iloc[::-1].head(8)

    def stream() -> None:
        charts.replay_stream(frame, shown, alarm_cutoff(frame), "replay-stream")
        st.caption("Rings: alarms. Amber: runs that failed. Dotted line: the alarm cutoff.")

    def wafer() -> None:
        if current is None:
            st.caption("Press Play or Next run to start the line.")
        else:
            wafer_view(current, "replay-wafer", height=200, compact=True)

    # Phase 8.7: the stream beside the wafer and the latest alarms (on a phone, three tabs)
    ui.cards([[("Risk score of each run as it comes off the line", stream, "Risk stream")],
              [("Newest run: simulated wafer", wafer, "Wafer"),
               ("Latest alarms", lambda: _latest(alarms), "Alarms")]], "replay",
             widths=[3, 2])


def _latest(alarms: pd.DataFrame) -> None:
    """The newest alarms first."""
    if alarms.empty:
        st.caption("No alarm yet.")
        return
    ui.table(pd.DataFrame({
        "time": alarms.timestamp.dt.strftime("%d %b %H:%M"),
        "run": alarms.run_id,
        "risk score": alarms.risk_score,
        "outcome": alarms.label.map({1: "failed: caught", 0: "passed: false alarm"}),
        "top signals": alarms.top_signals.fillna(""),
    }), {"risk score": st.column_config.NumberColumn(format="%.3f")}, max_rows=8)


def wafer_view(run: pd.Series, key: str, height: int = 300, compact: bool = False) -> None:
    """A run's simulated wafer and what is known about the run (also on Investigation &
    Report)."""
    failed = int(run.label) == 1
    wafer = simulate(int(run.run_id), failed, float(run.risk_score))
    outcome = ":orange-badge[failed]" if failed else ":gray-badge[passed]"
    alarm = ":blue-badge[alarm]" if int(run.flagged) == 1 else ":gray-badge[no alarm]"
    st.markdown(f"**Run {int(run.run_id)}** {outcome} {alarm} · risk {run.risk_score:.3f}",
                help=NOTE if compact else None)  # compact: the note as a tooltip
    charts.wafer_3d(wafer, key, height=height)
    pattern = f" · pattern: {wafer.pattern}" if wafer.pattern else ""
    signals = run.top_signals if isinstance(run.top_signals, str) and run.top_signals else "none"
    st.caption(f"Simulated die yield {wafer.die_yield:.0%} ({wafer.bad_dies} of {wafer.dies} "
               f"dies defective){pattern}. Top signals (measured): {signals}.")
    if not compact:
        st.caption(NOTE)
