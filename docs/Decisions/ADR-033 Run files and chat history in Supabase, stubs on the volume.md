---
date: 2026-11-23
status: accepted
tags: [decision, supabase, runs]
---
# ADR-033 Run files and chat history in Supabase, stubs on the volume

## Context
On 2026-11-22 the `dev` runs volume (500 MB) filled up:
- **The embedding model's cache** took 167 MB, including an 80 MB archive that was no longer needed.
- **Runs** take 12 to 36 MB each, and 21 were kept.

Two runs died because they couldn't write their files, and Resume crashed with "No space left on device". The app only said the runs were interrupted "for example because the app restarted". Ravid asked for everything to be kept in Supabase, so Railway keeps as little as possible.

## Options considered
- Grow the volume (Railway Hobby allows more): it fills up again, and the data is still tied to one container
- Delete old runs automatically: their pages are lost
- Files as `bytea` rows in Postgres: needs no new key, but the free plan's database is 500 MB and backups grow
- **Supabase Storage for the files and Postgres for the chat history, with a stub of each older run on the volume** (chosen)

## Decision
- **Files:**
  - When a run ends, its folder is packed into one `<run id>.tar.gz` in the private Storage bucket `runs`. The bucket is created by a migration, with a 50 MB limit and gzip only.
  - The server uses the project's secret key (`SUPABASE_SECRET_KEY`); there are no storage policies, so the client roles cannot read the bucket.
  - The project URL comes from the database URL.
  - The registry row gets the run's whole progress, and `archived_at` and `archive_bytes` are set.
- **Stubs:**
  - The volume keeps the newest 3 runs whole.
  - Older runs keep only `progress.json`, `run_manifest.json` and `archived.json` (a few KB). Every list, label, history and owner check works unchanged from them.
  - Picking an older run in the sidebar, or resuming it, downloads its files again.
  - On a new or wiped volume, startup rebuilds the stubs from the registry.
  - A stub is never recorded over its full registry row.
- **Interrupted runs:** before an interrupted run is archived, its cause is written into its progress, because `run.log` does not stay on the server. The causes:
  - the storage was full;
  - the run crashed (its last error);
  - the app restarted;
  - the process stopped without a word (usually memory).
- **Chat history** goes to `foresight.questions` (RLS, no client privileges, each record stored once). Startup imports the old `chat_logs/*.jsonl` files and deletes them. If the database cannot be reached, a question goes to the file meanwhile and is imported later.
- **Model cache:** on Railway the embedding model lives on the container's own disk (`/tmp`). Each deploy downloads it again, about 80 MB.
- **Safety:** a Storage or database problem is logged and never fails a run or a page. A run folder stays whole until it is safely archived. Start and Resume check for 50 MB free first.

## Consequences
- Updates [[ADR-016 Uploads through the Data Contract, runs on a Railway volume]]: the volume still holds the run in progress and the newest runs, but finished runs live in Supabase.
- The volume holds a few runs and stubs instead of filling up. Supabase's free plan gives 1 GB of Storage per project, enough for a few hundred runs at a few MB each.
- An older run's pages take a second or two the first time they are opened (one download).
- Without the secret key (tests, CI, a laptop) nothing changes: the newest 10 runs are kept on disk.
- The sign-in activity clock (`.access`, a few bytes per sign-in) stays on the volume; losing it only signs people out.
