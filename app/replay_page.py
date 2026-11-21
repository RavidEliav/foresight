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

    st.caption(run_label(run_dir))
    st.caption("The test period played back run by run, as the line would have seen it. "
               "Alarms are this run's own: the riskiest share of the test period (its alarm "
               "budget), so the totals at the end match the Investigation & Report page. "
               "Nothing is re-scored.")
    state = st.session_state
    if state.get(SHOWN_RUN) != str(run_dir):  # another run: start from the beginning
        state[SHOWN_RUN], state[POS], state[PLAYING] = str(run_dir), 0, False
    _controls(len(frame))
    if state[PLAYING]:
        _live(str(run_dir))
    else:
        _view(frame, state[POS])


def _controls(n: int) -> None:
    state = st.session_state
    with st.container(key="card-replay-controls"):
        play, restart, step, end, speed = st.columns([1.2, 1, 1, 1, 3],
                                                     vertical_alignment="bottom")
        if state[PLAYING]:
            play.button("Pause", key="replay-pause", icon=":material/pause:", type="primary",
                        on_click=lambda: state.update({PLAYING: False}), width="stretch")
        else:
            play.button("Play", key="replay-play", icon=":material/play_arrow:",
                        type="primary", on_click=_play, args=(n,), width="stretch")
        restart.button("Restart", key="replay-restart", icon=":material/replay:",
                       on_click=lambda: state.update({POS: 0, PLAYING: False}),
                       width="stretch")
        step.button("Next run", key="replay-step", icon=":material/skip_next:",
                    on_click=lambda: state.update({POS: min(state[POS] + 1, n),
                                                   PLAYING: False}), width="stretch")
        end.button("End", key="replay-end", icon=":material/last_page:",
                   on_click=lambda: state.update({POS: n, PLAYING: False}), width="stretch")
        speed.segmented_control("Speed", list(SPEEDS), key=SPEED, default="3 runs/s")
        if not state[PLAYING]:
            state[SCRUB] = state[POS]
            st.slider("Position in the test period", 0, n, key=SCRUB,
                      on_change=lambda: state.update({POS: state[SCRUB]}))


def _play(n: int) -> None:
    state = st.session_state
    if state[POS] >= n:
        state[POS] = 0
    state[PLAYING] = True


@st.fragment(run_every=TICK_S)
def _live(run_dir: str) -> None:
    """One tick of the replay: advance by the chosen speed and redraw."""
    state = st.session_state
    frame = load(Path(run_dir))
    if frame is None or not state.get(PLAYING):
        return
    n = len(frame)
    state[POS] = min(state[POS] + SPEEDS.get(state.get(SPEED) or "", 3), n)
    _view(frame, state[POS])
    if state[POS] >= n:
        state[PLAYING] = False
        st.rerun()


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

    left, right = st.columns([3, 2], gap="medium")
    with left, st.container(key="card-replay-stream", height="stretch"):
        ui.label("Risk score of each run as it comes off the line")
        charts.replay_stream(frame, shown, alarm_cutoff(frame), "replay-stream")
        st.caption("Rings: alarms. Amber: runs that failed. Dotted line: the alarm cutoff.")
    with right, st.container(key="card-replay-wafer", height="stretch"):
        ui.label("Newest run: simulated wafer")
        if current is None:
            st.caption("Press Play or Next run to start the line.")
        else:
            wafer_view(current, "replay-wafer")

    alarms = frame.iloc[:shown]
    alarms = alarms[alarms.flagged == 1].iloc[::-1].head(8)
    with st.container(key="card-replay-alarms"):
        ui.label("Latest alarms")
        if alarms.empty:
            st.caption("No alarm yet.")
        else:
            ui.table(pd.DataFrame({
                "time": alarms.timestamp.dt.strftime("%d %b %H:%M"),
                "run": alarms.run_id,
                "risk score": alarms.risk_score,
                "outcome": alarms.label.map({1: "failed: caught", 0: "passed: false alarm"}),
                "top signals": alarms.top_signals.fillna(""),
            }), {"risk score": st.column_config.NumberColumn(format="%.3f")}, max_rows=8)


def wafer_view(run: pd.Series, key: str) -> None:
    """A run's simulated wafer and what is known about the run (also on Investigation &
    Report)."""
    failed = int(run.label) == 1
    wafer = simulate(int(run.run_id), failed, float(run.risk_score))
    outcome = ":orange-badge[failed]" if failed else ":gray-badge[passed]"
    alarm = ":blue-badge[alarm]" if int(run.flagged) == 1 else ":gray-badge[no alarm]"
    st.markdown(f"**Run {int(run.run_id)}** {outcome} {alarm} · risk {run.risk_score:.3f}")
    charts.wafer_3d(wafer, key, height=300)
    pattern = f" · pattern: {wafer.pattern}" if wafer.pattern else ""
    signals = run.top_signals if isinstance(run.top_signals, str) and run.top_signals else "none"
    st.caption(f"Simulated die yield {wafer.die_yield:.0%} ({wafer.bad_dies} of {wafer.dies} "
               f"dies defective){pattern}. Top signals (measured): {signals}.")
    st.caption(NOTE)
