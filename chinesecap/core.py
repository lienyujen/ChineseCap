from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from uuid import uuid4


@dataclass
class Cue:
    start: float
    end: float
    speaker: str
    raw: str
    text: str = ""
    notes: list[str] = field(default_factory=list)


def stamp(seconds: float, srt: bool = False) -> str:
    ms = max(0, round(seconds * 1000))
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02}:{m:02}:{s:02}{',' if srt else '.'}{ms:03}"


def clean_text(text: str) -> str:
    from opencc import OpenCC
    text = OpenCC("s2twp").convert(text).strip()
    # Only unambiguous hesitation sounds at punctuation/utterance boundaries.
    text = re.sub(r"(^|[，,。！？、；：\s])(?:嗯+|呃+|呣+)[，,。！？、；：\s]*", r"\1", text)
    # A standalone, comma-delimited filler is different from 「那個人」 or 「就是老師」.
    while True:
        reduced = re.sub(r"(^|[，,]\s*)(?:那個|這個|就是|就是說)\s*[，,]\s*", r"\1", text)
        if reduced == text:
            break
        text = reduced
    return text.strip(" ，,、；")


def speaker_at(start: float, end: float, turns: list[tuple]) -> tuple[str, list[str]]:
    scores: dict[int, float] = {}
    intersections = []
    for a, b, speaker in turns:
        left, right = max(start, a), min(end, b)
        if right > left:
            scores[speaker] = scores.get(speaker, 0) + right - left
            intersections.append((left, right, speaker))
    if not scores:
        return "未辨識", ["無法判定說話者"]
    best = max(scores, key=scores.get)
    overlap = any(x[2] != y[2] and min(x[1], y[1]) - max(x[0], y[0]) > 0.04
                  for i, x in enumerate(intersections) for y in intersections[i + 1:])
    if overlap:
        return "重疊發言", ["多人同時發言，需聽音確認"]
    notes = ["說話者邊界不確定"] if scores[best] < (end - start) * .55 else []
    return f"說話者 {best + 1}", notes


def make_cues(words: list[tuple], turns: list[tuple] | None) -> list[Cue]:
    cues: list[Cue] = []
    for start, end, text in words:
        if not text.strip() or end <= start:
            continue
        speaker, notes = speaker_at(start, end, turns) if turns is not None else ("未分辨", [])
        last = cues[-1] if cues else None
        if (last and last.speaker == speaker and end - last.start <= 6
                and len(last.raw) + len(text) <= 36 and start - last.end < .8
                and not re.search(r"[。！？!?]$", last.raw)):
            last.end = end
            last.raw += text
            last.notes = list(dict.fromkeys(last.notes + notes))
        else:
            cues.append(Cue(start, end, speaker, text, notes=notes))
    for cue in cues:
        cue.text = clean_text(cue.raw)
    return cues


def validate_correction(original: str, candidate: str) -> bool:
    if not isinstance(candidate, str) or "\n" in candidate or len(candidate) > max(24, len(original) * 1.6):
        return False
    # Never silently change numeric values. Other uncertain edits are reviewed in the UI.
    if re.findall(r"\d+(?:[.,]\d+)*", original) != re.findall(r"\d+(?:[.,]\d+)*", candidate):
        return False
    if len(original) >= 12 and len(candidate) < len(original) * .5:
        return False
    a = re.sub(r'\W', '', original)
    b = re.sub(r'\W', '', candidate)
    if len(a) >= 4 and SequenceMatcher(None, a, b).ratio() < .65:
        return False
    return True


def validate_cues(cues: list[Cue]) -> None:
    previous = 0.0
    for c in cues:
        if not (math.isfinite(c.start) and math.isfinite(c.end) and 0 <= c.start < c.end):
            raise ValueError("字幕時間必須是有效的正向時間區間")
        if c.start < previous - .001:
            raise ValueError("字幕順序或時間重疊，請修正後再匯出")
        previous = c.end


def subtitle_lines(text: str, preferred: int = 26) -> str:
    """Wrap only at punctuation; never cut an uninterrupted Chinese term by width."""
    if len(text) <= preferred:
        return text
    parts = [part for part in re.split(r'(?<=[，,、；;：:。！？!?])', text) if part]
    if len(parts) == 1:
        return text
    lines: list[str] = []
    current = ''
    for part in parts:
        if current and len(current) + len(part) > preferred:
            lines.append(current)
            current = part
        else:
            current += part
    if current:
        lines.append(current)
    return '\n'.join(lines)


def export(cues: list[Cue], parent: Path, name: str, metadata: dict,
           speaker_in_srt: bool = True) -> Path:
    validate_cues(cues)
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(' .')[:80] or '逐字稿'
    target = parent / f"{safe}_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
    target.mkdir(parents=True, exist_ok=False)
    cleaned, raw, subtitles = [], [], []
    for c in cues:
        raw.append(f"[{stamp(c.start)}] {c.speaker}：{c.raw}")
        text = c.text.replace('\r', ' ').replace('\n', ' ').strip()
        if not text:
            continue
        cleaned.append(f"[{stamp(c.start)}] {c.speaker}：{text}")
        line = f"{c.speaker}：{text}" if speaker_in_srt else text
        # YouTube/player may wrap long lines visually. We only add a newline at
        # punctuation, so an uninterrupted name or technical term is never cut.
        wrapped = subtitle_lines(line)
        subtitles.append(f"{len(subtitles)+1}\n{stamp(c.start, True)} --> {stamp(c.end, True)}\n{wrapped}\n")
    (target / '逐字稿.txt').write_text('\n'.join(cleaned) + '\n', encoding='utf-8-sig')
    (target / '原始辨識.txt').write_text('\n'.join(raw) + '\n', encoding='utf-8-sig')
    (target / '字幕.srt').write_text('\n'.join(subtitles), encoding='utf-8')
    (target / '專案.json').write_text(json.dumps({'version': 1, 'metadata': metadata,
        'cues': [asdict(c) for c in cues]}, ensure_ascii=False, indent=2), encoding='utf-8')
    return target


def load_project(path: Path) -> tuple[list[Cue], dict]:
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if data.get('version') != 1:
        raise ValueError('不支援的專案版本')
    cues = [Cue(**row) for row in data['cues']]
    validate_cues(cues)
    return cues, data.get('metadata', {})
