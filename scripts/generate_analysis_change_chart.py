#!/usr/bin/env python3
"""Generate a visual comparison chart between two daily forecast reports."""

from __future__ import annotations

import argparse
import html
import os
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class MatchRow:
    date: str
    team1: str
    team2: str
    team1_probability: float
    team2_probability: float

    @property
    def label(self) -> str:
        return f"{self.team1} vs {self.team2}"

    @property
    def favorite_probability(self) -> float:
        return max(self.team1_probability, self.team2_probability)


@dataclass
class ReportSnapshot:
    path: Path
    report_date: str
    completed_matches: int
    remaining_matches: int
    champion_probabilities: dict[str, float]
    next_matches: list[MatchRow]
    market_status: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a SVG change chart for forecast analysis.")
    parser.add_argument("--current", default="forecasts/latest.md", help="Current daily report Markdown.")
    parser.add_argument("--previous", help="Previous daily report Markdown. Defaults to newest older dated report.")
    parser.add_argument("--out", help="Dated SVG output path. Defaults to forecasts/analysis/YYYY-MM-DD-change.svg.")
    parser.add_argument("--latest-out", default="forecasts/analysis/latest-change.svg", help="Latest SVG copy path.")
    return parser


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_markdown_table(block: list[str]) -> list[dict[str, str]]:
    if len(block) < 3:
        return []
    headers = parse_cells(block[0])
    rows: list[dict[str, str]] = []
    for line in block[2:]:
        cells = parse_cells(line)
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def table_blocks_after_heading(lines: list[str], heading: str) -> list[list[str]]:
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return []
    heading_level = len(heading) - len(heading.lstrip("#"))
    blocks: list[list[str]] = []
    index = start + 1
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            if level <= heading_level:
                break
        if stripped.startswith("|"):
            block: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                block.append(lines[index])
                index += 1
            blocks.append(block)
            continue
        index += 1
    return blocks


def table_after_heading(lines: list[str], heading: str) -> list[dict[str, str]]:
    blocks = table_blocks_after_heading(lines, heading)
    return parse_markdown_table(blocks[0]) if blocks else []


def pct_to_float(value: object) -> float:
    text = "" if value is None else str(value)
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return 0.0
    number = float(match.group(0))
    return number / 100.0 if "%" in text else number


def int_from_value(value: object) -> int:
    text = "" if value is None else str(value)
    match = re.search(r"-?\d+", text)
    return int(match.group(0)) if match else 0


def report_date_from_text(text: str, path: Path) -> str:
    match = re.search(r"^#\s+.*?(\d{4}-\d{2}-\d{2})\s*$", text, flags=re.MULTILINE)
    if match:
        return match.group(1)
    if re.match(r"\d{4}-\d{2}-\d{2}", path.stem):
        return path.stem
    raise ValueError(f"Cannot determine report date from {path}")


def market_status_from_text(text: str) -> str:
    match = re.search(r"市场信号[:：]\s*([^|\n]+)", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"\|\s*市场来源\s*\|\s*([^|]+)\|", text)
    if match:
        return match.group(1).strip()
    return "未知"


def parse_snapshot(path: Path) -> ReportSnapshot:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    report_date = report_date_from_text(text, path)

    overview_rows = table_after_heading(lines, "### 当前概况")
    overview = {row.get("项目", ""): row.get("数值", "") for row in overview_rows}
    completed = int_from_value(overview.get("已完赛场次"))
    remaining = int_from_value(overview.get("剩余场次"))

    champion_rows = table_after_heading(lines, "### 冠军")
    champions = {
        row.get("球队", ""): pct_to_float(row.get("概率", ""))
        for row in champion_rows
        if row.get("球队")
    }

    next_blocks = table_blocks_after_heading(lines, "### 下一轮预测")
    next_matches: list[MatchRow] = []
    for block in next_blocks:
        if len(block) < 3:
            continue
        headers = parse_cells(block[0])
        if len(headers) >= 7 and headers[0] == "日期" and headers[1] == "球队 1" and headers[2] == "球队 2":
            for line in block[2:]:
                cells = parse_cells(line)
                if len(cells) < 7:
                    continue
                next_matches.append(
                    MatchRow(
                        date=cells[0],
                        team1=cells[1],
                        team2=cells[2],
                        team1_probability=pct_to_float(cells[4]),
                        team2_probability=pct_to_float(cells[6]),
                    )
                )
            break

    return ReportSnapshot(
        path=path,
        report_date=report_date,
        completed_matches=completed,
        remaining_matches=remaining,
        champion_probabilities=champions,
        next_matches=next_matches,
        market_status=market_status_from_text(text),
    )


def newest_older_daily_report(current: ReportSnapshot) -> Path | None:
    daily_dir = ROOT / "forecasts" / "daily"
    if not daily_dir.exists():
        return None
    candidates = sorted(
        path for path in daily_dir.glob("*.md") if re.match(r"\d{4}-\d{2}-\d{2}$", path.stem) and path.stem < current.report_date
    )
    return candidates[-1] if candidates else None


def fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def fmt_delta(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.1f}pp"


def confidence_counts(matches: list[MatchRow]) -> tuple[int, int]:
    high = len([row for row in matches if row.favorite_probability >= 0.80])
    low = len([row for row in matches if row.favorite_probability < 0.58])
    return high, low


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: max(0, limit - 3)] + "..."


def card(x: int, y: int, width: int, height: int) -> str:
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" class="card"/>'


def metric_card(x: int, label: str, old_value: str, new_value: str, delta: str, delta_class: str) -> list[str]:
    return [
        card(x, 120, 220, 116),
        f'<text x="{x + 20}" y="154" class="small">{esc(label)}</text>',
        f'<text x="{x + 20}" y="194" class="num">{esc(old_value)} → {esc(new_value)}</text>',
        f'<text x="{x + 20}" y="222" class="small {delta_class}">{esc(delta)}</text>',
    ]


def render_delta_bar(x: int, y: int, delta: float, max_abs_delta: float) -> str:
    baseline = x + 150
    width = min(145.0, abs(delta) / max_abs_delta * 145.0) if max_abs_delta else 0
    color_class = "green" if delta >= 0 else "red"
    bar_x = baseline if delta >= 0 else baseline - width
    return "\n".join(
        [
            f'<rect x="{x}" y="{y}" width="300" height="16" rx="8" class="barbg"/>',
            f'<rect x="{bar_x:.1f}" y="{y}" width="{width:.1f}" height="16" rx="8" class="{color_class}"/>',
            f'<line x1="{baseline}" y1="{y - 5}" x2="{baseline}" y2="{y + 21}" stroke="#98a2b3" stroke-width="1"/>',
        ]
    )


def render_chart(previous: ReportSnapshot, current: ReportSnapshot) -> str:
    old_matches = {row.label: row for row in previous.next_matches}
    new_matches = {row.label: row for row in current.next_matches}
    removed = [label for label in old_matches if label not in new_matches]
    added = [label for label in new_matches if label not in old_matches]
    old_high, old_low = confidence_counts(previous.next_matches)
    new_high, new_low = confidence_counts(current.next_matches)

    teams = list(current.champion_probabilities)[:6]
    for team in previous.champion_probabilities:
        if team not in teams and len(teams) < 6:
            teams.append(team)
    deltas = [
        (team, previous.champion_probabilities.get(team, 0.0), current.champion_probabilities.get(team, 0.0))
        for team in teams
    ]
    max_abs_delta = max([abs(new - old) for _, old, new in deltas] or [0.01])
    max_abs_delta = max(max_abs_delta, 0.01)

    completed_delta = current.completed_matches - previous.completed_matches
    remaining_delta = current.remaining_matches - previous.remaining_matches
    queue_delta = len(current.next_matches) - len(previous.next_matches)
    completed_class = "pos" if completed_delta >= 0 else "neg"
    remaining_class = "pos" if remaining_delta >= 0 else "neg"
    queue_class = "pos" if queue_delta >= 0 else "neg"

    if removed:
        removed_text = "从预测表移除：" + "、".join(removed[:4])
    else:
        removed_text = "从预测表移除：无"
    if added:
        added_text = "新增待预测：" + "、".join(added[:4])
    else:
        added_text = "新增待预测：无"

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="880" viewBox="0 0 1200 880" role="img" aria-label="世界杯预测变化图">',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Noto Sans CJK SC",Arial,sans-serif}.bg{fill:#f6f7f2}.card{fill:#fff;stroke:#d9ded5}.title{font-size:34px;font-weight:700;fill:#172026}.subtitle{font-size:15px;fill:#667085}.h{font-size:21px;font-weight:700;fill:#172026}.label{font-size:16px;font-weight:600;fill:#172026}.small{font-size:13px;fill:#667085}.num{font-size:18px;font-weight:700;fill:#172026}.pos{fill:#13795b}.neg{fill:#c2410c}.zero{fill:#667085}.barbg{fill:#edf1ec}.green{fill:#13795b}.red{fill:#c2410c}</style>',
        '<rect width="1200" height="880" class="bg"/>',
        f'<text x="44" y="58" class="title">{esc(previous.report_date)} → {esc(current.report_date)} 预测变化图</text>',
        f'<text x="44" y="88" class="subtitle">来源：{esc(os.path.relpath(previous.path, ROOT))} 与 {esc(os.path.relpath(current.path, ROOT))}；市场信号：{esc(current.market_status)}</text>',
    ]
    parts.extend(
        metric_card(
            44,
            "已完赛",
            f"{previous.completed_matches} 场",
            f"{current.completed_matches} 场",
            f"{completed_delta:+d} 场",
            completed_class,
        )
    )
    parts.extend(
        metric_card(
            294,
            "剩余场次",
            f"{previous.remaining_matches} 场",
            f"{current.remaining_matches} 场",
            f"{remaining_delta:+d} 场",
            remaining_class,
        )
    )
    parts.extend(
        metric_card(
            544,
            "待预测16强",
            f"{len(previous.next_matches)} 场",
            f"{len(current.next_matches)} 场",
            f"{queue_delta:+d} 场",
            queue_class,
        )
    )

    parts.append(card(44, 270, 1112, 360))
    parts.append('<text x="70" y="312" class="h">冠军概率变化</text>')
    for index, (team, old_probability, new_probability) in enumerate(deltas):
        y = 352 + index * 40
        delta = new_probability - old_probability
        delta_class = "pos" if delta > 0 else "neg" if delta < 0 else "zero"
        parts.append(f'<text x="72" y="{y}" class="label">{esc(truncate(team, 12))}</text>')
        parts.append(f'<text x="230" y="{y}" class="small">{esc(fmt_pct(old_probability))} → {esc(fmt_pct(new_probability))}</text>')
        parts.append(render_delta_bar(430, y - 14, delta, max_abs_delta))
        parts.append(f'<text x="760" y="{y}" class="num {delta_class}">{esc(fmt_delta(delta))}</text>')

    parts.append(card(44, 660, 1112, 156))
    parts.append('<text x="70" y="702" class="h">16强预测队列变化</text>')
    parts.append(f'<text x="70" y="738" class="label">{esc(truncate(removed_text, 68))}</text>')
    parts.append(f'<text x="70" y="772" class="small">{esc(truncate(added_text, 90))}</text>')
    parts.append(
        f'<text x="70" y="802" class="small">高置信场次：{old_high} → {new_high}；低置信接近盘：{old_low} → {new_low}。不在图中补写比分或赛事实况。</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> int:
    args = build_parser().parse_args()
    current = parse_snapshot(resolve_path(args.current))
    previous_path = resolve_path(args.previous) if args.previous else newest_older_daily_report(current)
    if previous_path is None:
        print("No older daily report found; change chart was not generated.")
        return 0
    previous = parse_snapshot(previous_path)
    out_path = resolve_path(args.out) if args.out else ROOT / "forecasts" / "analysis" / f"{current.report_date}-change.svg"
    latest_out = resolve_path(args.latest_out)
    chart = render_chart(previous, current)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(chart, encoding="utf-8")
    latest_out.parent.mkdir(parents=True, exist_ok=True)
    latest_out.write_text(chart, encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"Wrote {latest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
