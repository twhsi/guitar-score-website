---
name: render-jianpu-trail-matrix
description: "Convert Jianpu/numbered-notation song data, guitar chord charts, lyrics, or mapped chord-anchor data into one long-scroll printable HTML guitar/vocal score plus one image of three vector matrices: guitar chord trail, vocal/Jianpu trail, and guitar-vocal intersection trail. Use when Codex needs to align guitar chord changes with sung lyric characters, place chords above the corresponding Chinese lyric, render an A4-printable chord sheet, or analyze the intersection points between guitar and vocal Trail sequences."
---

# Render Jianpu Trail Matrix

## Core Idea

Treat a song as two ordered Trail sequences:

- `guitar_trail`: chord-change events from guitar accompaniment.
- `vocal_trail`: lyric syllable / Jianpu note events from the sung melody.
- `intersection_trail`: points where a guitar chord change maps onto a vocal lyric character or the same bar/beat.

The preferred output is one continuous scrollable HTML chord sheet and one SVG image showing the three vector matrices. The HTML should also print naturally to A4 pages.

## Workflow

1. Read the existing project files first, especially `index.html` and `styles.css`, when working inside an existing guitar-chart site. Reuse the local chart conventions when they already support `.hit[data-chord]` chord anchors.
2. Normalize the source into the JSON shape described in `references/input-schema.md`. If the user provides raw Jianpu, lyrics, a screenshot, or another Codex thread, extract the song metadata, sections, lyric lines, vocal/Jianpu events, and guitar chord events before rendering.
3. Build three matrices:
   - Guitar matrix: one row per chord event, with section, line, bar, beat, chord, anchor character, and harmonic vector value.
   - Vocal matrix: one row per sung lyric/Jianpu event, with section, line, character index, bar, beat, lyric text, Jianpu note, and melodic vector value.
   - Intersection matrix: one row per matched guitar/vocal point, prioritizing explicit lyric anchors over approximate time matching.
4. Render the HTML:
   - Place each chord on the lyric character where the chord changes: `<span class="hit" data-chord="C">樂</span>`.
   - For Japanese songs, render `romaji` directly under each Japanese lyric line. Keep chord anchors on the Japanese `lyrics` line, not on the romaji line.
   - Avoid empty chord anchors unless the source explicitly marks an instrumental/rest position.
   - Keep the page as one long scrollable chart. Do not crop content into fixed 16:9 panels.
   - Print with A4 natural pagination and hide nonessential controls.
5. Render the image as `trail-matrix.svg`, with three stacked matrix bands for guitar, vocal, and intersection trails.
6. Validate by checking that anchored chord markers match intersection rows, the page has no horizontal overflow, and print CSS is present.

## Script

Use the bundled script when the source has been normalized to JSON:

```bash
python3 skills/render-jianpu-trail-matrix/scripts/render_jianpu_trail.py input.json --out-dir outputs/song-name
```

The script writes:

- `song.html`
- `trail-matrix.svg`
- `matrix-data.json`

For a quick smoke test:

```bash
python3 skills/render-jianpu-trail-matrix/scripts/render_jianpu_trail.py skills/render-jianpu-trail-matrix/references/sample-song.json --out-dir /private/tmp/jianpu-trail-sample
```

## Alignment Rules

Prefer explicit anchors in this order:

1. `anchor_index` or `char_index` on the chord event.
2. `anchor` text on the chord event, matched left-to-right within the lyric line.
3. A vocal event with the same `bar` and `beat`, allowing small numeric tolerance.
4. A nearest vocal event in the same line, only when the user accepts inferred mapping.

When a reference image is used, the important result is not decoration fidelity. The important result is a playable chart where the chord name appears above the exact lyric character at which the player changes chord.

## Visual Defaults

- Keep core content: title, artist/source metadata, key/capo/beat, section labels, lyric lines, chord anchors, intro/progression lines, and the matrix image.
- For Japanese charts, use a smaller muted romaji line beneath the original lyric line. Do not replace the Japanese line with romanization.
- Remove nonessential elements by default: watermarks, source badges such as `91pu`, treble-clef decorations, practice cards, and ornamental marks.
- Use a narrow long-chart reading width around 820px unless the existing project has a stronger convention.
- Keep Chinese lyric text readable and dense enough for a practical guitar sheet.

## References

- `references/input-schema.md`: accepted JSON fields and the three vector matrix definitions.
- `references/sample-song.json`: minimal sample input for testing the renderer.
