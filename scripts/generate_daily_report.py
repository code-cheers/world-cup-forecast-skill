#!/usr/bin/env python3
"""Generate a daily World Cup forecast report for GitHub."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
FORECAST_SCRIPT = ROOT / "scripts" / "worldcup_forecast.py"


def shanghai_tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo("Asia/Shanghai")
        except Exception:
            pass
    return timezone(timedelta(hours=8), name="Asia/Shanghai")


def run_forecast(args: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, str(FORECAST_SCRIPT), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"forecast command failed with exit code {result.returncode}")
    return result.stdout.strip()


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
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="Report language.")
    parser.add_argument("--no-elo", action="store_true", help="Disable public Elo ratings enhancement.")
    parser.add_argument("--use-fifa-ranking", action="store_true", help="Fetch optional FIFA rankings.")
    parser.add_argument("--market-signals-file", help="Optional JSON file with odds or prediction-market signals.")
    parser.add_argument("--market-weight", type=float, default=0.35, help="Default market blend weight.")
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
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tz = shanghai_tz()
    now = datetime.now(tz)
    report_date = args.date or now.strftime("%Y-%m-%d")
    seed = args.seed if args.seed is not None else int(report_date.replace("-", ""))

    common = ["--season", str(args.season), "--format", "markdown", "--lang", args.lang]
    if args.no_elo:
        common.append("--no-elo")
    if args.use_fifa_ranking:
        common.append("--use-fifa-ranking")

    market_args: list[str] = []
    if args.market_signals_file:
        market_args.extend(["--market-signals-file", args.market_signals_file])
    market_args.extend(["--market-weight", str(args.market_weight)])

    current = run_forecast(["current", *common])
    next_round = run_forecast(["predict", *common, "--target", "next-round", *market_args])
    final = run_forecast(["predict", *common, "--target", "final", "--runs", str(args.runs), "--seed", str(seed), *market_args])

    labels = report_labels(args.lang)
    market_line = args.market_signals_file or labels["no_market"]
    report = "\n".join(
        [
            f"# {labels['title']} {report_date}",
            "",
            f"{labels['generated']}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} | {labels['season']}: {args.season}",
            f"{labels['runs']}: {args.runs} | {labels['seed']}: {seed} | {labels['market']}: {market_line}",
            "",
            labels["disclaimer"],
            "",
            f"## {labels['current']}",
            embed_markdown(current),
            "",
            f"## {labels['next']}",
            embed_markdown(next_round),
            "",
            f"## {labels['final']}",
            embed_markdown(final),
            "",
        ]
    )

    out_dir = (ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    dated_path = out_dir / f"{report_date}.md"
    latest_arg = Path(args.latest_path)
    latest_path = latest_arg if latest_arg.is_absolute() else ROOT / latest_arg
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    dated_path.write_text(report, encoding="utf-8")
    latest_path.write_text(report, encoding="utf-8")
    print(f"Wrote {dated_path}")
    print(f"Wrote {latest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
