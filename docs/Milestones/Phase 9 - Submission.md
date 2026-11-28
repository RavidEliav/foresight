---
date: 2026-11-27
updated: 2026-11-28
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
- `scripts/record_demo.py`: about 4 minutes at 1920x1080 and 60 fps, narrated in Ravid's voice. Three versions go to `Videos/`: `Foresight demo.mp4` (English), `Foresight demo (Hebrew).mp4` and `Foresight demo (no narration).mp4` (music only, to talk over). None is in the repo.
- **What it shows, in order:**
  1. title cards: the intro, the challenge (SECOM in numbers) and how it works
  2. the sign-in page of `main`
  3. one take through the local app:
     - a real SECOM analysis, fast-forwarded to 18 seconds; the badge shows the real time
     - Data quality and Data insights
     - Model: all four chart tabs (risk scores, important sensors, alarms vs outcomes, precision-recall)
     - Findings: the anomalies and run map, the map's 3D view (the camera glides to the points), the simulated wafer
     - Line replay at 3 runs/s to the end of the test period, shown 10 times faster
     - Trends, and a real question on Ask Foresight
  4. title cards: RAG, the phone, deployment, the results and the links
- **Why the local app:** `main` needs a Google sign-in, which the script cannot do. The local app looks the same: the local badge is hidden and the top bar says "Hi, Ravid".
- **How it is recorded:**
  - Chrome runs full screen on the second monitor, and ffmpeg records that screen at 60 fps (Desktop Duplication, `ddagrab`). The first version used the DevTools screencast, which gave 10 to 25 frames a second and looked choppy. A magenta corner, shown and removed at the start of each clip, lines the recording up with the script's clock.
  - Windows must stay unlocked: while it is locked the screen capture is black.
  - The effects are drawn in the page: a glowing cursor that glides at every frame, click ripples, numbered captions, smooth zooms (a CSS transform; CSS `zoom` cuts Plotly charts) and the fast-forward badges.
  - The title cards are animated HTML pages.
  - ffmpeg adds the dissolves and a progress line.
- **The narration** (`NARRATION`, `NARRATION_HE`): a line a scene, made before the recording so each scene waits for its line. Both languages share one recording: a scene waits for the longer of its two lines, and each language gets its own mix.
  - Ravid recorded both narrations: Hebrew as one reading with 2-second pauses (`voice-lines-he.m4a`, cut into lines automatically), English as one file a line (`voice-en-NN.m4a`). A `voice-<lang>-NN` file replaces a line. Each line is cut to its own sounds, so breaths and clicks around it are left out.
  - Tried first and dropped: a clone of his voice (Chatterbox, `scripts/demo_voice.py`), whose Hebrew needed forced vowel marks for his name, 590 and English names, and which ran on into noise after some sentences; and OpenAI's text to speech, which sounded wrong in Hebrew. The script can still make either.
- **The music** (`scripts/demo_music.py`): composed in numpy at 118 BPM, a four-chord loop with drums, bass, a plucked arpeggio and a lead. Its energy follows the video (lifts during the fast-forwards and the closing cards) and it dips 10 dB under the voice. The mix is about -17 LUFS. The first version, a slow ambient pad, sounded like a thriller.
- **Cost:** about 2 US cents of OpenAI per recording. The real recording takes about 15 minutes.
- **To share by email:** a 30 fps copy at CRF 26 is about 17 MB a version, and looks the same.
