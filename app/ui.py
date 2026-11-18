"""Shared UI helpers: page style, headers, badges, environment badge, passcode check and
friendly errors."""

from __future__ import annotations

import base64
import hmac
from pathlib import Path

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
.fs-stage.fs-interrupted { --c: #FBBF24; border-color: rgba(251,191,36,.5);
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
.fs-dot.fs-skipped { background: #64748B; } .fs-dot.fs-interrupted { background: #FBBF24; }
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
</style>
"""


def apply_style() -> None:
    st.html(STYLE)


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


def sidebar_nav(pages: list, current) -> None:
    """The page menu as page links (Streamlit's own menu is hidden so the brand can come
    first); the current page gets the glass highlight."""
    with st.sidebar.container(key="nav"):
        for page in pages:
            active = page.url_path == current.url_path
            with st.container(key="nav-active" if active else f"nav-{page.url_path or 'home'}"):
                st.page_link(page, label=page.title, icon=page.icon, width="stretch")


def recent_questions(run_dir: Path | None, settings: Settings, ask_page) -> None:
    """The selected run's recent chat questions, once the chat is unlocked; a click opens the
    answer on the Ask Foresight page."""
    if run_dir is None or not st.session_state.get("chat_unlocked"):
        return
    from app.runs import local_time
    from foresight.rag.chat import recent_questions as recent

    items = recent(settings, run_dir)
    if not items:
        return
    st.sidebar.html('<div class="fs-side-label">Recent questions</div>')
    with st.sidebar.container(key="recent"):
        for i, item in enumerate(items):
            if st.button(item["question"], key=f"recent-{i}", type="tertiary", width="stretch",
                         help=f"{item['question']} (asked {local_time(item['time'])})"):
                st.session_state["chat_open"] = item
                st.switch_page(ask_page)


def page_header(title: str) -> None:
    st.title(title)
    st.html('<div class="fs-trace"></div>')


def section_label(text: str) -> None:
    """Uppercase divider between the main content and the extended data."""
    st.html(f'<div class="fs-section">{text}</div>')


def kpis(items: list[tuple[str, str, str | None, str | None]]) -> None:
    """The page's headline numbers as large glass tiles of equal height: (label, value,
    comparison, help). The comparison is a neutral second line (no arrow, no colour)."""
    with st.container(key="kpis"):
        for column, (name, value, comparison, note) in zip(st.columns(len(items)), items,
                                                           strict=True):
            column.metric(name, value, comparison, delta_color="off", delta_arrow="off",
                          help=note, height="stretch")


def table(frame, column_config: dict | None = None, max_rows: int = 12) -> None:
    """A compact table: columns as wide as their data, height fitted to the rows."""
    rows = min(len(frame), max_rows)
    st.dataframe(frame, hide_index=True, width="content", row_height=30,
                 height=38 + 30 * rows + 2, column_config=column_config)


def label(text: str) -> None:
    """Small uppercase section label inside a card."""
    st.html(f'<div class="fs-label">{text}</div>')


def md(text: str) -> str:
    """LLM text for st.markdown: '$' would start LaTeX."""
    return text.replace("$", r"\$")


def environment_badge(settings: Settings) -> None:
    env = settings.environment
    st.sidebar.markdown(f":{ENV_COLORS.get(env, 'blue')}-badge[Environment: {env}]")


def passcode_ok(settings: Settings, entered: str) -> bool:
    if not settings.run_passcode:
        return False
    return hmac.compare_digest(entered.encode(), settings.run_passcode.encode())


def friendly_error(message: str) -> None:
    st.error(message, icon=":material/error:")
