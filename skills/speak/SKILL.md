---
name: speak
description: Use when the user wants text turned into a short spoken transcript and audio reply. Rewrite the input into a natural TTS-ready script, keep it under about one minute at 1.2x speed, then generate and return the audio.
---

# Speak

## Role

You are not answering the content normally.
You are converting the input into something that should be spoken aloud.

## Goal

Take the user's text, read it, understand it, rewrite it into a natural spoken transcript, and return audio.

Keep the result:
- short enough for about one minute at 1.2x speed
- natural and conversational
- faithful to the original meaning
- in the same language as the source, including Korean if the source is Korean

Use the existing `humanizer` skill as the rewrite pass for the transcript. That pass should clean up awkward phrasing, but it must not change the language or inject unrelated commentary.

## When to Use

- The user says “read this to me”
- The user says “respond with speech”
- The user says “speak it to me”
- The user asks for a text-to-speech transcript
- The user wants a short spoken version of a note, thread, or document
- The user wants audio generated from a rewritten transcript

Do not use this for:
- Long-form narration
- Verbatim transcription of large documents unless explicitly requested
- Content that would need more than one minute of speech unless the user explicitly asks for a longer version

## Workflow

1. Read the input carefully.
   - If the input is in files, load them first.
   - Preserve key facts, names, numbers, and intent.
   - Keep the output language aligned with the source language.

2. Rewrite it into spoken form.
   - Use the `humanizer` skill to strip awkward AI phrasing.
   - Make it sound like a person talking, not like a document being read.
   - Do not add analysis, explanations, disclaimers, or unrelated assistant commentary.
   - Remove extra structure, headings, and filler.

3. Keep it short.
   - Target: about 80–120 words in English, or an equivalent short spoken length in Korean or another language.
   - Hard cap: about 130 English words or equivalent unless the user explicitly asks for longer.
   - If the source is longer, condense it instead of trying to fit everything.

4. Make it TTS-friendly.
   - Use short sentences.
   - Avoid tricky punctuation, long lists, and dense clauses.
   - Keep names and technical terms intact when they matter.
   - If the source is Korean, the transcript must be Korean and should sound natural when spoken.

5. Generate audio.
   - Call `text_to_speech` on the final transcript.
   - Return the audio and the transcript together.

## Output Format

Return only:
1. The final spoken transcript
2. The generated audio attachment

If the TTS step fails, provide the transcript and say the audio generation failed.

## Practical Rules

- Prefer a single compact paragraph unless the content clearly benefits from two short paragraphs.
- Do not over-explain.
- Do not add a preamble like “here is your transcript.”
- Do not mix in a separate answer to the user's original text.
- Keep the result easy to read aloud in one breath at a time.
- If the user provides an obviously long source, summarize first and mention that it was condensed only if that can be done without adding extra chatter.

## Verification Checklist

- [ ] Transcript is spoken, not written like an essay
- [ ] Transcript is under about one minute at 1.2x speed
- [ ] Humanizer-style cleanup applied
- [ ] Output language matches the source language
- [ ] Audio generated successfully
- [ ] Final reply includes both transcript and audio
