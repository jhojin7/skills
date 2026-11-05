---
name: google-keep
description: >
  Create, read, update, delete, list, and filter notes on keep.google.com
  with headless agent-browser and an existing Chrome profile.
  Use when the user mentions Google Keep, keep.google.com, or /google-keep.
---

# Google Keep

Run `scripts/keep.py` next to this file. Do not write a browser script, an `agent-browser` eval, or a card scraper. The script owns the session, the search, and the clicks.

```bash
python3 "<skill-dir>/scripts/keep.py" list --query "meeting" --query "agenda"
```

`<skill-dir>` is the directory that contains this file. Repeat `--query` for one topic. Keep search is literal, so pass the user's words and the close aliases that would miss that exact string. The script unions the searches and drops duplicates. One command, not one Python program per keyword.

`list` without `--query` returns the latest unpinned notes. `--all` includes pinned notes. `--label`, `--view`, and `--type` are separate calls. `filters` prints the live labels.

`get`, `create --title --body`, `update NOTE_ID --title --body`, and `delete NOTE_ID` are the writes. `delete` stops in Trash. Add `--forever` only when the note must be gone. `close` stops the browser when the task is done.

Stdout is JSON with `ok`. On a list, report `title`, `edited`, `text`, and `links` from that JSON. A tall note is included. Do not drop cards by a height cutoff.

Requires Python 3, `agent-browser` on `PATH`, and Google Chrome already signed in to Keep. The script finds Chrome and the last-used profile on macOS, Linux, and Windows. Override with `KEEP_CHROME` and `KEEP_PROFILE`. It launches a separate headless Chrome from a read-only copy of that profile. The Keep UI labels it clicks are English.
