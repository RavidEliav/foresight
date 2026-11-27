---
date: 2026-11-27
updated: 2026-11-27
phase: 9
tags: [milestone, submission]
---
# Phase 9: Submission (in progress)

Ravid's order: the README, then the demo video, then the slides (10 to 12). Due Dec 4; the presentation is on Dec 9.

## README (#84)
- A showcase in the Foresight look:
  - the sign-in wordmark as a banner, and themed badges
  - New analysis with its fourth stage running as the main picture
  - every page in the menu's order, two per row, and four phone views in one row
  - the pipeline, RAG, deployment and results drawn as images (GitHub strips CSS)
- The long sections moved word for word to [[Technical reference]].
- How the pictures are made:
  - `scripts/take_screenshots.py` takes the screenshots: the local app with the real LLM, Trends after three real analyses, and the sign-in page of `main`.
  - `scripts/readme_art.py` draws the diagrams from the app's own CSS.
  - `FORESIGHT_LOCAL_NAME` names the local developer ("Hi, Ravid").

## Demo video
- `scripts/record_demo.py`: 3.5 minutes at 1920x1080. It is saved to `Videos/Foresight demo.mp4`, plus a version without music; it is not in the repo.
- **What it shows, in order:**
  1. title cards: the intro, the challenge (SECOM in numbers) and how it works
  2. the sign-in page of `main`
  3. one take through the local app:
     - a real SECOM analysis, fast-forwarded to 18 seconds; the badge shows the real time
     - Data quality, Data insights, Model, Findings, Line replay and Trends
     - a real question on Ask Foresight
  4. title cards: RAG, the phone, deployment, the results and the links
- **Why the local app:** `main` needs a Google sign-in, which the script cannot do. The local app looks the same: the local badge is hidden and the top bar says "Hi, Ravid".
- **How it is recorded:**
  - Chrome's own frames through the DevTools screencast (Playwright's video is blurry at 1080p).
  - The effects are drawn in the page: a glowing cursor with click ripples, numbered captions, smooth zooms (a CSS transform; CSS `zoom` cuts Plotly charts) and the fast-forward badge.
  - The title cards are animated HTML pages.
  - ffmpeg adds the dissolves, a progress line and a synthesized ambient bed at about -21 LUFS (quiet enough to talk over).
- **Cost:** about 1 to 2 US cents of OpenAI per recording.
