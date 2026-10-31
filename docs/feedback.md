# Reader feedback

## In the browser (v1)
Each story and post has **Knew this**, **More like this**, **Skip** and a read mark. Any reaction
also marks the item read; Skip collapses it. At the end of the paper there is a one-line edition
note and **Export feedback**. Everything is stored in this browser's `localStorage` under
`sg:<slug>/<date>`. Nothing leaves the browser until the reader exports it.

## The export file
Export downloads `<slug>-<date>-feedback.json` and also copies it to the clipboard. Save it as
`papers/<slug>/feedback/<date>.json` (any `*.json` name works).

```json
{
  "format": "mediabot-feedback/1",
  "paper": "signal-seeker",
  "edition": "2026-10-31",
  "exported_at": "2026-10-31T13:02:11.000Z",
  "note": "More Investments, fewer Local briefs.",
  "items": [
    { "id": "alphabet", "section": "front", "title": "The AI spending bill comes due: …",
      "url": "https://…", "read": true, "reaction": "more", "at": "2026-10-31T12:58:40.000Z" }
  ]
}
```
`reaction` is `"knew"`, `"more"`, `"skip"` or `null` (read only).

## What the build does with it
Every build folds all files in `papers/<slug>/feedback/` into `feedback/summary.json`:
per-section counts (read, knew, more, skip), the lists of more-like-this, skipped and knew items,
and the edition notes. Grok Bot reads `summary.json` before editing the next edition:
"more" raises an author or topic, "skip" lowers it, "knew" means go deeper or drop it (the reader
had seen it elsewhere). Edits to the paper itself still go through `paper.yaml`.

## Sign-in later (plan, not built)
- **Login:** GitHub OAuth (or email magic links) through a small serverless function,
  e.g. Cloudflare Pages Functions or a Supabase Edge Function. Readers only; papers stay static.
- **Storage:** one table, `feedback(user_id, paper, edition, item_id, read, reaction, at)` plus
  `notes(user_id, paper, edition, note)`, in Cloudflare D1 or Supabase Postgres. `site.js` would
  POST the same records it now writes to localStorage, and the morning build would pull the
  last few days instead of reading the folder.
- **Private papers:** today `public: false` only means noindex and unlisted. The URL still works
  for anyone who has it. Real privacy needs the login above in front of the paper's path
  (Cloudflare Access does this with no code).
- **Forking:** a fork is a copy of `papers/<slug>/paper.yaml` under a new slug. With accounts,
  "Fork this paper" copies the config into the new owner's folder or row.
