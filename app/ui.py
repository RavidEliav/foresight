"""Shared UI helpers: page style, headers, badges, environment badge, passcode check and
friendly errors."""

from __future__ import annotations

import hmac
from pathlib import Path

import streamlit as st

from foresight.settings import Settings

ENV_COLORS = {"main": "green", "dev": "orange", "local": "gray"}
CONFIDENCE_COLORS = {"high": "green", "medium": "orange", "low": "gray"}
STATUS_COLORS = {"PASS": "green", "WARNING": "orange", "ERROR": "red"}
LOGO = Path(__file__).parent / "assets" / "logo.svg"

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
[class*="st-key-card-"], [data-testid="stMetric"], [data-testid="stExpander"] details,
[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"] {
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
/* sidebar: frosted panel, glass highlight on the selected page */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(13,21,38,.72), rgba(7,11,20,.6)) !important;
  -webkit-backdrop-filter: var(--fs-blur); backdrop-filter: var(--fs-blur);
}
[data-testid="stSidebar"] h1 { letter-spacing: 0.04em; }
[data-testid="stSidebarNavLink"] { border-radius: 10px; border: 1px solid transparent; }
[data-testid="stSidebarNavLink"]:hover { background: rgba(255,255,255,.05); }
[data-testid="stSidebarNavLink"][aria-current="page"] {
  border-left: 2px solid #22D3EE !important;
  box-shadow: var(--fs-glass-shadow), 0 0 18px -6px rgba(34,211,238,.45);
}
/* tabs */
[data-baseweb="tab-list"] { gap: .4rem; border-bottom: 1px solid rgba(148,163,184,.14); }
[data-baseweb="tab"] { padding: .45rem .9rem; border-radius: 10px 10px 0 0; }
[data-baseweb="tab"][aria-selected="true"] { background: rgba(34,211,238,.08); }
[data-baseweb="tab"] p { font-size: .95rem; font-weight: 600; }
</style>
"""


def apply_style() -> None:
    st.html(STYLE)
    st.logo(str(LOGO), size="large")


def page_header(title: str) -> None:
    st.title(title)
    st.html('<div class="fs-trace"></div>')


def section_label(text: str) -> None:
    """Uppercase divider between the main content and the extended data."""
    st.html(f'<div class="fs-section">{text}</div>')


def kpis(items: list[tuple]) -> None:
    """The page's headline numbers as large glass tiles: (label, value, comparison, help) and
    optionally a sparkline series. The comparison is a neutral second line (no arrow, no
    colour)."""
    with st.container(key="kpis"):
        for column, (name, value, comparison, note, *chart) in zip(st.columns(len(items)),
                                                                   items, strict=True):
            column.metric(name, value, comparison, delta_color="off", delta_arrow="off",
                          help=note, chart_data=chart[0] if chart else None,
                          chart_type="area")


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
