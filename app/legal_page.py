"""Privacy and Terms (Phase 8.6): public pages, linked from Google's sign-in screen."""

from __future__ import annotations

import streamlit as st

from app import ui

UPDATED = "21 November 2026"
CONTACT = ("open an issue in the project's GitHub repository "
           "([RavidEliav/foresight](https://github.com/RavidEliav/foresight))")

PRIVACY = f"""
Foresight is a final project of an AI Developers course, built and run by Ravid Eliav. It
analyzes the public SECOM semiconductor manufacturing dataset. This page says what it does
with information about you.

**What Foresight receives when you sign in with Google**
- Your name, email address and profile picture. Foresight never sees your Google password.
- The picture is only shown in your account menu; it is not stored.

**What Foresight stores**
- Your account: email address, name, role (user or developer), the message you wrote when
  asking for access, and when access was requested and decided.
- Your activity, so you can see it on the My activity page: the pipeline runs you started,
  stopped or resumed, and the questions you asked Ask Foresight with their answers.
- Files you upload to a run. Older runs are deleted automatically (the newest 20 are kept);
  a summary row of each run stays in the run history.

**Cookies**

One signed sign-in cookie, which ends when you close the browser or sign out. You are also
signed out after an hour without activity. No advertising or analytics cookies.

**Services that process data for Foresight**
- Google: sign-in.
- OpenAI: the pipeline's AI crews and Ask Foresight send report excerpts and your questions
  to OpenAI's API to write answers.
- Railway: hosts the app and the run files.
- Supabase: the database (accounts, run history, chat search index).
- Resend: emails your access request (name, email address and message) to the developer.

Your information is not sold or shared for any other purpose.

**Your choices**

To have your account and activity deleted, or for any question, {CONTACT}.

Last updated: {UPDATED}.
"""

TERMS = f"""
Foresight is an educational project (the final project of an AI Developers course). By
signing in you agree to these terms.

**Access**

Access is personal and granted by the developer, who can remove it at any time. Do not share
your account.

**What the results are**

Foresight's models, risk rankings and AI-generated hypotheses are leads for an engineer to
verify, not proven causes. Do not base manufacturing, safety or business decisions on them
without independent verification. Runs of a synthetic scenario are labeled SYNTHETIC; their
metrics are computed on the original SECOM data.

**Acceptable use**
- Upload only data you are allowed to share; do not upload personal or confidential data.
- Do not try to get around the run limits, read other people's data or disrupt the service.
- The pipeline and the chat use a paid AI service: keep to normal use.

**No warranty**

Foresight is provided as is, without any warranty. It may change, be unavailable or be
switched off when the course ends. To the extent the law allows, the developer is not liable
for any loss arising from its use.

**Contact**

For questions, {CONTACT}.

Last updated: {UPDATED}.
"""


def privacy() -> None:
    ui.page_header("Privacy")
    with st.container(key="card-privacy"):
        st.markdown(PRIVACY)


def terms() -> None:
    ui.page_header("Terms of use")
    with st.container(key="card-terms"):
        st.markdown(TERMS)
