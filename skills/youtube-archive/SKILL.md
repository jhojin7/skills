---
name: youtube-archive
description: Use when archiving a YouTube video from a URL into the user's local resources tree with metadata, thumbnail, and subtitles. Saves the raw source files under resources/youtube/<video_id>/ and keeps the layout stable.
---

# YouTube Archive Workflow

## Overview

Use this skill when the user gives a YouTube video, live, short, or playlist URL and wants the content archived locally. The goal is to keep the original source artifacts together in a stable directory layout under:

`~/.hermes/resources/youtube/<video_id>/`

This archive should usually include:
- `metadata.json` from `yt-dlp`
- the downloaded video file, usually `video.mp4`
- thumbnail image, usually `video.jpg` or `video.webp`
- subtitle files, usually `video.<lang>.srt` plus optional raw `vtt` files

Prefer `uvx yt-dlp` in this environment. If subtitles arrive as `.vtt`, convert them to `.srt` with `ffmpeg` and keep the originals unless the user asks to clean them up.

## When to Use

- The user says “download this YouTube video”
- The user asks for subtitles, thumbnail, and metadata together
- The user wants a durable local archive in `resources/youtube/<id>/...`
- The user wants a repeatable YouTube ingestion workflow

Do not use for:
- Pure summaries/transcripts only — use `youtube-content`
- Non-YouTube video sources

## Directory Convention

Use a per-video directory named by the YouTube video ID:

```text
~/.hermes/resources/youtube/<video_id>/
```

Example files:

```text
metadata.json
video.mp4
video.jpg
video.ko.srt
video.ko-orig.srt
```

## Recommended Commands

### 1) Extract metadata

```bash
video_id="<video_id>"
archive_dir="${HOME}/.hermes/resources/youtube/${video_id}"
mkdir -p "$archive_dir"
uvx yt-dlp -J --no-playlist "<url>" > "$archive_dir/metadata.json"
```

### 2) Download video + thumbnail

```bash
video_id="<video_id>"
archive_dir="${HOME}/.hermes/resources/youtube/${video_id}"
uvx yt-dlp \
  -f 'bv*+ba/b' \
  --merge-output-format mp4 \
  --write-thumbnail \
  --convert-thumbnails jpg \
  -P "$archive_dir" \
  -o 'video.%(ext)s' \
  "<url>"
```

### 3) Download subtitles

If manual subtitles exist, prefer those first. If not, use auto captions:

```bash
video_id="<video_id>"
archive_dir="${HOME}/.hermes/resources/youtube/${video_id}"
uvx yt-dlp \
  --skip-download \
  --write-auto-subs \
  --sub-langs 'ko-orig,ko,en' \
  -P "$archive_dir" \
  -o 'video.%(ext)s' \
  "<url>"
```

If YouTube rate-limits subtitle downloads or yt-dlp cannot fetch them reliably, fall back to `youtube-transcript-api` and write a local `.srt` from the transcript text/timestamps. This is especially useful for live videos or when yt-dlp hits HTTP 429.

```bash
video_id="<video_id>"
archive_dir="${HOME}/.hermes/resources/youtube/${video_id}"
uv run --with youtube-transcript-api python /tmp/fetch_transcript_srt.py "$video_id" "$archive_dir/video.transcript.srt"
```

If yt-dlp writes `.vtt` files, convert them:

```bash
video_id="<video_id>"
archive_dir="${HOME}/.hermes/resources/youtube/${video_id}"
for f in "$archive_dir"/video.*.vtt; do
  ffmpeg -y -i "$f" "${f%.vtt}.srt"
done
```

## Practical Defaults

- Put the archive under `resources/youtube/<video_id>/`
- Keep filenames simple: `video.mp4`, `video.jpg`, `metadata.json`
- Keep subtitle files side-by-side in the same folder
- Use `uvx yt-dlp` instead of installing globally
- When the source URL comes from the user's durable backlog, first confirm the backlog item and check whether `resources/youtube/<video_id>/` already exists before downloading.
- For large/live archives, do a metadata preflight before download: save metadata as `metadata.json.tmp`, report title/channel/duration/live status/estimated size, then wait for approval before fetching video bytes.
- After approval, move `metadata.json.tmp` to `metadata.json`, download video+thumbnail+captions, convert `.vtt` captions to `.srt`, verify with `ffprobe`, then mark the backlog item complete with exact saved files and any subtitle caveat.
- If one auto-caption language hits YouTube HTTP 429 but another requested language succeeds, keep the successful captions and report the failed language as a caveat rather than retrying indefinitely.
- For bulk archives from a newline-delimited txt file, prefer a wrapper that supports `OUTPUT_PATH`, `DRY_RUN`, and `LIMIT_N`.
- For bulk archives, use standard logging output with timestamp/level/step/context fields so progress can be grepped and audited.
- Subtitle priority for a bulk workflow is: video default language when available, then `en`, then `ko`.
- If subtitle download fails on one language, retry with a smaller language set

## Common Pitfalls

1. **Using the title as the directory name.**
   Titles change; video IDs do not. Always use `<video_id>`.

2. **Trying too many subtitle languages at once.**
   YouTube can rate-limit subtitle requests. Start with `ko-orig,ko,en` or the languages the user actually needs.

3. **Assuming `--write-auto-subs` means subtitles will always download.**
   Some videos have no usable captions. Check the output and keep the raw error if it fails.

4. **Forgetting to verify file creation.**
   After download, confirm the directory contains metadata, video, thumbnail, and subtitle files.

5. **Deleting raw `.vtt` too early.**
   Keep the source caption files unless the user explicitly wants cleanup.

## Verification Checklist

- [ ] A directory exists at `~/.hermes/resources/youtube/<video_id>/`
- [ ] `metadata.json` exists and parses as JSON
- [ ] `video.mp4` or another video file exists
- [ ] A thumbnail file exists (`.jpg`, `.png`, or `.webp`)
- [ ] Subtitle files exist for the requested languages
- [ ] If subtitles were `.vtt`, `.srt` versions were created
- [ ] File names are stable and do not depend on the title

## Checking Whether a Target Was Already Archived

When the user asks whether a YouTube item was already downloaded, verify by exact video ID, not by the mere presence of other archived videos:

1. Extract/identify the target video ID from the URL or backlog item.
2. Check `~/.hermes/resources/youtube/<video_id>/` for `metadata.json`, `video.*`, thumbnail, and subtitle/transcript files.
3. Optionally list other archived video-ID directories only as context.
4. Report clearly:
   - `yt-dlp` availability/version if asked about setup
   - whether the exact target ID is archived
   - which expected files are present/missing
5. If other videos exist but the target ID directory is absent, say the target is **not downloaded yet**; do not imply archive completion from unrelated directories.
