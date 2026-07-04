#!/usr/bin/env python3
"""Generate a visual-first daily World Cup forecast report for GitHub."""

from __future__ import annotations

import argparse
import html as html_lib
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

import worldcup_forecast as forecast


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "assets" / "daily-report-template.md"
FLAG_ICONS_VERSION = "7.5.0"
FLAG_BASE_URL = f"https://cdn.jsdelivr.net/gh/lipis/flag-icons@{FLAG_ICONS_VERSION}/flags/4x3"
FLAG_LICENSE_URL = f"https://cdn.jsdelivr.net/gh/lipis/flag-icons@{FLAG_ICONS_VERSION}/LICENSE"


def shanghai_tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("Asia/Shanghai")
        except Exception:
            pass
    return timezone(timedelta(hours=8), name="Asia/Shanghai")


def demote_headings(markdown: str) -> str:
    return re.sub(r"^(#{1,5}) ", lambda match: "#" + match.group(1) + " ", markdown, flags=re.MULTILINE)


def embed_markdown(markdown: str) -> str:
    lines = markdown.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
        if lines and not lines[0].strip():
            lines = lines[1:]
    return demote_headings("\n".join(lines).strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a daily World Cup forecast report.")
    parser.add_argument("--season", type=int, default=2026, help="World Cup season.")
    parser.add_argument("--runs", type=int, default=5000, help="Monte Carlo runs for final forecasts.")
    parser.add_argument("--seed", type=int, help="Deterministic random seed. Defaults to the report date as YYYYMMDD.")
    parser.add_argument("--date", help="Report date in YYYY-MM-DD. Defaults to current Asia/Shanghai date.")
    parser.add_argument("--out-dir", default="forecasts/daily", help="Directory for dated reports.")
    parser.add_argument("--latest-path", default="forecasts/latest.md", help="Path for the latest report copy.")
    parser.add_argument("--asset-dir", default="forecasts/assets", help="Directory for generated dashboard assets.")
    parser.add_argument("--flag-cache-dir", default="forecasts/assets/flags", help="Directory for cached SVG flag assets.")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="Report language.")
    parser.add_argument("--no-elo", action="store_true", help="Disable public Elo ratings enhancement.")
    parser.add_argument("--use-fifa-ranking", action="store_true", help="Fetch optional FIFA rankings.")
    parser.add_argument("--market-signals-file", help="Optional JSON file with odds or prediction-market signals.")
    parser.add_argument("--market-weight", type=float, default=0.35, help="Default market blend weight.")
    parser.add_argument("--no-fetch-flags", action="store_true", help="Do not download missing SVG flags into the local cache.")
    return parser


def report_labels(lang: str) -> dict[str, str]:
    if lang == "zh":
        return {
            "title": "世界杯预测日报",
            "generated": "生成时间",
            "season": "赛季",
            "runs": "最终排名模拟次数",
            "seed": "随机种子",
            "market": "市场信号",
            "no_market": "未配置",
            "disclaimer": "本报告基于公开赛事数据、透明启发式模型和可选赔率/预测市场信号生成，仅作方向性预测，不是投注建议。",
            "current": "当前概况",
            "next": "下一轮预测",
            "final": "最终预测",
            "dashboard_alt": "世界杯预测看板",
            "key_conclusions": "今日结论",
            "details": "可审计明细",
        }
    return {
        "title": "World Cup Forecast",
        "generated": "Generated at",
        "season": "season",
        "runs": "Final simulation runs",
        "seed": "Seed",
        "market": "Market signals",
        "no_market": "not configured",
        "disclaimer": "This is a directional forecast generated from public tournament data, transparent heuristics, and optional market/odds signals. It is not betting advice.",
        "current": "Current State",
        "next": "Next Round",
        "final": "Final Forecast",
        "dashboard_alt": "World Cup forecast dashboard",
        "key_conclusions": "Key Conclusions",
        "details": "Auditable Details",
    }


def fetch_text(url: str, timeout: int = 20) -> str:
    request = Request(url, headers={"User-Agent": "world-cup-forecast-skill/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def ensure_flag_license(flag_dir: Path, fetch_enabled: bool) -> None:
    if not fetch_enabled:
        return
    flag_dir.mkdir(parents=True, exist_ok=True)
    license_path = flag_dir / "LICENSE.flag-icons.txt"
    if license_path.exists():
        return
    try:
        text = fetch_text(FLAG_LICENSE_URL)
    except (HTTPError, URLError, TimeoutError, OSError):
        return
    license_path.write_text(text, encoding="utf-8")


def ensure_flag_svg(code: str | None, flag_dir: Path, fetch_enabled: bool) -> Path | None:
    if not code:
        return None
    flag_dir.mkdir(parents=True, exist_ok=True)
    path = flag_dir / f"{code}.svg"
    if path.exists():
        return path
    if not fetch_enabled:
        return None
    try:
        text = fetch_text(f"{FLAG_BASE_URL}/{code}.svg")
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    if "<svg" not in text:
        return None
    path.write_text(text, encoding="utf-8")
    return path


def esc(value: object) -> str:
    return html_lib.escape("" if value is None else str(value), quote=True)


def pct(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.{digits}f}%"


def display_team(team: object, lang: str) -> str:
    return forecast.display_team(team, lang)


def truncate(value: object, limit: int) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: max(0, limit - 3)] + "..."


def relative_markdown_path(markdown_path: Path, asset_path: Path) -> str:
    return os.path.relpath(asset_path, start=markdown_path.parent).replace(os.sep, "/")


def inline_flag(team: object, x: float, y: float, width: float, height: float, flag_dir: Path, fetch_enabled: bool) -> str:
    code = forecast.team_flag_code(team)
    path = ensure_flag_svg(code, flag_dir, fetch_enabled)
    if path:
        raw = path.read_text(encoding="utf-8")
        raw = re.sub(r"<\?xml[^>]*>\s*", "", raw).strip()
        match = re.search(r"<svg\b([^>]*)>(.*)</svg>\s*$", raw, flags=re.DOTALL)
        if match:
            attrs, inner = match.groups()
            view_box_match = re.search(r"viewBox=[\"']([^\"']+)[\"']", attrs)
            view_box = view_box_match.group(1) if view_box_match else "0 0 640 480"
            inner = prefix_svg_ids(inner, f"flag-{code}-{int(x)}-{int(y)}")
            return (
                f'<rect x="{x - 1:.1f}" y="{y - 1:.1f}" width="{width + 2:.1f}" height="{height + 2:.1f}" rx="4" fill="#ffffff" stroke="#d4d9d0"/>'
                f'<svg x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" viewBox="{esc(view_box)}" preserveAspectRatio="xMidYMid slice">{inner}</svg>'
            )
    label = truncate(display_team(team, "zh"), 2)
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="4" fill="#e8ece6" stroke="#cfd6ca"/>'
        f'<text x="{x + width / 2:.1f}" y="{y + height / 2 + 5:.1f}" text-anchor="middle" class="flag-fallback">{esc(label)}</text>'
    )


def prefix_svg_ids(inner: str, prefix: str) -> str:
    ids = sorted(set(re.findall(r"\bid=[\"']([^\"']+)[\"']", inner)), key=len, reverse=True)
    for old_id in ids:
        new_id = f"{prefix}-{old_id}"
        inner = inner.replace(f'id="{old_id}"', f'id="{new_id}"')
        inner = inner.replace(f"id='{old_id}'", f"id='{new_id}'")
        inner = inner.replace(f'url(#{old_id})', f'url(#{new_id})')
        inner = inner.replace(f'href="#{old_id}"', f'href="#{new_id}"')
        inner = inner.replace(f"href='#{old_id}'", f"href='#{new_id}'")
        inner = inner.replace(f'xlink:href="#{old_id}"', f'xlink:href="#{new_id}"')
        inner = inner.replace(f"xlink:href='#{old_id}'", f"xlink:href='#{new_id}'")
    return inner


def card(x: float, y: float, width: float, height: float) -> str:
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" class="card"/>'


def section_title(text: str, x: float, y: float) -> str:
    return f'<text x="{x}" y="{y}" class="section-title">{esc(text)}</text>'


def confidence_label(probability: float, lang: str) -> tuple[str, str]:
    if probability >= 0.80:
        return ("高置信" if lang == "zh" else "High", "high")
    if probability >= 0.65:
        return ("中置信" if lang == "zh" else "Medium", "medium")
    return ("低置信" if lang == "zh" else "Low", "low")


def forecast_rows(next_round: dict[str, object]) -> list[dict[str, object]]:
    return [row for row in next_round.get("predictions", []) if isinstance(row, dict) and row.get("status") == "forecast"]


def favorite_for_match(row: dict[str, object]) -> tuple[str, float]:
    p1 = float(row.get("team1_probability") or 0.0)
    p2 = float(row.get("team2_probability") or 0.0)
    if p1 >= p2:
        return str(row.get("team1") or ""), p1
    return str(row.get("team2") or ""), p2


def build_conclusions(current: dict[str, object], next_round: dict[str, object], final: dict[str, object], lang: str) -> str:
    champion_rows = final.get("rankings", {}).get("champion", []) if isinstance(final.get("rankings"), dict) else []
    matches = forecast_rows(next_round)
    top = champion_rows[0] if champion_rows else {}
    clear_matches = [row for row in matches if favorite_for_match(row)[1] >= 0.80]
    tight_matches = [row for row in matches if favorite_for_match(row)[1] < 0.58]
    warnings = set(current.get("rating_warnings", []) or [])
    warnings.update(next_round.get("rating_warnings", []) or [])
    warnings.update(next_round.get("market_warnings", []) or [])
    warnings.update(final.get("rating_warnings", []) or [])
    warnings.update(final.get("market_warnings", []) or [])
    market_sources = (next_round.get("market_sources") or []) + (final.get("market_sources") or [])
    if lang == "zh":
        lines = []
        if top:
            lines.append(f"- 冠军主线：{display_team(top.get('team'), lang)} 以 `{pct(top.get('probability'))}` 排在第一。")
        lines.append(f"- 下一轮：`{len(clear_matches)}` 场是高置信方向，`{len(tight_matches)}` 场是低置信接近盘。")
        lines.append(f"- 市场信号：{', '.join(dict.fromkeys(market_sources)) if market_sources else '未配置'}。数据警告 `{len([w for w in warnings if w])}` 条。")
        return "\n".join(lines)
    lines = []
    if top:
        lines.append(f"- Champion line: {display_team(top.get('team'), lang)} leads at `{pct(top.get('probability'))}`.")
    lines.append(f"- Next round: `{len(clear_matches)}` high-confidence favorites and `{len(tight_matches)}` low-confidence near coin flips.")
    lines.append(f"- Market signals: {', '.join(dict.fromkeys(market_sources)) if market_sources else 'not configured'}. Data warnings: `{len([w for w in warnings if w])}`.")
    return "\n".join(lines)


def render_metadata(labels: dict[str, str], now: datetime, args: argparse.Namespace, seed: int, market_line: str) -> str:
    return "\n".join(
        [
            f"{labels['generated']}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} | {labels['season']}: {args.season}",
            f"{labels['runs']}: {args.runs} | {labels['seed']}: {seed} | {labels['market']}: {market_line}",
        ]
    )


def render_report_from_template(context: dict[str, str]) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    report = template
    for key, value in context.items():
        report = report.replace("{{" + key + "}}", value)
    missing = sorted(set(re.findall(r"{{([a-zA-Z0-9_]+)}}", report)))
    if missing:
        raise RuntimeError(f"daily report template has unresolved placeholders: {', '.join(missing)}")
    return report.rstrip() + "\n"


def load_daily_data(args: argparse.Namespace, seed: int) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    data = forecast.fetch_json(forecast.season_url(args.season, None))
    public_ratings = forecast.load_public_ratings(
        forecast.team_names_from_matches(data.get("matches", [])),
        None,
        None,
        None,
        use_elo=not args.no_elo,
        use_fifa=args.use_fifa_ranking,
    )
    historical, _ = forecast.load_historical_strength(None, current_year=args.season)
    market_signals = forecast.load_market_signals(args.market_signals_file)
    market_weight = forecast.clamp(args.market_weight, 0.0, 0.65)
    current = forecast.current_summary(data, args.season, public_ratings)
    next_round = forecast.next_round_predictions(data, args.season, historical, public_ratings, market_signals, market_weight)
    final = forecast.final_predictions(data, args.season, historical, args.runs, seed, public_ratings, market_signals, market_weight)
    return current, next_round, final


def render_dashboard(
    report_date: str,
    now: datetime,
    args: argparse.Namespace,
    seed: int,
    current: dict[str, object],
    next_round: dict[str, object],
    final: dict[str, object],
    flag_dir: Path,
    fetch_flags: bool,
    lang: str,
) -> str:
    ensure_flag_license(flag_dir, fetch_flags)
    width = 1200
    height = 1560
    champion_rows = final.get("rankings", {}).get("champion", []) if isinstance(final.get("rankings"), dict) else []
    podium_rows = final.get("podiums", []) if isinstance(final.get("podiums"), list) else []
    matches = forecast_rows(next_round)
    scorers = current.get("top_scorers", []) if isinstance(current.get("top_scorers"), list) else []
    warnings = set(current.get("rating_warnings", []) or [])
    warnings.update(next_round.get("rating_warnings", []) or [])
    warnings.update(next_round.get("market_warnings", []) or [])
    warnings.update(final.get("rating_warnings", []) or [])
    warnings.update(final.get("market_warnings", []) or [])
    market_sources = list(dict.fromkeys((next_round.get("market_sources") or []) + (final.get("market_sources") or [])))
    rating_sources = list(dict.fromkeys((current.get("rating_sources") or []) + (next_round.get("rating_sources") or []) + (final.get("rating_sources") or [])))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="World Cup forecast dashboard">',
        "<defs>",
        "<style>",
        "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Noto Sans CJK SC',Arial,sans-serif}.bg{fill:#f6f7f2}.card{fill:#fff;stroke:#d9ded5;stroke-width:1}.title{font-size:38px;font-weight:700;fill:#172026}.subtitle{font-size:16px;font-weight:400;fill:#586069}.section-title{font-size:22px;font-weight:700;fill:#172026}.label{font-size:16px;font-weight:600;fill:#172026}.small{font-size:13px;font-weight:400;fill:#667085}.number{font-size:19px;font-weight:700;fill:#172026}.metric{font-size:28px;font-weight:700;fill:#172026}.chip{fill:#eef3ee;stroke:#d7dfd4}.chip-text{font-size:13px;font-weight:600;fill:#475467}.flag-fallback{font-size:13px;font-weight:700;fill:#475467}.bar-bg{fill:#edf1ec}.bar-a{fill:#1f6feb}.bar-b{fill:#d97706}.bar-win{fill:#13795b}.high{fill:#dff3ea}.medium{fill:#fff0cf}.low{fill:#fbe3dc}.high-text{fill:#13795b}.medium-text{fill:#b25e00}.low-text{fill:#c2410c}",
        "</style>",
        "</defs>",
        '<rect width="1200" height="1560" class="bg"/>',
        f'<text x="42" y="62" class="title">{"世界杯预测日报" if lang == "zh" else "World Cup Forecast"} {esc(report_date)}</text>',
        f'<text x="44" y="94" class="subtitle">{esc(now.strftime("%Y-%m-%d %H:%M:%S %Z"))} · season {args.season} · runs {args.runs} · seed {seed}</text>',
    ]

    chip_y = 112
    chips = [
        f"{current.get('completed_matches', 0)} completed",
        f"{current.get('remaining_matches', 0)} remaining",
        f"market: {', '.join(market_sources) if market_sources else ('未配置' if lang == 'zh' else 'none')}",
        f"warnings: {len([w for w in warnings if w])}",
    ]
    x = 42
    for chip in chips:
        chip_w = max(118, len(chip) * 8 + 28)
        parts.append(f'<rect x="{x}" y="{chip_y}" width="{chip_w}" height="30" rx="15" class="chip"/>')
        parts.append(f'<text x="{x + 14}" y="{chip_y + 20}" class="chip-text">{esc(chip)}</text>')
        x += chip_w + 12

    parts.append(card(40, 160, 540, 435))
    parts.append(section_title("冠军概率 Top 6" if lang == "zh" else "Champion Probability Top 6", 66, 202))
    max_champion = max([float(row.get("probability") or 0.0) for row in champion_rows[:6]] or [1.0])
    colors = ["#13795b", "#1f6feb", "#d97706", "#7c3aed", "#c2410c", "#667085"]
    for index, row in enumerate(champion_rows[:6], start=1):
        y = 228 + (index - 1) * 56
        team = row.get("team")
        probability = float(row.get("probability") or 0.0)
        parts.append(f'<text x="66" y="{y + 25}" class="small">{index}</text>')
        parts.append(inline_flag(team, 92, y + 4, 42, 30, flag_dir, fetch_flags))
        parts.append(f'<text x="148" y="{y + 24}" class="label">{esc(display_team(team, lang))}</text>')
        parts.append(f'<rect x="270" y="{y + 9}" width="230" height="18" rx="9" class="bar-bg"/>')
        parts.append(f'<rect x="270" y="{y + 9}" width="{230 * probability / max_champion:.1f}" height="18" rx="9" fill="{colors[index - 1]}"/>')
        parts.append(f'<text x="518" y="{y + 24}" text-anchor="end" class="number">{esc(pct(probability))}</text>')

    parts.append(card(620, 160, 540, 760))
    parts.append(section_title(str(next_round.get("round") or ("下一轮" if lang == "zh" else "Next Round")), 646, 202))
    for index, row in enumerate(matches[:8], start=1):
        y = 222 + (index - 1) * 82
        team1 = row.get("team1")
        team2 = row.get("team2")
        p1 = float(row.get("team1_probability") or 0.0)
        p2 = float(row.get("team2_probability") or 0.0)
        _, favorite_probability = favorite_for_match(row)
        conf_text, conf_class = confidence_label(favorite_probability, lang)
        parts.append(f'<rect x="646" y="{y}" width="488" height="74" rx="8" fill="#fbfcfa" stroke="#e2e6df"/>')
        parts.append(f'<text x="662" y="{y + 22}" class="small">{esc(row.get("date") or "")}</text>')
        parts.append(f'<rect x="1060" y="{y + 9}" width="58" height="24" rx="12" class="{conf_class}"/>')
        parts.append(f'<text x="1089" y="{y + 26}" text-anchor="middle" class="chip-text {conf_class}-text">{esc(conf_text)}</text>')
        parts.append(inline_flag(team1, 662, y + 34, 31, 22, flag_dir, fetch_flags))
        parts.append(f'<text x="702" y="{y + 51}" class="label">{esc(truncate(display_team(team1, lang), 7))}</text>')
        parts.append(f'<text x="798" y="{y + 68}" text-anchor="end" class="number">{esc(pct(p1))}</text>')
        parts.append(f'<rect x="836" y="{y + 56}" width="138" height="12" rx="6" class="bar-bg"/>')
        parts.append(f'<rect x="836" y="{y + 56}" width="{138 * p1:.1f}" height="12" rx="6" class="bar-a"/>')
        parts.append(f'<rect x="{836 + 138 * p1:.1f}" y="{y + 56}" width="{138 * p2:.1f}" height="12" rx="6" class="bar-b"/>')
        parts.append(inline_flag(team2, 994, y + 34, 31, 22, flag_dir, fetch_flags))
        parts.append(f'<text x="1034" y="{y + 51}" class="label">{esc(truncate(display_team(team2, lang), 7))}</text>')
        parts.append(f'<text x="1118" y="{y + 68}" text-anchor="end" class="number">{esc(pct(p2))}</text>')

    parts.append(card(40, 620, 540, 405))
    parts.append(section_title("最可能冠亚季军组合" if lang == "zh" else "Most Likely Podiums", 66, 662))
    for index, row in enumerate(podium_rows[:5], start=1):
        y = 692 + (index - 1) * 62
        teams = [row.get("champion"), row.get("runner_up"), row.get("third")]
        parts.append(f'<rect x="66" y="{y}" width="488" height="48" rx="8" fill="#fbfcfa" stroke="#e2e6df"/>')
        parts.append(f'<text x="84" y="{y + 31}" class="small">{index}</text>')
        x = 112
        for medal_index, team in enumerate(teams, start=1):
            parts.append(inline_flag(team, x, y + 12, 30, 20, flag_dir, fetch_flags))
            parts.append(f'<text x="{x + 38}" y="{y + 29}" class="label">{esc(truncate(display_team(team, lang), 5))}</text>')
            if medal_index < 3:
                parts.append(f'<text x="{x + 106}" y="{y + 29}" class="small">›</text>')
            x += 124
        parts.append(f'<text x="536" y="{y + 31}" text-anchor="end" class="number">{esc(pct(row.get("probability")))}</text>')

    parts.append(card(40, 1050, 540, 315))
    parts.append(section_title("射手榜 Top 5" if lang == "zh" else "Top Scorers", 66, 1092))
    for index, row in enumerate(scorers[:5], start=1):
        y = 1120 + (index - 1) * 45
        team = row.get("team")
        parts.append(f'<text x="66" y="{y + 24}" class="small">{index}</text>')
        parts.append(inline_flag(team, 92, y + 4, 32, 23, flag_dir, fetch_flags))
        parts.append(f'<text x="136" y="{y + 23}" class="label">{esc(truncate(row.get("player"), 22))}</text>')
        parts.append(f'<text x="410" y="{y + 23}" class="small">{esc(display_team(team, lang))}</text>')
        parts.append(f'<text x="536" y="{y + 23}" text-anchor="end" class="number">{esc(row.get("goals", ""))}</text>')

    parts.append(card(620, 950, 540, 415))
    parts.append(section_title("证据栈与风险" if lang == "zh" else "Evidence And Risk", 646, 992))
    top = champion_rows[0] if champion_rows else {}
    clear_count = len([row for row in matches if favorite_for_match(row)[1] >= 0.80])
    tight_count = len([row for row in matches if favorite_for_match(row)[1] < 0.58])
    metrics = [
        ("头号冠军" if lang == "zh" else "Leader", display_team(top.get("team"), lang) if top else "-", pct(top.get("probability") if top else None)),
        ("高置信场次" if lang == "zh" else "High Confidence", str(clear_count), f"/ {len(matches)}"),
        ("接近盘" if lang == "zh" else "Near Flips", str(tight_count), f"/ {len(matches)}"),
    ]
    for index, (name, value, suffix) in enumerate(metrics):
        x = 646 + index * 158
        parts.append(f'<rect x="{x}" y="1022" width="142" height="105" rx="8" fill="#fbfcfa" stroke="#e2e6df"/>')
        parts.append(f'<text x="{x + 14}" y="1052" class="small">{esc(name)}</text>')
        parts.append(f'<text x="{x + 14}" y="1090" class="metric">{esc(value)}</text>')
        parts.append(f'<text x="{x + 14}" y="1115" class="small">{esc(suffix)}</text>')
    source_text = ", ".join(rating_sources) if rating_sources else ("无公开评分" if lang == "zh" else "No public rating source")
    market_text = ", ".join(market_sources) if market_sources else ("未配置" if lang == "zh" else "not configured")
    parts.append(f'<text x="646" y="1172" class="label">{"评分来源" if lang == "zh" else "Rating source"}</text>')
    parts.append(f'<text x="646" y="1198" class="small">{esc(truncate(source_text, 62))}</text>')
    parts.append(f'<text x="646" y="1240" class="label">{"市场信号" if lang == "zh" else "Market signals"}</text>')
    parts.append(f'<text x="646" y="1266" class="small">{esc(truncate(market_text, 62))}</text>')
    parts.append(f'<text x="646" y="1308" class="label">{"数据警告" if lang == "zh" else "Data warnings"}</text>')
    warning_text = f"{len([w for w in warnings if w])} 条" if lang == "zh" else str(len([w for w in warnings if w]))
    parts.append(f'<text x="646" y="1334" class="small">{esc(warning_text)}</text>')

    parts.append(f'<text x="42" y="1510" class="small">flag-icons {FLAG_ICONS_VERSION} · public data + transparent heuristic model · not betting advice</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def build_report(
    report_date: str,
    now: datetime,
    args: argparse.Namespace,
    seed: int,
    dashboard_path: str,
    current: dict[str, object],
    next_round: dict[str, object],
    final: dict[str, object],
) -> str:
    labels = report_labels(args.lang)
    market_line = args.market_signals_file or labels["no_market"]
    return render_report_from_template(
        {
            "title": labels["title"],
            "report_date": report_date,
            "dashboard_alt": labels["dashboard_alt"],
            "dashboard_path": dashboard_path,
            "metadata": render_metadata(labels, now, args, seed, market_line),
            "disclaimer": labels["disclaimer"],
            "key_conclusions_heading": labels["key_conclusions"],
            "key_conclusions": build_conclusions(current, next_round, final, args.lang),
            "details_heading": labels["details"],
            "current_heading": labels["current"],
            "current_section": embed_markdown(forecast.render_current(current, "markdown", args.lang)),
            "next_heading": labels["next"],
            "next_section": embed_markdown(forecast.render_prediction(next_round, "markdown", args.lang)),
            "final_heading": labels["final"],
            "final_section": embed_markdown(forecast.render_prediction(final, "markdown", args.lang)),
        }
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tz = shanghai_tz()
    now = datetime.now(tz)
    report_date = args.date or now.strftime("%Y-%m-%d")
    seed = args.seed if args.seed is not None else int(report_date.replace("-", ""))

    try:
        current, next_round, final = load_daily_data(args, seed)
    except forecast.DataError as exc:
        print(f"generate_daily_report: {exc}", file=sys.stderr)
        return 2

    out_dir = (ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    dated_path = out_dir / f"{report_date}.md"
    latest_arg = Path(args.latest_path)
    latest_path = latest_arg if latest_arg.is_absolute() else ROOT / latest_arg
    latest_path.parent.mkdir(parents=True, exist_ok=True)

    asset_arg = Path(args.asset_dir)
    asset_dir = asset_arg if asset_arg.is_absolute() else ROOT / asset_arg
    asset_dir.mkdir(parents=True, exist_ok=True)
    flag_arg = Path(args.flag_cache_dir)
    flag_dir = flag_arg if flag_arg.is_absolute() else ROOT / flag_arg
    fetch_flags = not args.no_fetch_flags

    dated_dashboard = asset_dir / f"{report_date}-dashboard.svg"
    latest_dashboard = asset_dir / "latest-dashboard.svg"
    dashboard_svg = render_dashboard(report_date, now, args, seed, current, next_round, final, flag_dir, fetch_flags, args.lang)
    dated_dashboard.write_text(dashboard_svg, encoding="utf-8")
    latest_dashboard.write_text(dashboard_svg, encoding="utf-8")

    dated_report = build_report(report_date, now, args, seed, relative_markdown_path(dated_path, dated_dashboard), current, next_round, final)
    latest_report = build_report(report_date, now, args, seed, relative_markdown_path(latest_path, latest_dashboard), current, next_round, final)
    dated_path.write_text(dated_report, encoding="utf-8")
    latest_path.write_text(latest_report, encoding="utf-8")
    print(f"Wrote {dated_path}")
    print(f"Wrote {latest_path}")
    print(f"Wrote {dated_dashboard}")
    print(f"Wrote {latest_dashboard}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
