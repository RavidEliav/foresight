---
date: 2026-11-18
status: accepted
tags: [decision, ux]
---
# ADR-021 Headline-first pages in a cleanroom design system

## Context
Validating Phase 4 showed long, scattered pages: the numbers people looked for were hidden in text and expanders, and charts were static PNGs. The direction from [[ADR-017 Phase order after Phase 4 and the design direction]] was a futuristic look that gently resembles the semiconductor industry.

## Options considered
- Restyle the existing pages only
- **One layout rule and one design system for every page** (chosen; mock-up approved by Ravid with his notes: glass effect, compact tables, main numbers emphasised, extended data at the bottom)

## Decision
- **Layout:** each result page leads with its headline numbers as equal-height tiles (exact value, a neutral comparison line, help), then its main charts in equal-height cards, then everything else under **Extended data** tabs. Tables are compact and formatted.
- **Design system:** a dark "cleanroom" theme in `.streamlit/config.toml` (cyan and violet for lithography light, amber, the fab's yellow-room light, for failing runs), a faint die-grid background, frosted-glass surfaces, a wafer logo used in the wordmark "F◉resight" and as the chat avatar (`app/ui.py`).
- **Charts:** Plotly, built in the app from the run's files (`app/charts.py`); charts in one row share a height. The PNGs stay in the run folder for the reports.
- **Run Pipeline:** one tile per stage (green done, red failed, gray skipped, amber interrupted, cyan while running) with a small animation of the stage's work and its crew's status; gates between tiles (`app/stepper.py`).
- **Plain language:** failures explain what happened and what to do; technical details are collapsed. Times are in the viewer's time zone. An older run says what it lacks.

## Consequences
- The sidebar menu is drawn with page links (Streamlit's own menu is hidden) so the brand can come first; E2E navigation follows it.
- Fonts load from Google Fonts; inline SVG is not allowed in `st.html`, so drawings are SVG data URIs.
- Pages read more files on render; caching and data access are Phase 7 topics ([[ADR-020 Single service now, frontend-backend seam in Phase 7]]).
