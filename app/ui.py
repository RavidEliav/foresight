"""Shared UI helpers: page style, headers, badges, environment badge, the developer view and
friendly errors."""

from __future__ import annotations

import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from foresight.settings import Settings

ENV_COLORS = {"main": "green", "dev": "orange", "local": "gray"}
CONFIDENCE_COLORS = {"high": "green", "medium": "orange", "low": "gray"}
STATUS_COLORS = {"PASS": "green", "WARNING": "orange", "ERROR": "red"}
LOGO = Path(__file__).parent / "assets" / "logo.svg"
LOGO_IMAGE = str(LOGO)  # chat avatar of the assistant

# Subtle semiconductor motifs: a die-grid background with soft light, gradient headings, a
# circuit-trace rule under page titles, and frosted-glass surfaces (cards, KPI tiles, metrics,
# sidebar, the selected page, expanders, tabs). Cards are keyed containers ("card-...") and the
# headline KPI row is the keyed container "kpis".
STYLE = """
<style>
:root {
  --fs-glass: linear-gradient(135deg, rgba(255,255,255,.075), rgba(255,255,255,.018));
  --fs-glass-border: rgba(255,255,255,.09);
  --fs-glass-top: rgba(255,255,255,.17);
  --fs-glass-shadow: 0 10px 34px -16px rgba(0,0,0,.7), inset 0 1px 0 rgba(255,255,255,.07);
  --fs-blur: blur(16px) saturate(150%);
}
.stApp {
  background:
    radial-gradient(900px 520px at 6% -8%, rgba(34,211,238,.16), transparent 62%),
    radial-gradient(800px 520px at 102% 8%, rgba(167,139,250,.14), transparent 58%),
    radial-gradient(700px 420px at 55% 108%, rgba(251,191,36,.06), transparent 60%),
    linear-gradient(rgba(148,163,184,.035) 1px, transparent 1px) 0 0 / 32px 32px,
    linear-gradient(90deg, rgba(148,163,184,.035) 1px, transparent 1px) 0 0 / 32px 32px,
    #070B14;
  background-attachment: fixed;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMain"] h1 {
  background: linear-gradient(90deg, #F1F5F9 0%, #67E8F9 55%, #A78BFA 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  letter-spacing: -0.02em;
}
[data-testid="stMain"] h3 { letter-spacing: -0.01em; }
.fs-trace {
  height: 10px; margin: -0.4rem 0 0.2rem 0;
  background:
    radial-gradient(circle, #22D3EE 0 3px, transparent 3.5px) 0 50% / 10px 10px no-repeat,
    linear-gradient(90deg, rgba(34,211,238,.9), rgba(167,139,250,.6) 35%, transparent 80%)
      10px 50% / 100% 1.5px no-repeat;
}
/* glass surfaces */
[class*="st-key-card-"], [data-testid="stMetric"], [data-testid="stExpander"] details {
  background: var(--fs-glass);
  -webkit-backdrop-filter: var(--fs-blur); backdrop-filter: var(--fs-blur);
  border: 1px solid var(--fs-glass-border); border-top-color: var(--fs-glass-top);
  box-shadow: var(--fs-glass-shadow);
}
[class*="st-key-card-"] {
  border-radius: 16px; padding: 1rem 1.15rem;
  transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
}
[class*="st-key-card-"]:hover, [data-testid="stMetric"]:hover {
  border-color: rgba(34,211,238,.38);
  box-shadow: var(--fs-glass-shadow), 0 0 26px -8px rgba(34,211,238,.35);
}
[class*="st-key-card-hyp"]:hover { transform: translateY(-2px); }
.st-key-card-summary { border-left: 3px solid #22D3EE !important; }
.fs-headline {
  font-family: 'Space Grotesk', sans-serif; font-size: 1.22rem; line-height: 1.45;
  color: #F1F5F9; margin: .2rem 0 .4rem 0;
}
.fs-label {
  font-size: .72rem; letter-spacing: .12em; text-transform: uppercase; color: #7DD3FC;
  font-weight: 600;
}
.fs-section {
  font-size: .78rem; letter-spacing: .14em; text-transform: uppercase; color: #94A3B8;
  font-weight: 600; margin: 1.4rem 0 .2rem 0; padding-top: .9rem;
  border-top: 1px solid rgba(148,163,184,.14);
}
[data-testid="stMetric"] { border-radius: 14px; padding: .8rem 1rem; }
[data-testid="stMetricLabel"] p {
  font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; color: #94A3B8;
  white-space: normal;
}
[data-testid="stMetricLabel"] [data-testid="stMarkdownContainer"] { overflow: visible; }
[data-testid="stMetricDelta"] { color: #94A3B8; }
[data-testid="stMetricDelta"] div { white-space: normal; overflow: visible; }
[data-testid="stColumn"] > div > [data-testid="stElementContainer"] > [data-testid="stMetric"],
.st-key-kpis [data-testid="stMetric"] { height: 100%; }
.st-key-kpis [data-testid="stMetric"] { padding: 1rem 1.15rem; }
.st-key-kpis [data-testid="stMetricValue"] > div {
  font-family: 'Space Grotesk', sans-serif; font-size: 2.1rem; font-weight: 700;
  background: linear-gradient(90deg, #F8FAFC, #67E8F9); -webkit-background-clip: text;
  background-clip: text; color: transparent;
}
[data-testid="stExpander"] details { border-radius: 14px; }
/* sidebar: frosted panel (brand, menu and recent questions are styled further below) */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(13,21,38,.72), rgba(7,11,20,.6)) !important;
  -webkit-backdrop-filter: var(--fs-blur); backdrop-filter: var(--fs-blur);
}
/* tabs */
[data-baseweb="tab-list"] { gap: .4rem; border-bottom: 1px solid rgba(148,163,184,.14); }
[data-baseweb="tab"] { padding: .45rem .9rem; border-radius: 10px 10px 0 0; }
[data-baseweb="tab"][aria-selected="true"] { background: rgba(34,211,238,.08); }
[data-baseweb="tab"] p { font-size: .95rem; font-weight: 600; }
/* Run Pipeline stepper (app/stepper.py) */
.fs-stepper { display: flex; align-items: stretch; margin: .3rem 0 .5rem 0; }
.fs-stage {
  --c: #475569; flex: 1 1 0; min-width: 0; position: relative; display: flex;
  flex-direction: column; gap: .3rem; padding: .85rem .9rem .8rem; border-radius: 16px;
  background: var(--fs-glass); -webkit-backdrop-filter: var(--fs-blur);
  backdrop-filter: var(--fs-blur); border: 1px solid var(--fs-glass-border);
  border-top-color: var(--fs-glass-top); box-shadow: var(--fs-glass-shadow);
  transition: border-color .4s ease, background .4s ease;
}
.fs-stage.fs-done { --c: #34D399; border-color: rgba(52,211,153,.5);
  background: linear-gradient(135deg, rgba(52,211,153,.16), rgba(255,255,255,.02)); }
.fs-stage.fs-failed { --c: #F87171; border-color: rgba(248,113,113,.55);
  background: linear-gradient(135deg, rgba(248,113,113,.18), rgba(255,255,255,.02)); }
.fs-stage.fs-running { --c: #22D3EE; border-color: rgba(34,211,238,.6);
  background: linear-gradient(135deg, rgba(34,211,238,.16), rgba(255,255,255,.02));
  animation: fs-glow 2s ease-in-out infinite; }
.fs-stage.fs-skipped { --c: #64748B; opacity: .55; }
.fs-stage.fs-interrupted, .fs-stage.fs-stopped { --c: #FBBF24; border-color: rgba(251,191,36,.5);
  background: linear-gradient(135deg, rgba(251,191,36,.14), rgba(255,255,255,.02)); }
.fs-stage.fs-pending { opacity: .75; }
.fs-stage-title { font-weight: 600; font-size: .9rem; line-height: 1.25; color: #E2E8F0;
  padding-right: 1.4rem; }
.fs-stage-crew, .fs-stage-meta { font-size: .76rem; color: #94A3B8; line-height: 1.3; }
.fs-stage-meta { margin-top: auto; color: var(--c); font-weight: 600; letter-spacing: .02em; }
.fs-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  margin-right: .35rem; background: #475569; vertical-align: middle; }
.fs-dot.fs-done { background: #34D399; } .fs-dot.fs-failed { background: #F87171; }
.fs-dot.fs-running { background: #22D3EE; animation: fs-blink 1s infinite; }
.fs-dot.fs-skipped { background: #64748B; } .fs-dot.fs-interrupted,
.fs-dot.fs-stopped { background: #FBBF24; }
.fs-badge { position: absolute; top: .6rem; right: .65rem; width: 20px; height: 20px;
  border-radius: 50%; display: grid; place-items: center; font-size: .72rem;
  font-weight: 800; color: #070B14; background: var(--c); }
.fs-pending .fs-badge { background: transparent; border: 1.5px dashed #475569; }
.fs-running .fs-badge { background: transparent; border: 2px solid rgba(34,211,238,.2);
  border-top-color: #22D3EE; animation: fs-spin .9s linear infinite; }
.fs-link { flex: 0 0 18px; align-self: center; height: 2px; background: rgba(148,163,184,.25);
  position: relative; }
.fs-link.fs-gate::after { content: ""; position: absolute; left: 50%; top: 50%; width: 9px;
  height: 9px; border-radius: 2px; transform: translate(-50%, -50%) rotate(45deg);
  background: #334155; }
.fs-gate-pass, .fs-gate-pass::after { background: #34D399 !important; }
.fs-gate-warning, .fs-gate-warning::after { background: #FBBF24 !important; }
.fs-gate-error, .fs-gate-error::after { background: #F87171 !important; }
.fs-art { width: 100%; height: 46px; margin: .1rem 0 .15rem 0; }
@keyframes fs-spin { to { transform: rotate(360deg); } }
@keyframes fs-spin-row { from { transform: translateY(-50%) rotate(0deg); }
  to { transform: translateY(-50%) rotate(360deg); } }  /* a phone: the badge is centered */
@keyframes fs-glow {
  50% { box-shadow: var(--fs-glass-shadow), 0 0 26px -4px rgba(34,211,238,.6); } }
@keyframes fs-blink { 0%, 100% { opacity: .25; } 50% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) {
  .fs-stepper *, .fs-stage, .fs-o { animation: none !important; } }
/* sidebar brand, menu and recent questions */
.fs-brand { padding: .2rem 0 .3rem 0; }
.fs-wordmark { font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 2.3rem;
  line-height: 1; letter-spacing: .01em; color: #F1F5F9; display: flex; align-items: center; }
.fs-o { display: inline-block; width: 3.3rem; height: 3.3rem; margin: 0 .02em; }
.fs-o { animation: fs-brand-glow 4s ease-in-out infinite; }
@keyframes fs-brand-glow { 0%, 100% { filter: drop-shadow(0 0 3px rgba(34,211,238,.35)); }
  50% { filter: drop-shadow(0 0 10px rgba(167,139,250,.6)); } }
.fs-tagline { margin-top: .45rem; font-size: .74rem; letter-spacing: .14em;
  text-transform: uppercase; color: #7DD3FC; }
.fs-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.st-key-nav { gap: .2rem; }
.st-key-nav [data-testid="stPageLink"] a { border-radius: 10px; padding: .3rem .6rem;
  border: 1px solid transparent; }
.st-key-nav [data-testid="stPageLink"] a:hover { background: rgba(255,255,255,.05); }
.st-key-nav-active [data-testid="stPageLink"] a {
  background: var(--fs-glass); -webkit-backdrop-filter: var(--fs-blur);
  backdrop-filter: var(--fs-blur); border: 1px solid var(--fs-glass-border);
  border-left: 2px solid #22D3EE; box-shadow: var(--fs-glass-shadow),
  0 0 18px -6px rgba(34,211,238,.45); }
.st-key-nav-active [data-testid="stPageLink"] p { font-weight: 600; color: #F1F5F9; }
.fs-side-label { font-size: .7rem; letter-spacing: .14em; text-transform: uppercase;
  color: #94A3B8; font-weight: 600; margin-top: .6rem; }
.st-key-recent { gap: 0; }
.st-key-recent button { justify-content: flex-start; text-align: left; min-height: 1.9rem;
  padding-left: .4rem; }
.st-key-recent button > div, .st-key-recent button [data-testid="stMarkdownContainer"] {
  justify-content: flex-start; width: 100%; text-align: left; }
.st-key-recent button p { white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  font-size: .84rem; color: #CBD5E1; }
/* signed-in person (Phase 8.6): the "Hi, name" menu top right, above the page title.
   No angle brackets in this style block: the HTML sanitizer drops a style that has them. */
/* Phase 8.7: on the title's line, taking no height of its own */
.st-key-topbar { position: absolute; top: -.2rem; right: 0; width: auto !important;
  z-index: 10; }
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
  position: relative; }
.st-key-topbar [data-testid="stPopover"] button p { font-weight: 600; color: #E2E8F0; }
/* Streamlit's header is a transparent strip over the top of the page; on a phone it lay over
   the "Hi, name" menu and took its taps. Only its own buttons take taps now. */
[data-testid="stHeader"], [data-testid="stHeader"] * { pointer-events: none; }
[data-testid="stHeader"] button, [data-testid="stHeader"] button *,
[data-testid="stHeader"] a { pointer-events: auto; }
.fs-gap { height: .4rem; }
/* Phase 8.7: one screen per page. Less space above the title, compact headline tiles, and
   tables whose long text wraps instead of being cut off. */
[data-testid="stMainBlockContainer"] { padding-top: 2.6rem; padding-bottom: 3rem; }
[data-testid="stMain"] h1 { font-size: 2.15rem; padding: .1rem 0 .35rem 0; }
.st-key-kpis [data-testid="stMetric"] { padding: .7rem 1rem; }
.st-key-kpis [data-testid="stMetricValue"] > div { font-size: 1.85rem; }
[class*="st-key-card-tabs"] [data-baseweb="tab-list"] { margin-top: -.3rem; }
.st-key-card-replay-controls { padding-top: .7rem; padding-bottom: .5rem; }
[data-testid="stTable"] table { font-size: .84rem; }
[data-testid="stTable"] td, [data-testid="stTable"] th { padding: .3rem .55rem;
  white-space: normal; vertical-align: top; }
/* Ask Foresight: the conversation scrolls in a box that fills the window between the scope
   line and the examples above the question bar, so those stay in place */
/* the examples right above the question bar, compact */
.st-key-ask-bottom [data-testid="stButtonGroup"] button { min-height: 1.7rem;
  padding: .1rem .6rem; }
.st-key-ask-bottom [data-testid="stButtonGroup"] p { font-size: .8rem; }
.st-key-chat-log, [data-testid="stLayoutWrapper"]:has(.st-key-chat-log) {
  height: calc(100dvh - 27rem) !important; min-height: 12rem !important;
  max-height: none !important; flex: 0 0 auto !important; }
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding: 1.4rem .75rem 2rem .75rem; }
  [data-testid="stMain"] h1 { font-size: 1.6rem; }
  .st-key-kpis [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: .5rem; }
  .st-key-kpis [data-testid="stColumn"] { flex: 1 1 40% !important; min-width: 40% !important; }
  .st-key-kpis [data-testid="stMetric"] { padding: .55rem .7rem; }
  .st-key-kpis [data-testid="stMetricValue"] > div { font-size: 1.45rem; }
  [class*="st-key-card-"] { padding: .75rem .8rem; }
  .st-key-chat-log, [data-testid="stLayoutWrapper"]:has(.st-key-chat-log) {
    height: calc(100dvh - 31.5rem) !important; }
  /* phone view: one screen per page (the pages draw one card with tabs, ui.phone) */
  /* an iPhone zooms the page into a text field under 16 px when it is tapped */
  [data-testid="stApp"] input, [data-testid="stApp"] textarea {
    font-size: 16px !important; }
  [data-testid="stMainBlockContainer"] { padding-top: 2.2rem; }
  [data-testid="stMain"] h1 { font-size: 1.4rem; padding: 0 0 .15rem 0; }
  [data-testid="stMainBlockContainer"] [data-testid="stCaptionContainer"] { font-size: .7rem; }
  [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: .55rem; }
  .st-key-kpis [data-testid="stHorizontalBlock"] { gap: .4rem; }
  .st-key-kpis [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(5))
    > [data-testid="stColumn"] { flex: 1 1 30% !important; min-width: 30% !important; }
  .st-key-kpis [data-testid="stMetric"] { padding: .3rem .5rem; }
  .st-key-kpis [data-testid="stMetricLabel"] p { font-size: .62rem; }
  .st-key-kpis [data-testid="stMetricValue"] > div { font-size: 1.05rem; }
  .st-key-kpis [data-testid="stMetricDelta"] { font-size: .64rem; padding: 0 .3rem; }
  [class*="st-key-card-"] { padding: .55rem .65rem; }
  [data-baseweb="tab"] p { font-size: .82rem; }
  /* a long tab scrolls inside its card, so the page itself fits */
  [data-testid="stMainBlockContainer"] [data-testid="stTabPanel"] {
    max-height: max(13rem, calc(100dvh - 26rem)); overflow-y: auto; }
  .st-key-report-main [data-testid="stTabPanel"] {
    max-height: max(11rem, calc(100dvh - 31rem)); }
  .st-key-card-cleaning { max-height: max(12rem, calc(100dvh - 30rem)); overflow-y: auto; }
  /* Run Pipeline: the stages as one-line rows */
  .fs-stepper { flex-direction: column; gap: .3rem; }
  .fs-link { display: none; }
  .fs-stage { flex-direction: row; align-items: center; gap: .6rem; padding: .4rem .6rem; }
  .fs-art { flex: 0 0 40px; width: 40px; height: 26px; margin: 0; }
  .fs-stage-title { flex: 1 1 auto; font-size: .8rem; padding-right: 0; }
  .fs-stage-crew { display: none; }
  .fs-stage-meta { margin: 0 1.7rem 0 0; white-space: nowrap; font-size: .7rem; }
  .fs-badge { top: 50%; transform: translateY(-50%); width: 18px; height: 18px; }
  .fs-running .fs-badge { animation: fs-spin-row .9s linear infinite; }
  /* Line Replay: the four buttons on one line (short words), the speed under them */
  .st-key-card-replay-controls [data-testid="stHorizontalBlock"] { flex-wrap: wrap;
    gap: .35rem; }
  .st-key-card-replay-controls [data-testid="stColumn"] { flex: 1 1 18% !important;
    min-width: 18% !important; }
  .st-key-card-replay-controls [data-testid="stColumn"]:last-child {
    flex: 1 1 100% !important; min-width: 100% !important; }
  .st-key-card-replay-controls [data-testid="stSliderThumbValue"] { display: none; }
  .st-key-card-replay-controls { padding-top: .45rem; padding-bottom: .2rem; }
  .st-key-card-replay-controls [data-testid="stSlider"] { margin-top: -.9rem; }
  .st-key-card-replay-controls [data-testid="stColumn"]:not(:last-child) button p {
    font-size: .8rem; }  /* short words, no icons (replay_page) */
}
/* Phase 8.10: less of Streamlit around the app: no colour strip on top. (Its "Running..." badge
   lives in the toolbar, which toolbarMode "minimal" leaves out.) Instead, while the page works,
   a thin cyan line runs across the top. It shows only after 0.6 s, so the short timed reruns
   (progress every 2 s, the replay ticks) don't make it flash. */
[data-testid="stDecoration"] { display: none !important; }
.stApp[data-test-script-state="running"]::before { content: ""; position: fixed; top: 0;
  left: 0; right: 0; height: 3px; z-index: 1000000; pointer-events: none; opacity: 0;
  background: linear-gradient(90deg, transparent, #22D3EE, #A78BFA, transparent);
  background-size: 40% 100%; background-repeat: no-repeat;
  animation: fs-loading 1.1s ease-in-out infinite, fs-show .2s ease-out .6s forwards; }
@keyframes fs-loading { from { background-position: -40% 0; } to { background-position: 140% 0; } }
@keyframes fs-show { to { opacity: 1; } }
/* the sign-in page (auth.gate_page): no sidebar, one centred card */
.st-key-gate-page { max-width: 30rem; margin: 3vh auto 0 auto; }
.fs-hero { text-align: center; }
.fs-hero .fs-wordmark { font-size: 3.1rem; justify-content: center; }
.fs-hero .fs-o { width: 4.3rem; height: 4.3rem; }
.fs-hero .fs-tagline { margin: .3rem 0 1.1rem 0; }
.fs-pitch { font-size: 1.02rem; line-height: 1.55; color: #CBD5E1; margin: 0 0 .9rem 0; }
/* on a computer the pitch reaches a little past the card, so it is two lines */
@media (min-width: 640px) { .fs-pitch { margin: 0 -1.5rem .9rem -1.5rem; } }
.fs-benefits { list-style: none; padding: 0; margin: 0 auto 1.2rem auto; display: inline-grid;
  gap: .35rem; text-align: left; }
.fs-benefits li { color: #E2E8F0; font-size: .95rem; }
.fs-benefits li::before { content: "✓"; color: #22D3EE; font-weight: 700;
  margin-right: .55rem; }
.st-key-sign-in button { background: #FFFFFF !important; color: #1F1F1F !important;
  border: 1px solid #DADCE0 !important; font-weight: 600; }
.st-key-sign-in button p { color: #1F1F1F !important; }
</style>
"""


# Google's "G" (its four colours) on the sign-in button, as Google's sign-in guidelines show it
GOOGLE_G = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><path fill="#EA4335" d="M2'
            '4 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.6 13.3l7.9 6'
            '.1C12.4 13.6 17.7 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5'
            'H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.7c4.3-4 6.9-9.9 6.9-17.1z"/><path fill="#FBBC'
            '05" d="M10.5 28.6c-.5-1.4-.8-2.9-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4'
            ' 2.6 10.7l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.7c-'
            '2.1 1.4-4.8 2.3-8.5 2.3-6.3 0-11.6-4.1-13.5-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z"/></s'
            'vg>')


def apply_style() -> None:
    """The theme, plus what needs the logo: the spinner is the spinning wafer, not
    Streamlit's ring (Phase 8.10)."""
    st.html(STYLE)
    st.html(f"""<style>
[data-testid="stSpinnerIcon"] {{ border: none !important; width: 1.15rem !important;
  height: 1.15rem !important; background: url("{_logo_uri()}") center / contain no-repeat;
  animation: fs-spin 1.3s linear infinite !important; }}
.st-key-sign-in button::before {{ content: ""; width: 1.15rem; height: 1.15rem;
  margin-right: .55rem; background: url("{_svg_uri(GOOGLE_G)}") center / contain no-repeat; }}
</style>""")


def _svg_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _logo_uri() -> str:
    """The logo as a data URI (st.html drops inline <svg>)."""
    return "data:image/svg+xml;base64," + base64.b64encode(LOGO.read_bytes()).decode()


def brand() -> None:
    """Sidebar header: the wordmark, whose "o" is the wafer logo, and the tagline."""
    st.sidebar.html(
        '<div class="fs-brand"><div class="fs-wordmark" aria-hidden="true">F'
        f'<img class="fs-o" alt="" src="{_logo_uri()}">resight</div>'
        '<span class="fs-sr">Foresight</span>'
        '<div class="fs-tagline">Semiconductor yield intelligence</div></div>')


def hero_html() -> str:
    """The sign-in page's top: the large wordmark, what Foresight does, three benefits."""
    return ('<div class="fs-hero fs-brand"><div class="fs-wordmark" aria-hidden="true">F'
            f'<img class="fs-o" alt="" src="{_logo_uri()}">resight</div>'
            '<span class="fs-sr">Foresight</span>'
            '<div class="fs-tagline">Semiconductor yield intelligence</div>'
            '<p class="fs-pitch">Find failing production runs early, see which sensors go with '
            'them, and get a cited engineering report, on the SECOM fab data.</p>'
            '<ul class="fs-benefits"><li>Checks the data against a contract</li>'
            '<li>Ranks the riskiest runs and flags anomalies</li>'
            '<li>Explains them in cited reports and a chat</li></ul></div>')


def sidebar_nav(pages: list, current) -> None:
    """The page menu as page links (Streamlit's own menu is hidden so the brand can come
    first); the current page gets the glass highlight."""
    with st.sidebar.container(key="nav"):
        for page in pages:
            active = page.url_path == current.url_path
            with st.container(key="nav-active" if active else f"nav-{page.url_path or 'home'}"):
                st.page_link(page, label=page.title, icon=page.icon, width="stretch")


def recent_questions(run_dir: Path | None, settings: Settings, ask_page, user: str) -> None:
    """The signed-in person's recent questions about the selected run and about all runs; a
    click opens the answer on the Ask Foresight page."""
    if run_dir is None:
        return
    from app import store
    from app.runs import local_time

    items = store.recent_questions(settings, run_dir, user)
    if not items:
        return
    st.sidebar.html('<div class="fs-side-label">Recent questions</div>')
    with st.sidebar.container(key="recent"):
        for i, item in enumerate(items):
            every = item.get("run") == store.ALL_RUNS
            scope = "about all runs, " if every else ""
            if st.button(item["question"], key=f"recent-{i}", type="tertiary", width="stretch",
                         icon=":material/stacks:" if every else None,
                         help=f"{item['question']} ({scope}asked {local_time(item['time'])})"):
                st.session_state["chat_open"] = item
                st.switch_page(ask_page)


def page_header(title: str) -> None:
    st.title(title)
    st.html('<div class="fs-trace"></div>')


def section_label(text: str) -> None:
    """Uppercase divider between the main content and the extended data."""
    st.html(f'<div class="fs-section">{text}</div>')


def run_report_button(run_dir: Path) -> None:
    """In the sidebar under the run choice: download the run report, every result page of
    that run in one PDF (Phase 8.8; the one place for it). The PDF is made when the button is
    pressed, not on every page."""
    from app import store
    from app.runs import analysis_name, local_zone

    zone = local_zone()  # read now: the PDF is made outside the page run, without the browser
    name = analysis_name(run_dir)
    st.sidebar.download_button(
        "Download the full report", data=lambda: store.run_report(run_dir, zone, name),
        file_name=f"Foresight - {name} - Full report.pdf", mime="application/pdf",
        key="run-report", icon=":material/picture_as_pdf:", width="stretch", type="primary",
        help="Every result page of this analysis in one PDF: Data quality, Data insights, "
             "Model, Findings (with the engineering report) and the report's checks.")
    st.sidebar.caption("All result pages of this analysis in one PDF.")  # the whole run, not a page


def extended(labels: list[str], key: str) -> str | None:
    """Extended data: a row of tabs that are all closed until one is pressed (pressing it
    again closes it). Returns the open tab's label; only that tab is drawn. On a phone, one
    dropdown, so the page fits the screen."""
    if phone():
        return st.selectbox("Extended data", labels, index=None, key=f"extended-{key}",
                            placeholder="Extended data", label_visibility="collapsed",
                            filter_mode=None)
    section_label("Extended data")
    return st.segmented_control("Extended data", labels, key=f"extended-{key}",
                                label_visibility="collapsed")


def phone() -> bool:
    """A phone's browser (its user agent says Mobile, or iPhone): the pages put their cards
    into one card with tabs, and charts are lower, so a page fits the phone's screen."""
    try:
        agent = st.context.headers.get("User-Agent") or ""
    except Exception:  # no browser (tests, bare mode)
        return False
    return "Mobi" in agent or "iPhone" in agent


def search() -> str | None:
    """A long dropdown's search: typing filters it on a computer. On a phone a tap opened the
    keyboard to type instead of the list, so there it only opens the list (None)."""
    return None if phone() else "fuzzy"


def cards(groups: list[list[tuple]], key: str, widths: list[int] | None = None) -> None:
    """The main cards of a page. ``groups`` are lists of (label, draw) or (label, draw,
    short label). On a computer each group is a card, side by side: a group of one is a card
    under its label, a group of several a card with tabs. On a phone every item is a tab of
    one card (with the short label), so the page fits the screen."""
    if phone():
        items = [item for group in groups for item in group]
        with st.container(key=f"card-tabs-{key}"):
            for item, tab in zip(items, st.tabs([i[2] if len(i) > 2 else i[0] for i in items]),
                                 strict=True):
                with tab:
                    item[1]()
        return
    columns = st.columns(widths or [1] * len(groups), gap="medium")
    for i, (column, group) in enumerate(zip(columns, groups, strict=True)):
        if len(group) == 1:
            with column, st.container(key=f"card-{key}-{i}", height="stretch"):
                label(group[0][0])
                group[0][1]()
            continue
        with column, st.container(key=f"card-tabs-{key}-{i}", height="stretch"):
            for item, tab in zip(group, st.tabs([item[0] for item in group]), strict=True):
                with tab:
                    item[1]()


def kpis(items: list[tuple[str, str, str | None, str | None]]) -> None:
    """The page's headline numbers as large glass tiles of equal height: (label, value,
    comparison, help). The comparison is a neutral second line (no arrow, no colour)."""
    with st.container(key="kpis"):
        for column, (name, value, comparison, note) in zip(st.columns(len(items)), items,
                                                           strict=True):
            column.metric(name, value, comparison, delta_color="off", delta_arrow="off",
                          help=note, height="stretch")


WRAP_CHARS = 60  # a column with longer text makes the table wrap its cells (Phase 8.7)
MAX_TABLE_PX = 1000  # wider than a laptop's page: the table wraps its cells instead


def _shown(value) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    return "" if value is None else str(value)


def _formatted(value, config) -> str:
    """A cell as text with the column's number format ("percent", "%.3f"), when it has one."""
    fmt = ((config or {}).get("type_config") or {}).get("format") \
        if isinstance(config, dict) else None
    try:
        if fmt and value is not None and not pd.isna(value):
            return f"{float(value):.1%}" if fmt == "percent" else fmt % float(value)
    except (TypeError, ValueError):
        pass
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) \
        else _shown(value)


def column_widths(frame) -> dict[str, int]:
    """Each column as wide as its header or its longest value, in pixels, so no header or
    value is cut off."""
    return {str(c): int(7.4 * max([len(str(c)), *(len(_shown(v)) for v in frame[c])]) + 30)
            for c in frame.columns}


def table(frame, column_config: dict | None = None, max_rows: int = 12) -> None:
    """A compact table that fits its content (Phase 8.7): every column as wide as its header
    or longest value, height fitted to the rows. A table with long text (more than
    ``WRAP_CHARS`` characters in a cell), or wider than a laptop's page, is shown with wrapped
    cells instead, so nothing is hidden behind a cut-off column."""
    longest = max((len(_shown(v)) for c in frame.columns for v in frame[c]), default=0)
    widths = column_widths(frame)
    if longest > WRAP_CHARS or sum(widths.values()) > MAX_TABLE_PX:
        shown = frame.head(max_rows) if len(frame) > max_rows else frame
        shown = pd.DataFrame({column: [_formatted(v, (column_config or {}).get(column))
                                       for v in shown[column]] for column in shown.columns})
        st.table(shown, hide_index=True)
        if len(frame) > max_rows:
            st.caption(f"The first {max_rows} of {len(frame)} rows.")
        return
    config = dict(column_config or {})
    for name, width in widths.items():
        given = config.get(name, {})
        if isinstance(given, dict):  # a page's own setting (format, label) keeps the width
            config[name] = {**given, "width": given.get("width") or width}
    rows = min(len(frame), max_rows)
    st.dataframe(frame, hide_index=True, width="content", row_height=30,
                 height=38 + 30 * rows + 2, column_config=config)


def label(text: str) -> None:
    """Small uppercase section label inside a card."""
    st.html(f'<div class="fs-label">{text}</div>')


def md(text: str) -> str:
    """LLM text for st.markdown: '$' would start LaTeX."""
    return text.replace("$", r"\$")


def environment_badge(settings: Settings) -> None:
    """Which app a developer is in, on dev and a local checkout; main is the product, so it
    shows no environment (Phase 8.10)."""
    env = settings.environment
    if env == "main":
        return
    st.sidebar.markdown(f":{ENV_COLORS.get(env, 'blue')}-badge[Environment: {env}]")


def developer() -> bool:
    """True for the developer view (Phase 8.6): technical details, Extended data, Trends and
    Users & access. Closed by default: no signed-in developer, no developer view."""
    viewer = st.session_state.get("viewer")
    return bool(viewer is not None and viewer.developer)


def user_email() -> str:
    """The signed-in email (empty for a local checkout without sign-in)."""
    viewer = st.session_state.get("viewer")
    return viewer.email if viewer is not None else ""


def friendly_error(message: str) -> None:
    st.error(message, icon=":material/error:")
