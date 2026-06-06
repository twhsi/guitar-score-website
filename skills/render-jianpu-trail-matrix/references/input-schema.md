# Input Schema And Matrix Spec

Use JSON as the normalized handoff format before rendering.

## Minimal Shape

```json
{
  "song": {
    "title": "小手拉大手",
    "artist": "梁靜茹",
    "language": "zh-Hant",
    "key": "C",
    "capo": "0",
    "beat": "4/4"
  },
  "sections": [
    {
      "name": "A",
      "lines": [
        {
          "lyrics": "還記得那場音樂會的煙火",
          "chords": [
            { "chord": "C", "anchor": "樂", "bar": 1, "beat": 3 },
            { "chord": "Am", "anchor": "火", "bar": 2, "beat": 1 }
          ],
          "vocal": [
            { "text": "還", "jianpu": "5", "char_index": 0, "bar": 1, "beat": 1 },
            { "text": "記", "jianpu": "5", "char_index": 1, "bar": 1, "beat": 1.5 }
          ]
        }
      ]
    }
  ]
}
```

## Song Fields

- `title`: Song title.
- `artist`: Artist or performer.
- `lyricist`, `composer`: Optional credits.
- `key`: Musical key.
- `play_key`: Optional chord-shape key used by the player. When present, output shows `原調`, `Play`, `Capo`, and `Beat`.
- `capo`: Capo value.
- `beat` or `meter`: Time signature such as `4/4`.
- `language`: Optional language tag. Use `ja` for Japanese songs that need romaji.

## Section Fields

- `name`: Section label such as `前奏`, `A`, `B`, `副歌`.
- `progression`: Optional list of instrumental chords, for example `["| F", "| C", "| F G", "| C |"]`.
- `lines`: List of lyric lines.

## Line Fields

- `lyrics`: Full lyric text for the line.
- `romaji`: Optional romanized reading for Japanese lyrics. Render it below `lyrics`.
- `jianpu`: Optional compact Jianpu text for the line.
- `bar`: Optional default bar number for the line.
- `chords`: Guitar chord Trail events.
- `vocal` or `voice`: Vocal/Jianpu Trail events.

## Guitar Event Fields

- `chord`: Required chord label, for example `C`, `Am`, `Gsus4 - G`.
- `anchor_index` or `char_index`: Zero-based character index in `lyrics`.
- `anchor_pos`: Optional one-based character index when the source uses human counting.
- `anchor`: Lyric character or text fragment used to locate the chord.
- `bar`, `beat`, `duration`: Optional timing fields.
- `allow_empty`: Set true only for explicit instrumental/rest chord positions.

## Vocal Event Fields

- `text`: Lyric character or syllable.
- `jianpu`: Numbered note such as `1`, `2`, `3`, `5.`, `#4`, or `0`.
- `char_index`: Zero-based character index in `lyrics`.
- `bar`, `beat`, `duration`: Optional timing fields.

If `vocal` is omitted, the renderer creates an approximate vocal trail from non-space lyric characters. This is useful for visual drafts, but final playable charts should use real Jianpu/timing when available.

## Japanese Song Rule

When `song.language` is `ja` or any line has `romaji`, render the original Japanese lyric with chord anchors and render `romaji` below it in a smaller muted style.

Keep intersections bound to `lyrics`, not `romaji`; the player changes chords while singing the Japanese lyric, and romaji is only a pronunciation aid.

## Three Vector Matrices

The renderer outputs `matrix-data.json` with these matrices:

- `guitar`: rows shaped like `[id, section, line, bar, beat, duration, chord, anchor, anchor_index, time_x, harmonic_y]`.
- `vocal`: rows shaped like `[id, section, line, char_index, bar, beat, duration, text, jianpu, time_x, melody_y]`.
- `intersection`: rows shaped like `[id, section, line, guitar_id, vocal_id, chord, text, bar, beat, delta, match_type, x, y]`.

`time_x` is a normalized sequence-time coordinate. `harmonic_y` is derived from chord root pitch class. `melody_y` is derived from the Jianpu scale degree when available.

## Matching Policy

Use explicit lyric anchors first. A chord mapped to `anchor_index: 6` or `anchor: "樂"` should wrap that lyric character in the HTML.

Use timing only when anchors are absent. A same-line guitar event and vocal event match when their normalized times are close enough. Keep the match type as `time` or `nearest` so later revisions can distinguish inferred intersections from explicit lyric anchors.
