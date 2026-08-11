---
name: clickbait-cleaner
description: Strip clickbait/filler from articles, videos, threads, or transcripts and return only dense key takeaways.
---

# Clickbait Cleaner

## When to use

Use when the user asks to clean up clickbait, summarize a linked article/video/thread, or distill source material into key takeaways without hype or beginner filler.

## Instruction

Apply this exact style and output constraint:

```text
clean up clickbait and distil key takeaways. bullet points. max 20. under 10 if possible.
no bullshit. no glazing. no ai hype. no introductory newbie stuff that advanced users would already know and skip. only the meat. throw away the rest.
```

## Output rules

- Bullet points only.
- Maximum 20 bullets.
- Prefer under 10 bullets if the source does not need more.
- Remove clickbait framing, sponsor/filler, intro/outro, recaps, generic advice, and obvious beginner context.
- No praise, no “AI hype”, no motivational language.
- Keep only concrete claims, mechanisms, tradeoffs, numbers, caveats, and actions.
- If the source is mostly fluff, say so in one bullet and include only any remaining useful points.

## Workflow

1. Fetch or read the source material.
   - For YouTube links, prefer transcript/captions over page metadata. Use `yt-dlp --dump-json --skip-download <url>` to inspect title, duration, channel, subtitles, and automatic captions; then download captions with `yt-dlp --skip-download --write-auto-subs --sub-lang en-orig,en --sub-format vtt <url>` when available.
   - For YouTube live archives, expect repeated rolling-caption fragments. Clean VTT by stripping timestamps/markup and merging overlapping caption windows before summarizing; otherwise repeated fragments will inflate or distort takeaways.
2. Extract the non-obvious substance.
3. Deduplicate repeated points.
4. Return compact bullets in descending importance.

## Pitfalls

- Do not summarize YouTube metadata, chat, title, or assumptions when captions are available; base bullets on transcript substance.
- For long livestream demos, separate reusable mechanisms from incidental demo-app decisions. Keep architecture decisions, tradeoffs, blockers, and concrete actions; discard banter, setup chatter, chat Q&A fluff, and live-debug noise unless it changes the takeaway.
