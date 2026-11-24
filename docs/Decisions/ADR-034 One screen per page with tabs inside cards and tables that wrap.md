---
date: 2026-11-24
status: accepted
tags: [decision, ux]
---
# ADR-034 One screen per page with tabs inside cards and tables that wrap

## Context
After 8.6, Ravid asked that the main part of each page fit one screen, on a laptop and on a phone, and that every table show all its columns. Measured at a laptop browser window (1920×1080 at 125%: about 1536×730):
- **Investigation & Report:** its main part was 2,670 px tall, about 11 phone screens.
- **Model, EDA, Trends and Line Replay:** about two screens each.
- **Tables:** columns were cut off at a fixed width, and long descriptions were hidden.

[[ADR-021 Headline-first pages in a cleanroom design system]] set the order (headline numbers, main charts, Extended data) but not the height.

## Options considered
- Smaller charts only: rejected. At 270 px the sensor chart dropped every other label.
- Move charts to Extended data: rejected. The main charts are the page's point.
- **Tabs inside the chart card, with the summary card beside it** (chosen)

## Decision
- **Layout:**
  - Each result page has one summary card (the selected model, the insights, the findings) beside one chart card.
  - The chart card's charts are tabs inside it, for example Risk scores, Important sensors, Alarms vs outcomes and Precision-recall on Model.
  - Investigation & Report's main part has four tabs: Key findings, Hypotheses, Anomalies and run map, Simulated wafer.
  - Less space at the top: the "Hi, name" bar sits over the title row, and long captions became help tooltips.
- **Heights:** chart heights are constants in `app/charts.py`: rows 300 px, Model 290, trends 270, the replay stream 205.
- **Phone:** headline numbers sit two per row (a CSS media query under 640 px). Cards stack, so a phone still scrolls on chart pages, but the title, the headline and the start of the main content are on the first screen.
- **Tables** (`ui.table`):
  - every column is as wide as its header or its longest shown value
  - a table with text over 60 characters, or wider than 1,000 px, is shown as a wrapped table (`st.table`, first 12 rows, with a caption that says so), so no column is cut off
- **Checks:**
  - **E9** (Playwright) fails if a page's main part is taller than 1536×730, or if the headline is not on a 390×844 phone's first screen.
  - `scripts/measure_fit.py` measures and screenshots every page at laptop, desktop (1920×960) and phone sizes.

## Consequences
- Investigation & Report's main part: 2,670 px → 663 px. Model, EDA, Trends and Line Replay fit the laptop window, and so do all pages on a desktop.
- The Extended data tabs follow the main tabs. App tests now look up tabs by label and wrapped tables through `at.table`.
- A page can grow past the fold again when content changes: E9 catches it in CI. Line Replay first measured 730 px on a 730 px window in CI (the reference run's longer label), which is why the stream is 205 px.
