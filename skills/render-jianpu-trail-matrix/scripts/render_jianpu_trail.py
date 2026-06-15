#!/usr/bin/env python3
"""Render Jianpu/chord Trail data to HTML plus one SVG matrix image."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ROOTS = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}


def read_source(path: str) -> dict[str, Any]:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_meter(value: Any) -> float:
    if not value:
        return 4.0
    match = re.match(r"\s*(\d+)\s*/\s*(\d+)\s*", str(value))
    if not match:
        return 4.0
    return float(match.group(1))


def to_float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def time_x(event: dict[str, Any], beats_per_bar: float) -> float:
    bar = to_float(event.get("bar"), 1.0)
    beat = to_float(event.get("beat"), 1.0)
    return max(0.0, (bar - 1.0) * beats_per_bar + (beat - 1.0))


def chord_root_value(chord: str) -> int:
    match = re.match(r"^\s*([A-G](?:#|b)?)", chord or "")
    if not match:
        return 0
    return ROOTS.get(match.group(1), 0)


def melody_value(jianpu: Any) -> int:
    if jianpu is None:
        return 0
    match = re.search(r"[#b]?([0-7])", str(jianpu))
    if not match:
        return 0
    return int(match.group(1))


def clean_chars(text: str) -> list[str]:
    return [char for char in text]


def find_anchor_index(lyrics: str, anchor: Any, start: int) -> int | None:
    if anchor is None:
        return None
    token = str(anchor)
    if not token:
        return None
    idx = lyrics.find(token, max(0, start))
    if idx >= 0:
        return idx
    idx = lyrics.find(token)
    if idx >= 0:
        return idx
    first = token[0]
    idx = lyrics.find(first, max(0, start))
    if idx >= 0:
        return idx
    idx = lyrics.find(first)
    return idx if idx >= 0 else None


def normalize_vocal_events(
    line: dict[str, Any],
    section_name: str,
    section_i: int,
    line_i: int,
    beats_per_bar: float,
) -> list[dict[str, Any]]:
    lyrics = str(line.get("lyrics", ""))
    raw = line.get("vocal") or line.get("voice") or []
    base_bar = to_float(line.get("bar"), 1.0 + line_i)
    events: list[dict[str, Any]] = []

    if raw:
        for i, item in enumerate(raw):
            item = dict(item)
            char_index = item.get("char_index", item.get("anchor_index"))
            if char_index is None and item.get("anchor_pos") is not None:
                char_index = int(item["anchor_pos"]) - 1
            if char_index is None and item.get("text") is not None:
                idx = find_anchor_index(lyrics, item.get("text"), 0)
                char_index = idx if idx is not None else i
            char_index = int(char_index if char_index is not None else i)
            text = str(item.get("text", lyrics[char_index] if 0 <= char_index < len(lyrics) else ""))
            event = {
                "id": f"V{section_i + 1:02d}-{line_i + 1:02d}-{i + 1:03d}",
                "section": section_name,
                "line": line_i + 1,
                "char_index": char_index,
                "text": text,
                "jianpu": item.get("jianpu", item.get("note", "")),
                "bar": to_float(item.get("bar"), base_bar),
                "beat": to_float(item.get("beat"), 1.0 + (i % int(beats_per_bar))),
                "duration": to_float(item.get("duration"), 1.0),
            }
            event["time_x"] = time_x(event, beats_per_bar)
            event["melody_y"] = melody_value(event["jianpu"])
            events.append(event)
        return events

    note_tokens = re.findall(r"[#b]?[0-7][.'-]*", str(line.get("jianpu", "")))
    vocal_i = 0
    for char_i, char in enumerate(clean_chars(lyrics)):
        if char.isspace():
            continue
        note = note_tokens[vocal_i] if vocal_i < len(note_tokens) else ""
        event = {
            "id": f"V{section_i + 1:02d}-{line_i + 1:02d}-{vocal_i + 1:03d}",
            "section": section_name,
            "line": line_i + 1,
            "char_index": char_i,
            "text": char,
            "jianpu": note,
            "bar": base_bar + math.floor(vocal_i / beats_per_bar),
            "beat": 1.0 + (vocal_i % int(beats_per_bar)),
            "duration": 1.0,
        }
        event["time_x"] = time_x(event, beats_per_bar)
        event["melody_y"] = melody_value(note)
        events.append(event)
        vocal_i += 1
    return events


def normalize_guitar_events(
    line: dict[str, Any],
    lyrics: str,
    vocal_events: list[dict[str, Any]],
    section_name: str,
    section_i: int,
    line_i: int,
    beats_per_bar: float,
) -> list[dict[str, Any]]:
    raw = line.get("chords") or line.get("guitar") or line.get("guitar_chords") or []
    base_bar = to_float(line.get("bar"), 1.0 + line_i)
    events: list[dict[str, Any]] = []
    search_from = 0

    for i, item in enumerate(raw):
        if isinstance(item, str):
            item = {"chord": item}
        else:
            item = dict(item)
        chord = str(item.get("chord", item.get("name", ""))).strip()
        char_index = item.get("anchor_index", item.get("char_index"))
        if item.get("allow_empty"):
            char_index = None
        elif char_index is None and item.get("anchor_pos") is not None:
            char_index = int(item["anchor_pos"]) - 1
        if char_index is None:
            idx = find_anchor_index(lyrics, item.get("anchor", item.get("text")), search_from)
            char_index = idx
        if char_index is None and item.get("bar") is not None and not item.get("allow_empty"):
            temp = {"bar": item.get("bar"), "beat": item.get("beat", 1)}
            target = time_x(temp, beats_per_bar)
            same_line = sorted(vocal_events, key=lambda ev: abs(ev["time_x"] - target))
            if same_line:
                char_index = same_line[0]["char_index"]
        char_index = int(char_index) if char_index is not None else None
        if char_index is not None:
            search_from = max(search_from, char_index + 1)
        anchor = item.get("anchor")
        if anchor is None and char_index is not None and 0 <= char_index < len(lyrics):
            anchor = lyrics[char_index]
        event = {
            "id": f"G{section_i + 1:02d}-{line_i + 1:02d}-{i + 1:03d}",
            "section": section_name,
            "line": line_i + 1,
            "chord": chord,
            "anchor": str(anchor or ""),
            "anchor_index": char_index,
            "bar": to_float(item.get("bar"), base_bar),
            "beat": to_float(item.get("beat"), 1.0 + (i % int(beats_per_bar))),
            "duration": to_float(item.get("duration"), 1.0),
            "allow_empty": bool(item.get("allow_empty", False)),
        }
        event["time_x"] = time_x(event, beats_per_bar)
        event["harmonic_y"] = chord_root_value(chord)
        events.append(event)
    return events


def match_intersections(
    guitar_events: list[dict[str, Any]],
    vocal_events: list[dict[str, Any]],
    section_i: int,
    line_i: int,
) -> list[dict[str, Any]]:
    by_char = {ev["char_index"]: ev for ev in vocal_events}
    intersections: list[dict[str, Any]] = []

    for i, guitar in enumerate(guitar_events):
        vocal = None
        match_type = "none"
        delta = 0.0
        idx = guitar.get("anchor_index")
        if idx is not None and idx in by_char:
            vocal = by_char[idx]
            match_type = "anchor"
            delta = abs(guitar["time_x"] - vocal["time_x"])
        elif vocal_events:
            vocal = min(vocal_events, key=lambda ev: abs(ev["time_x"] - guitar["time_x"]))
            delta = abs(guitar["time_x"] - vocal["time_x"])
            match_type = "time" if delta <= 0.25 else "nearest"

        if vocal is None:
            continue
        intersections.append(
            {
                "id": f"I{section_i + 1:02d}-{line_i + 1:02d}-{i + 1:03d}",
                "section": guitar["section"],
                "line": guitar["line"],
                "guitar_id": guitar["id"],
                "vocal_id": vocal["id"],
                "chord": guitar["chord"],
                "text": vocal["text"],
                "bar": guitar["bar"],
                "beat": guitar["beat"],
                "delta": round(delta, 3),
                "match_type": match_type,
                "x": guitar["time_x"],
                "y": (guitar["harmonic_y"] + vocal["melody_y"]) / 2,
            }
        )
    return intersections


def normalize(doc: dict[str, Any]) -> dict[str, Any]:
    song = dict(doc.get("song", {}))
    beats_per_bar = parse_meter(song.get("beat", song.get("meter")))
    sections_out = []
    guitar_all: list[dict[str, Any]] = []
    vocal_all: list[dict[str, Any]] = []
    intersections_all: list[dict[str, Any]] = []

    for section_i, section in enumerate(doc.get("sections", [])):
        section_name = str(section.get("name", f"Section {section_i + 1}"))
        lines_out = []
        for line_i, line in enumerate(section.get("lines", [])):
            lyrics = str(line.get("lyrics", ""))
            vocal_events = normalize_vocal_events(line, section_name, section_i, line_i, beats_per_bar)
            guitar_events = normalize_guitar_events(
                line, lyrics, vocal_events, section_name, section_i, line_i, beats_per_bar
            )
            intersections = match_intersections(guitar_events, vocal_events, section_i, line_i)
            lines_out.append(
                {
                    "lyrics": lyrics,
                    "cue": line.get("cue", ""),
                    "romaji": line.get("romaji", line.get("romanization", "")),
                    "jianpu": line.get("jianpu", ""),
                    "bar_grid": line.get("bar_grid", ""),
                    "guitar_events": guitar_events,
                    "vocal_events": vocal_events,
                    "intersections": intersections,
                }
            )
            guitar_all.extend(guitar_events)
            vocal_all.extend(vocal_events)
            intersections_all.extend(intersections)
        sections_out.append(
            {
                "name": section_name,
                "progression": section.get("progression", []),
                "notes": section.get("notes", section.get("instructions", [])),
                "lines": lines_out,
            }
        )

    return {
        "song": song,
        "chord_diagrams": doc.get("chord_diagrams", []),
        "layout": doc.get("layout", {}),
        "beats_per_bar": beats_per_bar,
        "sections": sections_out,
        "guitar_events": guitar_all,
        "vocal_events": vocal_all,
        "intersections": intersections_all,
    }


def matrix_payload(norm: dict[str, Any]) -> dict[str, Any]:
    guitar_columns = [
        "id",
        "section",
        "line",
        "bar",
        "beat",
        "duration",
        "chord",
        "anchor",
        "anchor_index",
        "time_x",
        "harmonic_y",
    ]
    vocal_columns = [
        "id",
        "section",
        "line",
        "char_index",
        "bar",
        "beat",
        "duration",
        "text",
        "jianpu",
        "time_x",
        "melody_y",
    ]
    intersection_columns = [
        "id",
        "section",
        "line",
        "guitar_id",
        "vocal_id",
        "chord",
        "text",
        "bar",
        "beat",
        "delta",
        "match_type",
        "x",
        "y",
    ]

    def row(item: dict[str, Any], columns: list[str]) -> list[Any]:
        return [item.get(col) for col in columns]

    return {
        "song": norm["song"],
        "matrices": {
            "guitar": {"columns": guitar_columns, "rows": [row(ev, guitar_columns) for ev in norm["guitar_events"]]},
            "vocal": {"columns": vocal_columns, "rows": [row(ev, vocal_columns) for ev in norm["vocal_events"]]},
            "intersection": {
                "columns": intersection_columns,
                "rows": [row(ev, intersection_columns) for ev in norm["intersections"]],
            },
        },
    }


def render_progression(progression: list[Any]) -> str:
    if not progression:
        return ""
    cells = "".join(f"<span>{html.escape(str(item))}</span>" for item in progression)
    return f'<p class="progression">{cells}</p>'


def render_section_notes(notes: Any) -> str:
    if not notes:
        return ""
    if isinstance(notes, str):
        notes = [notes]
    items = "".join(f"<p>{html.escape(str(note))}</p>" for note in notes)
    return f'<div class="section-notes">{items}</div>'


def render_chord_diagrams(diagrams: list[dict[str, Any]]) -> str:
    if not diagrams:
        return ""

    def marker(class_name: str, string: Any, text: str, fret: Any | None = None) -> str:
        style = f"--s:{html.escape(str(string), quote=True)}"
        if fret is not None:
            style += f";--f:{html.escape(str(fret), quote=True)}"
        return f'<span class="{class_name}" style="{style}">{html.escape(text)}</span>'

    cards = []
    for diagram in diagrams:
        name = html.escape(str(diagram.get("name", "")))
        marks = []
        for string in diagram.get("muted", []):
            marks.append(marker("muted", string, "×"))
        for string in diagram.get("open", []):
            marks.append(marker("open", string, "○"))
        for dot in diagram.get("dots", []):
            marks.append(marker("dot", dot.get("s"), str(dot.get("finger", "")), dot.get("f")))

        note = str(diagram.get("note", "")).strip()
        note_html = f"<p>{html.escape(note)}</p>" if note else ""
        cards.append(
            '<article class="chord-card">'
            f"<h3>{name}</h3>"
            f'<div class="chord-diagram" aria-label="{name} chord">{"".join(marks)}</div>'
            f"{note_html}"
            "</article>"
        )

    return (
        '<section class="diagram-section">'
        "<h2>不熟悉和弦</h2>"
        f'<div class="chord-sheet-grid">{"".join(cards)}</div>'
        "</section>"
    )


def render_site_nav(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    links = []
    for item in items:
        href = html.escape(str(item.get("href", "#")), quote=True)
        label = html.escape(str(item.get("label", "")))
        meta = html.escape(str(item.get("meta", "")))
        active = " is-active" if item.get("active") else ""
        links.append(
            f'<a class="song-link{active}" href="{href}">'
            f"<span>{label}</span>"
            f"<small>{meta}</small>"
            "</a>"
        )
    return (
        '<aside class="song-sidebar" aria-label="曲目">'
        '<div class="brand"><p>吉他譜曲庫</p><h1>曲目</h1></div>'
        f'<nav class="song-list">{"".join(links)}</nav>'
        '<div class="sidebar-actions">'
        '<button class="theme-toggle" type="button" data-theme-toggle aria-pressed="true">亮模式</button>'
        '<button class="print-button" type="button" onclick="window.print()">列印</button>'
        "</div>"
        "</aside>"
    )


def render_lyric_line(line: dict[str, Any]) -> str:
    anchors: dict[int, list[str]] = {}
    for event in line["guitar_events"]:
        idx = event.get("anchor_index")
        if idx is None:
            continue
        anchors.setdefault(int(idx), []).append(event["chord"])

    chunks: list[str] = ['<span class="lyric-phrase">']
    lyrics = line["lyrics"]
    for i, char in enumerate(clean_chars(lyrics)):
        if char == "\u3000":
            chunks.append('</span><span class="lyric-phrase">')
            continue
        escaped = html.escape(char)
        if i in anchors:
            label = " / ".join(anchors[i])
            label_len = len(label.replace(" ", ""))
            if label_len >= 5:
                hit_class = "hit long-chord"
            elif label_len >= 2:
                hit_class = "hit medium-chord"
            else:
                hit_class = "hit"
            chunks.append(
                f'<span class="{hit_class}" data-chord="{html.escape(label, quote=True)}">{escaped}</span>'
            )
        else:
            chunks.append(escaped)
    chunks.append("</span>")

    for event in line["guitar_events"]:
        if event.get("anchor_index") is None and event.get("allow_empty"):
            chunks.append(f'<span class="hit empty" data-chord="{html.escape(event["chord"], quote=True)}"></span>')

    romaji = str(line.get("romaji", "")).strip()
    cue = str(line.get("cue", "")).strip()
    cue_html = f'<span class="line-cue">{html.escape(cue)}</span>' if cue else ""
    if not romaji:
        return f'<p class="lyric-line">{cue_html}{"".join(chunks)}</p>'
    lyric_html = f'<p class="lyric-line jp-line phrase-layout">{cue_html}{"".join(chunks)}</p>'
    return (
        '<div class="vocal-pair">'
        f'{lyric_html}'
        f'<p class="romaji-line">{html.escape(romaji)}</p>'
        '</div>'
    )


def render_html(norm: dict[str, Any], svg_name: str) -> str:
    song = norm["song"]
    layout = norm.get("layout", {})
    renderer_options = layout.get("renderer", {}) if isinstance(layout.get("renderer", {}), dict) else {}
    is_compact = layout.get("profile") == "performance-compact"
    chart_class = "chart compact" if is_compact else "chart"
    show_matrix = bool(renderer_options.get("show_matrix_in_chart", True))
    site_nav = renderer_options.get("site_nav", layout.get("site_nav", []))
    include_site_nav = bool(renderer_options.get("include_site_nav", False) and site_nav)
    title = html.escape(str(song.get("title", "Untitled")))
    artist = html.escape(str(song.get("artist", "")))
    credits = "　".join(
        part
        for part in [
            artist,
            f'詞：{html.escape(str(song.get("lyricist")))}' if song.get("lyricist") else "",
            f'曲：{html.escape(str(song.get("composer")))}' if song.get("composer") else "",
            f'編曲：{html.escape(str(song.get("arranger")))}' if song.get("arranger") else "",
            f'製作：{html.escape(str(song.get("producer")))}' if song.get("producer") else "",
        ]
        if part
    )

    if song.get("play_key"):
        meta = [
            ("原調", song.get("key", "")),
            ("Play", song.get("play_key", "")),
            ("Capo", song.get("capo", "")),
            ("Beat", song.get("beat", song.get("meter", ""))),
        ]
    else:
        meta = [
            ("Key", song.get("key", "")),
            ("Capo", song.get("capo", "")),
            ("Beat", song.get("beat", song.get("meter", ""))),
        ]
    meta_html = "".join(
        f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(str(value or '-'))}</dd></div>" for label, value in meta
    )

    sections_html = []
    for section in norm["sections"]:
        body = render_section_notes(section.get("notes", []))
        body += render_progression(section.get("progression", []))
        body += "".join(render_lyric_line(line) for line in section["lines"])
        if not body:
            continue
        sections_html.append(
            f'<section class="section"><h2>{html.escape(section["name"])}</h2>{body}</section>'
        )

    diagrams_html = render_chord_diagrams(norm.get("chord_diagrams", []))
    site_nav_html = render_site_nav(site_nav if include_site_nav else [])
    shell_open = '<div class="app-shell">' if include_site_nav else ""
    shell_close = "</div>" if include_site_nav else ""
    toolbar_theme_html = "" if include_site_nav else '<button class="theme-toggle" type="button" data-theme-toggle aria-pressed="true">亮模式</button>'
    toolbar_html = "" if include_site_nav else f"""
      <nav class="toolbar" aria-label="工具列">
        {toolbar_theme_html}
        <button type="button" onclick="window.print()">列印</button>
      </nav>"""
    matrix_html = (
        '\n        <figure class="matrix-figure">'
        f'<img src="{html.escape(svg_name, quote=True)}" alt="吉他、人聲與交集 Trail 向量矩陣">'
        "</figure>"
        if show_matrix
        else ""
    )
    toolbar_slot = f"\n      {toolbar_html}" if toolbar_html else ""

    return f"""<!doctype html>
<html lang="zh-Hant" data-theme="dark">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}｜Trail 和弦譜</title>
    <script>
      (() => {{
        try {{
          document.documentElement.dataset.theme = localStorage.getItem("guitar-score-theme") || "dark";
        }} catch (error) {{
          document.documentElement.dataset.theme = "dark";
        }}
      }})();
    </script>
    <style>
      :root {{
        color-scheme: dark;
        --page: #171b1b;
        --sidebar: #121514;
        --sidebar-soft: #1d211f;
        --paper: #211a10;
        --ink: #f4eddf;
        --muted: #c7bcaa;
        --chord: #48b7ff;
        --rule: #4c473f;
        --section: #f06d7b;
        --accent: #dfb85b;
        --sidebar-text: #f6efe2;
        --sidebar-muted: #c8beb0;
        --sidebar-border: rgba(255,255,255,.08);
        --link-border: rgba(255,255,255,.1);
        --link-hover-bg: rgba(255,255,255,.08);
        --link-active-border: rgba(223,184,91,.7);
        --button-bg: #f6efe2;
        --button-ink: #171819;
        --paper-grid: rgba(255,255,255,.035);
        --chart-shadow: 0 20px 70px rgba(0,0,0,.38);
        --card-bg: rgba(255,255,255,.06);
        --diagram-line: #d8d0c1;
        --diagram-dot: #f4eddf;
        --diagram-dot-ink: #211a10;
        font-family: "PingFang TC", "Noto Sans TC", "Microsoft JhengHei", system-ui, sans-serif;
      }}
      :root[data-theme="light"] {{
        color-scheme: light;
        --page: #ece7dc;
        --sidebar: #f8f3e9;
        --sidebar-soft: #fffaf1;
        --paper: #fffaf0;
        --ink: #2c2d2e;
        --muted: #68635c;
        --chord: #1176b8;
        --rule: #d7d0c4;
        --section: #c9515b;
        --accent: #a57920;
        --sidebar-text: #2c2d2e;
        --sidebar-muted: #6b6257;
        --sidebar-border: rgba(44,45,46,.1);
        --link-border: rgba(44,45,46,.12);
        --link-hover-bg: rgba(223,184,91,.15);
        --link-active-border: rgba(165,121,32,.7);
        --button-bg: #171819;
        --button-ink: #fffaf0;
        --paper-grid: rgba(0,0,0,.022);
        --chart-shadow: 0 20px 70px rgba(44,45,46,.22);
        --card-bg: rgba(255,255,255,.68);
        --diagram-line: #27292a;
        --diagram-dot: #27292a;
        --diagram-dot-ink: #f7f3ea;
      }}
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; background: var(--page); color: var(--ink); }}
      .app-shell {{ display: grid; grid-template-columns: 276px minmax(0, 1fr); min-height: 100vh; }}
      .song-sidebar {{ position: sticky; top: 0; display: flex; flex-direction: column; gap: 26px; height: 100vh; padding: 28px 22px; background: linear-gradient(180deg, var(--sidebar), var(--sidebar-soft)); border-right: 1px solid var(--sidebar-border); color: var(--sidebar-text); }}
      .brand p, .brand h1, .song-link span, .song-link small {{ margin: 0; }}
      .brand p {{ color: var(--accent); font-size: 13px; font-weight: 850; }}
      .brand h1 {{ margin-top: 7px; font-size: 34px; line-height: 1; }}
      .song-list {{ display: grid; gap: 10px; }}
      .song-link {{ display: grid; gap: 7px; border: 1px solid var(--link-border); border-radius: 8px; color: inherit; padding: 14px 13px; text-decoration: none; transition: background 150ms ease, border-color 150ms ease, transform 150ms ease; }}
      .song-link:hover, .song-link:focus-visible, .song-link.is-active {{ background: var(--link-hover-bg); border-color: var(--link-active-border); }}
      .song-link:hover {{ transform: translateY(-1px); }}
      .song-link span {{ font-size: 18px; font-weight: 900; }}
      .song-link small {{ color: var(--sidebar-muted); font-size: 13px; font-weight: 700; }}
      .sidebar-actions {{ margin-top: auto; display: grid; gap: 10px; }}
      .page {{ display: flex; justify-content: center; min-height: 100vh; padding: 28px 16px 72px; }}
      .chart {{
        width: min(100%, 840px);
        min-height: 1120px;
        background:
          repeating-linear-gradient(0deg, var(--paper-grid) 0 1px, transparent 1px 4px),
          repeating-linear-gradient(90deg, var(--paper-grid) 0 1px, transparent 1px 5px),
          var(--paper);
        box-shadow: var(--chart-shadow);
        padding: 34px 42px 48px;
      }}
      .chart-header {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 24px;
        border-bottom: 2px solid var(--rule);
        padding-bottom: 18px;
        margin-bottom: 24px;
      }}
      h1, h2, p, dl, figure {{ margin: 0; }}
      h1 {{ color: var(--ink); font-size: 40px; line-height: 1; letter-spacing: 0; }}
      .chart-header p {{ margin-top: 10px; color: var(--muted); font-size: 16px; font-weight: 650; }}
      .song-key {{ display: grid; grid-template-columns: repeat({len(meta)}, auto); gap: 12px 18px; color: var(--muted); font-size: 14px; text-align: right; white-space: nowrap; }}
      .song-key div {{ display: grid; gap: 4px; }}
      .song-key dt {{ font-weight: 700; }}
      .song-key dd {{ color: var(--ink); font-size: 17px; font-weight: 900; }}
      .diagram-section {{ margin: 0 0 30px; border-bottom: 2px solid var(--rule); padding-bottom: 24px; }}
      .diagram-section h2 {{ margin: 0 0 14px; color: var(--section); font-size: 16px; font-weight: 900; }}
      .chord-sheet-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(92px, 1fr)); gap: 12px; }}
      .chord-card {{ display: grid; justify-items: center; min-height: 168px; border: 1px solid var(--rule); border-radius: 8px; background: var(--card-bg); padding: 12px 8px 10px; }}
      .chord-card h3 {{ margin: 0 0 12px; color: var(--chord); font-size: 24px; font-weight: 900; line-height: 1; }}
      .chord-card p {{ margin: 7px 0 0; color: var(--muted); font-size: 12px; font-weight: 760; line-height: 1.25; text-align: center; }}
      .chord-diagram {{
        --diagram-width: 78px;
        --diagram-height: 92px;
        --dot-size: 16px;
        position: relative;
        width: var(--diagram-width);
        height: var(--diagram-height);
        margin: 16px auto 22px;
        border-top: 4px solid var(--diagram-line);
        border-right: 2px solid var(--diagram-line);
        border-bottom: 2px solid var(--diagram-line);
        border-left: 2px solid var(--diagram-line);
        background:
          repeating-linear-gradient(to right, transparent 0 calc(20% - 1px), var(--diagram-line) calc(20% - 1px) calc(20% + 1px), transparent calc(20% + 1px) 20%),
          repeating-linear-gradient(to bottom, transparent 0 calc(20% - 1px), var(--diagram-line) calc(20% - 1px) calc(20% + 1px), transparent calc(20% + 1px) 20%);
      }}
      .chord-diagram::after {{ content: "E   A   D   G   B   e"; position: absolute; right: -2px; bottom: -22px; left: -2px; color: var(--muted); font-size: 10px; font-weight: 760; letter-spacing: 0; text-align: justify; text-align-last: justify; }}
      .dot, .open, .muted {{ position: absolute; left: 0; }}
      .dot {{ display: grid; place-items: center; width: var(--dot-size); height: var(--dot-size); border-radius: 999px; background: var(--diagram-dot); color: var(--diagram-dot-ink); font-size: 10px; font-weight: 900; line-height: 1; transform: translate(-50%, -50%); }}
      .open, .muted {{ top: -25px; color: var(--diagram-line); font-size: 20px; font-weight: 760; line-height: 1; transform: translateX(-50%); }}
      .chord-diagram [style*="--s:1"] {{ left: 0%; }}
      .chord-diagram [style*="--s:2"] {{ left: 20%; }}
      .chord-diagram [style*="--s:3"] {{ left: 40%; }}
      .chord-diagram [style*="--s:4"] {{ left: 60%; }}
      .chord-diagram [style*="--s:5"] {{ left: 80%; }}
      .chord-diagram [style*="--s:6"] {{ left: 100%; }}
      .chord-diagram .dot[style*="--f:1"] {{ top: 10%; }}
      .chord-diagram .dot[style*="--f:2"] {{ top: 30%; }}
      .chord-diagram .dot[style*="--f:3"] {{ top: 50%; }}
      .chord-diagram .dot[style*="--f:4"] {{ top: 70%; }}
      .chord-diagram .dot[style*="--f:5"] {{ top: 90%; }}
      .section {{ position: relative; display: grid; gap: 24px; margin-top: 34px; padding-left: 44px; }}
      .section h2 {{ position: absolute; left: 0; top: 16px; color: var(--section); font-size: 18px; font-weight: 900; }}
      .progression {{ display: flex; flex-wrap: wrap; gap: 20px; color: var(--chord); font-size: 24px; font-weight: 900; line-height: 1.2; }}
      .section-notes {{ display: grid; gap: 6px; border-left: 3px solid var(--section); padding-left: 12px; color: var(--muted); font-size: 16px; font-weight: 760; line-height: 1.35; }}
      .vocal-pair {{ display: grid; gap: 4px; }}
      .lyric-line {{ position: relative; min-height: 54px; padding-top: 24px; color: var(--ink); font-size: 21px; font-weight: 760; line-height: 1.45; letter-spacing: 0; word-spacing: .16em; }}
      .line-cue {{ display: inline-block; min-width: 2.8em; margin-right: .35em; color: var(--section); font-size: .72em; font-weight: 900; vertical-align: .08em; }}
      .phrase-layout {{ padding-top: 0; }}
      .lyric-phrase {{ display: inline-block; position: relative; margin-right: .9em; padding-top: 24px; }}
      .jp-line {{ word-spacing: .05em; }}
      .jp-line .hit {{ min-width: 1.08em; }}
      .jp-line .hit[data-chord="C#dim7"],
      .jp-line .hit[data-chord="F#m7-5"],
      .jp-line .hit[data-chord="C#m7-5"] {{ min-width: 4.8em; }}
      .jp-line .hit::before {{ font-size: .72em; top: -1.36em; }}
      .romaji-line {{ color: var(--muted); font-size: 14px; font-weight: 760; line-height: 1.35; letter-spacing: 0; }}
      .hit {{ position: relative; display: inline-block; min-width: .95em; word-spacing: 0; }}
      .hit.medium-chord {{ min-width: 1.35em; }}
      .hit.long-chord {{ min-width: 4.2em; }}
      .hit::before {{ content: attr(data-chord); position: absolute; left: 0; top: -1.48em; color: var(--chord); font-size: .92em; font-weight: 900; line-height: 1; white-space: nowrap; }}
      .hit.empty {{ width: 2.4em; }}
      .matrix-figure {{ margin-top: 44px; border-top: 2px solid var(--rule); padding-top: 22px; }}
      .matrix-figure img {{ display: block; width: 100%; height: auto; }}
      .chart.compact {{ min-height: auto; padding: 26px 38px 36px; }}
      .chart.compact .chart-header {{ padding-bottom: 12px; margin-bottom: 16px; }}
      .chart.compact h1 {{ font-size: 34px; }}
      .chart.compact .chart-header p {{ margin-top: 7px; font-size: 14px; line-height: 1.35; }}
      .chart.compact .song-key {{ gap: 8px 14px; font-size: 12px; }}
      .chart.compact .song-key dd {{ font-size: 16px; }}
      .chart.compact .diagram-section {{ margin-bottom: 18px; padding-bottom: 16px; }}
      .chart.compact .diagram-section h2 {{ margin-bottom: 10px; font-size: 15px; }}
      .chart.compact .chord-sheet-grid {{ grid-template-columns: repeat(auto-fit, minmax(82px, 1fr)); gap: 9px; }}
      .chart.compact .chord-card {{ min-height: 136px; padding: 8px 6px; }}
      .chart.compact .chord-card h3 {{ margin-bottom: 8px; font-size: 21px; }}
      .chart.compact .chord-card p {{ margin-top: 4px; font-size: 10.5px; line-height: 1.15; }}
      .chart.compact .chord-diagram {{ --diagram-width: 64px; --diagram-height: 76px; --dot-size: 14px; margin: 12px auto 18px; }}
      .chart.compact .chord-diagram::after {{ bottom: -18px; font-size: 9px; }}
      .chart.compact .dot {{ font-size: 9px; }}
      .chart.compact .open, .chart.compact .muted {{ top: -21px; font-size: 17px; }}
      .chart.compact .section {{ gap: 12px; margin-top: 20px; padding-left: 66px; }}
      .chart.compact .section h2 {{ top: 10px; width: 56px; font-size: 15px; line-height: 1.12; }}
      .chart.compact .progression {{ gap: 12px; font-size: 22px; }}
      .chart.compact .section-notes {{ gap: 4px; padding-left: 10px; font-size: 14px; line-height: 1.25; }}
      .chart.compact .lyric-line {{ min-height: 36px; padding-top: 17px; font-size: 19px; line-height: 1.26; word-spacing: .09em; }}
      .chart.compact .line-cue {{ min-width: 2.35em; margin-right: .2em; }}
      .chart.compact .lyric-phrase {{ margin-right: .55em; padding-top: 17px; }}
      .chart.compact .hit::before {{ top: -1.28em; font-size: .82em; }}
      .chart.compact .hit.empty {{ width: 2em; }}
      .toolbar {{ position: fixed; right: 18px; bottom: 18px; display: flex; gap: 10px; }}
      button {{ border: 0; border-radius: 999px; background: var(--button-bg); color: var(--button-ink); cursor: pointer; font: inherit; font-weight: 850; padding: 11px 18px; box-shadow: 0 10px 30px rgba(0,0,0,.32); }}
      .theme-toggle {{ border: 1px solid var(--link-active-border); background: transparent; color: var(--sidebar-text); }}
      @media (max-width: 720px) {{
        .app-shell {{ display: block; }}
        .song-sidebar {{ position: static; height: auto; }}
        .page {{ padding: 0 0 72px; }}
        .chart {{ padding: 24px 22px 40px; }}
        .chart.compact {{ padding: 22px 18px 34px; }}
        .chart-header {{ display: grid; }}
        .song-key {{ justify-content: start; text-align: left; }}
        .chord-sheet-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .section {{ padding-left: 0; }}
        .section h2 {{ position: static; }}
        .lyric-line {{ font-size: 18px; }}
        .lyric-phrase {{ margin-right: .55em; padding-top: 22px; }}
        .jp-line {{ word-spacing: 0; }}
        .jp-line .hit {{ min-width: 1em; }}
        .jp-line .hit[data-chord="C#dim7"],
        .jp-line .hit[data-chord="F#m7-5"],
        .jp-line .hit[data-chord="C#m7-5"] {{ min-width: 4.35em; }}
        .jp-line .hit::before {{ font-size: .66em; }}
        .hit.medium-chord {{ min-width: 1.18em; }}
        .hit.long-chord {{ min-width: 3.7em; }}
        .romaji-line {{ font-size: 12px; }}
      }}
      @page {{ size: A4 portrait; margin: 12mm; }}
      @media print {{
        body, .page {{ background: white; }}
        .app-shell, .page {{ display: block; min-height: 0; padding: 0; }}
        .song-sidebar {{ display: none; }}
        .page {{ display: block; min-height: 0; padding: 0; }}
        .chart {{ width: auto; min-height: 0; box-shadow: none; padding: 0; print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
        .toolbar {{ display: none; }}
      }}
    </style>
  </head>
  <body>
    {shell_open}
    {site_nav_html}
    <main class="page" aria-label="{title} Trail 和弦譜">
      <article class="{chart_class}">
        <header class="chart-header">
          <div>
            <h1>{title}</h1>
            <p>{credits}</p>
          </div>
          <dl class="song-key" aria-label="調性資訊">{meta_html}</dl>
        </header>
        {diagrams_html}
        {''.join(sections_html)}{matrix_html}
      </article>{toolbar_slot}
    </main>
    {shell_close}
    <script>
      (() => {{
        const root = document.documentElement;
        const themeKey = "guitar-score-theme";
        const buttons = () => Array.from(document.querySelectorAll("[data-theme-toggle]"));
        const applyTheme = (theme) => {{
          root.dataset.theme = theme;
          buttons().forEach((button) => {{
            const isDark = theme === "dark";
            button.textContent = isDark ? "亮模式" : "暗模式";
            button.setAttribute("aria-pressed", String(isDark));
          }});
        }};
        applyTheme(localStorage.getItem(themeKey) || root.dataset.theme || "dark");
        document.addEventListener("click", (event) => {{
          const button = event.target.closest("[data-theme-toggle]");
          if (!button) return;
          const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
          localStorage.setItem(themeKey, nextTheme);
          applyTheme(nextTheme);
        }});
      }})();
    </script>
  </body>
</html>
"""


def scale(value: float, src_min: float, src_max: float, dst_min: float, dst_max: float) -> float:
    if src_max <= src_min:
        return (dst_min + dst_max) / 2
    ratio = (value - src_min) / (src_max - src_min)
    return dst_min + ratio * (dst_max - dst_min)


def svg_text(x: float, y: float, text: Any, size: int = 18, weight: int = 700, color: str = "#2c2d2e") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
        f'fill="{color}" font-family="PingFang TC, Noto Sans TC, sans-serif">{html.escape(str(text))}</text>'
    )


def render_band(
    title: str,
    events: list[dict[str, Any]],
    y0: float,
    width: float,
    min_t: float,
    max_t: float,
    kind: str,
) -> str:
    left = 110
    right = width - 70
    top = y0 + 46
    bottom = y0 + 210
    parts = [
        f'<rect x="40" y="{y0}" width="{width - 80}" height="238" rx="8" fill="#fffaf0" stroke="#d7d0c4"/>',
        svg_text(64, y0 + 31, title, 24, 900, "#c9515b"),
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#9a9286" stroke-width="2"/>',
    ]
    for i in range(5):
        x = left + (right - left) * i / 4
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="#e5ded1" stroke-width="1"/>')

    if not events:
        parts.append(svg_text(left, y0 + 122, "No events", 18, 700, "#68635c"))
        return "\n".join(parts)

    for i, ev in enumerate(events[:120]):
        x = scale(float(ev.get("time_x", ev.get("x", 0))), min_t, max_t, left, right)
        if kind == "guitar":
            y = scale(float(ev.get("harmonic_y", 0)), 0, 11, bottom - 12, top + 12)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#1176b8"/>')
            parts.append(svg_text(x + 10, y - 8, ev.get("chord", ""), 15, 900, "#1176b8"))
        elif kind == "vocal":
            y = scale(float(ev.get("melody_y", 0)), 0, 7, bottom - 12, top + 12)
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#2c2d2e"/>')
            if i % 2 == 0:
                label = f'{ev.get("text", "")}{ev.get("jianpu", "")}'
                parts.append(svg_text(x + 7, y - 7, label, 13, 700, "#2c2d2e"))
        else:
            y = scale(float(ev.get("y", 0)), 0, 11, bottom - 12, top + 12)
            parts.append(f'<rect x="{x - 6:.1f}" y="{y - 6:.1f}" width="12" height="12" rx="3" fill="#c9515b"/>')
            label = f'{ev.get("chord", "")}/{ev.get("text", "")}'
            parts.append(svg_text(x + 9, y - 7, label, 13, 850, "#c9515b"))
    return "\n".join(parts)


def render_svg(norm: dict[str, Any]) -> str:
    width = 1400
    height = 860
    all_times = [ev.get("time_x", ev.get("x", 0)) for ev in norm["guitar_events"] + norm["vocal_events"] + norm["intersections"]]
    max_t = max([float(t) for t in all_times], default=1.0)
    min_t = min([float(t) for t in all_times], default=0.0)
    if max_t == min_t:
        max_t = min_t + 1.0
    title = norm["song"].get("title", "Untitled")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f3ea"/>',
        svg_text(40, 46, f"{title} Trail Vector Matrices", 30, 900, "#2c2d2e"),
        svg_text(40, 76, "Guitar chord trail, vocal/Jianpu trail, and their intersection points", 17, 700, "#68635c"),
        render_band("Guitar Chord Trail Matrix", norm["guitar_events"], 104, width, min_t, max_t, "guitar"),
        render_band("Vocal / Jianpu Trail Matrix", norm["vocal_events"], 356, width, min_t, max_t, "vocal"),
        render_band("Intersection Trail Matrix", norm["intersections"], 608, width, min_t, max_t, "intersection"),
        "</svg>",
    ]
    return "\n".join(parts)


def write_outputs(norm: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_name = "trail-matrix.svg"
    html_text = render_html(norm, svg_name)
    svg_text_out = render_svg(norm)
    matrices = matrix_payload(norm)
    matrices["outputs"] = {"html": "song.html", "image": svg_name}

    (out_dir / "song.html").write_text(html_text, encoding="utf-8")
    (out_dir / svg_name).write_text(svg_text_out, encoding="utf-8")
    (out_dir / "matrix-data.json").write_text(json.dumps(matrices, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Jianpu Trail matrix HTML and SVG outputs.")
    parser.add_argument("input_json", help="Path to normalized input JSON, or '-' for stdin.")
    parser.add_argument("--out-dir", default="outputs/jianpu-trail", help="Directory for generated files.")
    args = parser.parse_args()

    doc = read_source(args.input_json)
    norm = normalize(doc)
    write_outputs(norm, Path(args.out_dir))
    print(json.dumps({"out_dir": args.out_dir, "html": "song.html", "image": "trail-matrix.svg"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
