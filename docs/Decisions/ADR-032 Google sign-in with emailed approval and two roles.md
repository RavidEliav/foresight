---
date: 2026-11-21
status: accepted
tags: [decision, security, app]
---
# ADR-032 Google sign-in with emailed approval and two roles

## Context
Until Phase 8.6 the deployed apps were open to anyone with the link, with a shared passcode for runs and the chat. Runs spend tokens, and the director and reviewers need access without sharing a password. Ravid wanted a "Hi, name" greeting and a page with each person's own activity.

## Options considered
- Keep the shared passcode
- Supabase Auth: a second user system next to the server-side registry, and keys in the browser
- **Streamlit's own `st.login` with Google (OIDC), accounts in the server-side registry** (chosen)
- Microsoft sign-in, to use the Intel account: tried on 2026-11-22, but registering an app in Azure/Entra is blocked for Ravid's account, so it was dropped

## Decision
- **Sign-in:** Google through `st.login` for the whole app. Google shows its account picker. On Railway sign-in is always required (without the keys nobody gets in); a local checkout and CI open as a local developer.
- **Sessions end** on Sign out, when the browser closes (Streamlit's 30-day cookie becomes a session cookie, guarded by a test) and after 1 hour without activity (a clock per sign-in).
- **Access requests:** a new account asks for access; the developers get an email through Resend's HTTP API (Railway blocks SMTP) with **Approve** / **Deny** links. Each link carries an HMAC-signed token for that one request, expires after 7 days, and asks for one more click so mail scanners decide nothing.
- **Accounts** live in `foresight.accounts` (private schema, RLS on, no client privileges; [[ADR-027 Run registry in Supabase Postgres, server-side only]]); without Supabase, in a file on the runs volume.
- **Two roles:**
  - **Users:** Run Pipeline (run, stop, resume), the result pages' headlines, charts and hypothesis cards, the report download, Line Replay, Ask Foresight and My activity. They see **only their own runs plus the reference run**: in the run picker, the history ("Your runs") and the All runs chat, whose search is limited to those runs (#49).
  - **Developers** (`FORESIGHT_DEVELOPERS`, or the role) also get the environment badge, technical details, every Extended data section, Trends and the Users & access page (approve, deny, add, change roles, remove).
- Runs record `started_by`, `resumed_by` and `stopped_by`; chat logs record who asked. No passcodes anywhere.

## Consequences
- Reviewers sign in with any Google account and wait for one click of approval.
- The Intel account cannot complete Google sign-in (most likely Intel IT policy); Ravid uses his Gmail.
- A stale OAuth callback (browser back/forward) keeps the previous session's cookie: "Missing provider for OAuth callback" in the log. It looked like one account signing in as another during testing.
- Secrets reach Railway through `push_secrets_to_railway.ps1`, which writes exact bytes and reads them back (a PowerShell pipe once added a byte-order mark to every value, #47).
