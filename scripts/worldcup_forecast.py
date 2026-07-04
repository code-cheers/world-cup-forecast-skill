#!/usr/bin/env python3
"""Fetch World Cup data and produce transparent heuristic forecasts.

This script intentionally uses only the Python standard library so the skill can
run in a fresh Codex environment without dependency installation.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote_plus
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENFOOTBALL_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/{season}/worldcup.json"
FJELSTUL_BASE_URL = "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv"
ELO_URL = "https://www.international-football.net/elo-ratings-table?year={year}&month={month:02d}&day={day:02d}"
FIFA_TEAM_URL = "https://inside.fifa.com/fifa-world-ranking/{code}?gender=men"
HOST_TEAMS = {"Canada", "Mexico", "United States", "USA"}
TEAM_ALIASES = {
    "USA": "United States",
    "Türkiye": "Turkey",
    "Czech Republic": "Czechoslovakia",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Côte d'Ivoire": "Ivory Coast",
    "DR Congo": "Zaire",
}
TEAM_ZH = {
    "Algeria": "阿尔及利亚",
    "Argentina": "阿根廷",
    "Australia": "澳大利亚",
    "Austria": "奥地利",
    "Belgium": "比利时",
    "Bosnia & Herzegovina": "波黑",
    "Brazil": "巴西",
    "Cameroon": "喀麦隆",
    "Canada": "加拿大",
    "Cape Verde": "佛得角",
    "Chile": "智利",
    "Colombia": "哥伦比亚",
    "Costa Rica": "哥斯达黎加",
    "Croatia": "克罗地亚",
    "Curaçao": "库拉索",
    "Czech Republic": "捷克",
    "Czechoslovakia": "捷克斯洛伐克",
    "Denmark": "丹麦",
    "DR Congo": "刚果民主共和国",
    "Ecuador": "厄瓜多尔",
    "Egypt": "埃及",
    "England": "英格兰",
    "France": "法国",
    "Germany": "德国",
    "Ghana": "加纳",
    "Haiti": "海地",
    "Hungary": "匈牙利",
    "Iran": "伊朗",
    "Iraq": "伊拉克",
    "Italy": "意大利",
    "Ivory Coast": "科特迪瓦",
    "Japan": "日本",
    "Jordan": "约旦",
    "Mexico": "墨西哥",
    "Morocco": "摩洛哥",
    "Netherlands": "荷兰",
    "New Zealand": "新西兰",
    "Nigeria": "尼日利亚",
    "North Korea": "朝鲜",
    "Norway": "挪威",
    "Panama": "巴拿马",
    "Paraguay": "巴拉圭",
    "Peru": "秘鲁",
    "Poland": "波兰",
    "Portugal": "葡萄牙",
    "Qatar": "卡塔尔",
    "Romania": "罗马尼亚",
    "Saudi Arabia": "沙特阿拉伯",
    "Scotland": "苏格兰",
    "Senegal": "塞内加尔",
    "South Africa": "南非",
    "South Korea": "韩国",
    "Soviet Union": "苏联",
    "Spain": "西班牙",
    "Sweden": "瑞典",
    "Switzerland": "瑞士",
    "Tunisia": "突尼斯",
    "Turkey": "土耳其",
    "Türkiye": "土耳其",
    "United States": "美国",
    "Uruguay": "乌拉圭",
    "USA": "美国",
    "Uzbekistan": "乌兹别克斯坦",
    "West Germany": "西德",
    "Yugoslavia": "南斯拉夫",
}
POSITION_POINTS = {1: 8.0, 2: 5.0, 3: 3.0, 4: 2.0}
GROUP_RE = re.compile(r"^([123])([A-L])$")
THIRD_RE = re.compile(r"^3([A-L](?:/[A-L])*)$")
WL_RE = re.compile(r"^([WL])(\d+)$")
TEXT = {
    "en": {
        "year": "Year",
        "position": "Position",
        "team": "Team",
        "code": "Code",
        "current_summary": "{competition} Current Summary",
        "completed_matches": "Completed matches",
        "remaining_matches": "Remaining matches",
        "next_unplayed_round": "Next unplayed round",
        "next_unplayed_date": "Next unplayed date",
        "none": "None",
        "top_scorers": "Top Scorers",
        "player": "Player",
        "goals": "Goals",
        "no_scorers": "No completed-match scorers available.",
        "group_tables": "Group Tables",
        "group": "Group {group}",
        "played": "P",
        "points": "Pts",
        "wins": "W",
        "draws": "D",
        "losses": "L",
        "gf": "GF",
        "ga": "GA",
        "gd": "GD",
        "next_round_forecast": "Next Round Forecast",
        "round": "Round",
        "date": "Date",
        "team1": "Team 1",
        "team2": "Team 2",
        "status": "Status",
        "draw": "Draw",
        "forecast": "forecast",
        "unresolved_placeholder": "unresolved placeholder",
        "no_upcoming_round": "No upcoming round",
        "final_ranking_forecast": "Final Ranking Forecast",
        "runs": "Runs",
        "seed": "Seed",
        "method": "Method",
        "method_text": "Transparent heuristic plus Monte Carlo simulation over remaining fixtures.",
        "champion": "Champion",
        "runner_up": "Runner-up",
        "third": "Third Place",
        "fourth": "Fourth Place",
        "probability": "Probability",
        "item": "Item",
        "value": "Value",
        "rank_type": "Rank",
        "podiums": "Most Likely Podiums",
        "public_ratings": "Public Ratings",
        "elo_rank": "Elo Rank",
        "elo_rating": "Elo",
        "fifa_rank": "FIFA Rank",
        "fifa_points": "FIFA Points",
        "rating_sources": "Rating sources",
        "market_sources": "Market sources",
        "warnings": "Warnings",
        "warning": "Warning",
        "market_signal": "Market signal",
        "model_probability": "Model",
        "market_probability": "Market",
        "blended_probability": "Blended",
    },
    "zh": {
        "year": "年份",
        "position": "排名",
        "team": "球队",
        "code": "代码",
        "current_summary": "{competition} 当前概况",
        "completed_matches": "已完赛场次",
        "remaining_matches": "剩余场次",
        "next_unplayed_round": "下一轮未赛轮次",
        "next_unplayed_date": "下一场未赛日期",
        "none": "无",
        "top_scorers": "射手榜",
        "player": "球员",
        "goals": "进球",
        "no_scorers": "暂无已完赛个人进球数据。",
        "group_tables": "小组积分榜",
        "group": "{group} 组",
        "played": "赛",
        "points": "分",
        "wins": "胜",
        "draws": "平",
        "losses": "负",
        "gf": "进",
        "ga": "失",
        "gd": "净胜",
        "next_round_forecast": "下一轮预测",
        "round": "轮次",
        "date": "日期",
        "team1": "球队 1",
        "team2": "球队 2",
        "status": "状态",
        "draw": "平局",
        "forecast": "预测",
        "unresolved_placeholder": "占位未解析",
        "no_upcoming_round": "暂无未赛轮次",
        "final_ranking_forecast": "最终排名预测",
        "runs": "模拟次数",
        "seed": "随机种子",
        "method": "方法",
        "method_text": "透明启发式评分加剩余赛程蒙特卡洛模拟。",
        "champion": "冠军",
        "runner_up": "亚军",
        "third": "第三名",
        "fourth": "第四名",
        "probability": "概率",
        "item": "项目",
        "value": "数值",
        "rank_type": "排名类型",
        "podiums": "最可能冠亚季军组合",
        "public_ratings": "公开评分",
        "elo_rank": "Elo 排名",
        "elo_rating": "Elo",
        "fifa_rank": "FIFA 排名",
        "fifa_points": "FIFA 积分",
        "rating_sources": "评分来源",
        "market_sources": "市场来源",
        "warnings": "警告",
        "warning": "警告",
        "market_signal": "市场信号",
        "model_probability": "模型",
        "market_probability": "市场",
        "blended_probability": "融合",
    },
}


class DataError(RuntimeError):
    """Raised when a remote data source cannot be fetched or parsed."""


@dataclass
class PublicRatings:
    elo: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    fifa: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class MarketSignals:
    matches: List[Dict[str, Any]] = field(default_factory=list)
    futures: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class TeamRecord:
    team: str
    group: str = ""
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    gf: int = 0
    ga: int = 0
    points: int = 0
    recent: List[int] = field(default_factory=list)

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    def copy(self) -> "TeamRecord":
        return TeamRecord(
            self.team,
            self.group,
            self.played,
            self.wins,
            self.draws,
            self.losses,
            self.gf,
            self.ga,
            self.points,
            list(self.recent),
        )


def fetch_text(url: str, timeout: int = 20) -> str:
    request = Request(url, headers={"User-Agent": "world-cup-forecast-skill/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise DataError(f"HTTP {exc.code} while fetching {url}") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise DataError(f"Network error while fetching {url}: {reason}") from exc
    except TimeoutError as exc:
        raise DataError(f"Timed out while fetching {url}") from exc


def fetch_json(url: str) -> Dict[str, Any]:
    try:
        return json.loads(fetch_text(url))
    except json.JSONDecodeError as exc:
        raise DataError(f"Invalid JSON from {url}: {exc}") from exc


def fetch_csv(url: str) -> List[Dict[str, str]]:
    text = fetch_text(url)
    try:
        return list(csv.DictReader(io.StringIO(text)))
    except csv.Error as exc:
        raise DataError(f"Invalid CSV from {url}: {exc}") from exc


def season_url(season: int, override: Optional[str]) -> str:
    template = override or os.getenv("OPENFOOTBALL_WORLDCUP_URL_TEMPLATE") or OPENFOOTBALL_URL
    return template.format(season=season)


def fjelstul_url(name: str, base_override: Optional[str]) -> str:
    base = base_override or os.getenv("FJELSTUL_WORLDCUP_BASE_URL") or FJELSTUL_BASE_URL
    return f"{base.rstrip('/')}/{name}.csv"


def dated_elo_url(override: Optional[str]) -> str:
    if override:
        return override
    template = os.getenv("WORLD_FOOTBALL_ELO_URL") or ELO_URL
    today = date.today()
    return template.format(year=today.year, month=today.month, day=today.day)


def fifa_team_url(code: str, override: Optional[str]) -> str:
    template = override or os.getenv("FIFA_RANKING_TEAM_URL_TEMPLATE") or FIFA_TEAM_URL
    return template.format(code=code)


def normalize_team_name(name: str) -> str:
    aliases = {
        "usa": "united states",
        "czechia": "czech republic",
        "cabo verde": "cape verde",
        "ivory coast": "cote d'ivoire",
        "côte d'ivoire": "cote d'ivoire",
        "bosnia & herzegovina": "bosnia and herzegovina",
        "dr congo": "zaire",
        "democratic republic of the congo": "zaire",
        "turkiye": "turkey",
        "türkiye": "turkey",
    }
    clean = html.unescape(name).strip().lower()
    clean = clean.replace("’", "'").replace("`", "'")
    clean = re.sub(r"\s+", " ", clean)
    return aliases.get(clean, clean)


def lookup_team(mapping: Dict[str, Any], team: str) -> Optional[Any]:
    for candidate in (team, TEAM_ALIASES.get(team, "")):
        if candidate and candidate in mapping:
            return mapping[candidate]
        normalized = normalize_team_name(candidate)
        for key, value in mapping.items():
            if normalize_team_name(key) == normalized:
                return value
    return None


def extract_next_data(text: str, url: str) -> Dict[str, Any]:
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text)
    if not match:
        raise DataError(f"Could not find Next.js data in {url}")
    try:
        return json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        raise DataError(f"Invalid embedded JSON from {url}: {exc}") from exc


def load_team_codes(base_url: Optional[str]) -> Dict[str, str]:
    rows = fetch_csv(fjelstul_url("teams", base_url))
    codes = {row["team_name"]: row["team_code"] for row in rows if row.get("team_name") and row.get("team_code")}
    codes.update(
        {
            "USA": "USA",
            "United States": "USA",
            "Cape Verde": "CPV",
            "Curaçao": "CUW",
            "Curacao": "CUW",
            "Ivory Coast": "CIV",
            "Côte d'Ivoire": "CIV",
            "Turkey": "TUR",
            "Czech Republic": "CZE",
            "DR Congo": "COD",
            "Bosnia & Herzegovina": "BIH",
        }
    )
    return codes


def load_elo_ratings(url_override: Optional[str]) -> Dict[str, Dict[str, Any]]:
    url = dated_elo_url(url_override)
    text = fetch_text(url)
    pattern = re.compile(
        r"<tr[^>]+class=\"survol\"[^>]*?team=([^&']+).*?"
        r"<strong>(\d+)</strong>.*?"
        r"<td>([^<]+)</td><td[^>]*>(\d+)</td>",
        re.DOTALL,
    )
    ratings: Dict[str, Dict[str, Any]] = {}
    for match in pattern.finditer(text):
        team = html.unescape(unquote_plus(match.group(1))).strip()
        row_team = html.unescape(match.group(3)).strip()
        if row_team:
            team = row_team
        ratings[team] = {"team": team, "rank": int(match.group(2)), "rating": int(match.group(4)), "source": url}
    if not ratings:
        raise DataError(f"No Elo ratings parsed from {url}")
    return ratings


def load_fifa_rating_for_code(code: str, url_override: Optional[str]) -> Optional[Dict[str, Any]]:
    url = fifa_team_url(code, url_override)
    data = extract_next_data(fetch_text(url), url)
    try:
        rows = data["props"]["pageProps"]["pageData"]["ranking"]["rankings"]["menRanking"]["rows"]
    except (KeyError, TypeError) as exc:
        raise DataError(f"Could not find FIFA ranking rows in {url}") from exc
    for row in rows:
        if row.get("countryCode") == code or row.get("active"):
            return {
                "team": row.get("name", code),
                "code": row.get("countryCode", code),
                "rank": row.get("rank"),
                "points": row.get("totalPoints"),
                "previous_rank": row.get("previousRank"),
                "previous_points": row.get("previousPoints"),
                "last_update": row.get("lastUpdateDate"),
                "source": url,
            }
    return None


def load_public_ratings(
    teams: Iterable[str],
    base_url: Optional[str],
    elo_url_override: Optional[str],
    fifa_url_override: Optional[str],
    use_elo: bool,
    use_fifa: bool,
) -> PublicRatings:
    ratings = PublicRatings()
    if use_elo:
        try:
            ratings.elo = load_elo_ratings(elo_url_override)
            ratings.sources.append("World Football Elo Ratings")
        except DataError as exc:
            ratings.warnings.append(str(exc))
    if use_fifa:
        try:
            codes = load_team_codes(base_url)
            for team in sorted(set(teams)):
                code = lookup_team(codes, team)
                if not code:
                    ratings.warnings.append(f"No FIFA country code found for {team}")
                    continue
                try:
                    row = load_fifa_rating_for_code(str(code), fifa_url_override)
                except DataError as exc:
                    ratings.warnings.append(str(exc))
                    continue
                if row:
                    ratings.fifa[team] = row
            if ratings.fifa:
                ratings.sources.append("FIFA/Coca-Cola Men's World Ranking")
        except DataError as exc:
            ratings.warnings.append(str(exc))
    return ratings


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def market_team_key(team: Any) -> str:
    if team is None:
        return ""
    name = str(team)
    canonical = TEAM_ALIASES.get(name, name)
    return normalize_team_name(canonical)


def load_market_signals(path: Optional[str]) -> MarketSignals:
    if not path:
        return MarketSignals()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        raise DataError(f"Could not read market signals file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DataError(f"Invalid market signals JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise DataError(f"Market signals file {path} must contain a JSON object")
    matches = raw.get("matches") or []
    futures = raw.get("futures") or []
    if not isinstance(matches, list) or not isinstance(futures, list):
        raise DataError(f"Market signals file {path} must use list values for matches and futures")
    sources = raw.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    warnings = raw.get("warnings") or []
    if isinstance(warnings, str):
        warnings = [warnings]
    return MarketSignals(matches=matches, futures=futures, sources=list(sources), warnings=list(warnings))


def row_market_weight(row: Dict[str, Any], default_weight: float) -> float:
    try:
        weight = float(row.get("weight", default_weight))
    except (TypeError, ValueError):
        weight = default_weight
    for key, threshold, factor in (("volume", 1000.0, 0.65), ("liquidity", 500.0, 0.75)):
        try:
            value = float(row.get(key, threshold))
        except (TypeError, ValueError):
            value = threshold
        if value < threshold:
            weight *= factor
    try:
        spread = float(row.get("spread", 0.0))
    except (TypeError, ValueError):
        spread = 0.0
    if spread > 0.15:
        weight *= 0.50
    elif spread > 0.08:
        weight *= 0.75
    return clamp(weight, 0.0, 0.65)


def market_match_probabilities(row: Dict[str, Any], team1: str, team2: str) -> Optional[Dict[str, float]]:
    probabilities_by_team = row.get("probabilities")
    if isinstance(probabilities_by_team, dict):
        lookup = {market_team_key(team): value for team, value in probabilities_by_team.items()}
        if market_team_key(team1) in lookup and market_team_key(team2) in lookup:
            try:
                p1 = float(lookup[market_team_key(team1)])
                p2 = float(lookup[market_team_key(team2)])
                draw = float(lookup.get("draw", row.get("draw_probability", 0.0)) or 0.0)
            except (TypeError, ValueError):
                return None
            total = p1 + p2 + draw
            if total <= 0:
                return None
            return {"team1": p1 / total, "draw": draw / total, "team2": p2 / total}

    row_team1 = row.get("team1")
    row_team2 = row.get("team2")
    if not row_team1 or not row_team2:
        return None
    direct = market_team_key(row_team1) == market_team_key(team1) and market_team_key(row_team2) == market_team_key(team2)
    reverse = market_team_key(row_team1) == market_team_key(team2) and market_team_key(row_team2) == market_team_key(team1)
    if not direct and not reverse:
        return None
    try:
        p1 = float(row.get("team1_probability"))
        p2 = float(row.get("team2_probability"))
        draw = float(row.get("draw_probability", 0.0) or 0.0)
    except (TypeError, ValueError):
        return None
    if reverse:
        p1, p2 = p2, p1
    total = p1 + p2 + draw
    if total <= 0:
        return None
    return {"team1": p1 / total, "draw": draw / total, "team2": p2 / total}


def find_market_match(signals: MarketSignals, team1: str, team2: str, default_weight: float) -> Optional[Dict[str, Any]]:
    for row in signals.matches:
        if not isinstance(row, dict):
            continue
        probabilities_row = market_match_probabilities(row, team1, team2)
        if not probabilities_row:
            continue
        return {
            "probabilities": probabilities_row,
            "weight": row_market_weight(row, default_weight),
            "source": row.get("source") or row.get("market") or "market",
            "updated_at": row.get("updated_at"),
        }
    return None


def blend_probabilities(model: Dict[str, float], market: Dict[str, float], weight: float) -> Dict[str, float]:
    blended = {key: (1.0 - weight) * model.get(key, 0.0) + weight * market.get(key, 0.0) for key in ("team1", "draw", "team2")}
    total = sum(blended.values())
    if total <= 0:
        return model
    return {key: blended[key] / total for key in blended}


def champion_market_probabilities(signals: MarketSignals, default_weight: float) -> Tuple[Dict[str, float], float, List[str]]:
    rows = [row for row in signals.futures if isinstance(row, dict) and row.get("rank_type", "champion") == "champion"]
    if not rows:
        return {}, 0.0, []
    raw: Dict[str, float] = {}
    weights = []
    warnings = []
    for row in rows:
        team = row.get("team")
        if not team:
            continue
        try:
            probability = float(row.get("champion_probability", row.get("probability")))
        except (TypeError, ValueError):
            warnings.append(f"Invalid champion probability for {team}")
            continue
        if probability > 0:
            raw[str(team)] = probability
            weights.append(row_market_weight(row, default_weight))
    total = sum(raw.values())
    if total <= 0:
        return {}, 0.0, warnings
    if total < 0.50:
        warnings.append("Champion futures cover less than 50% total probability; skipping futures blend.")
        return {}, 0.0, warnings
    if total < 0.95:
        warnings.append("Champion futures do not cover the full field; teams missing from futures receive zero market probability.")
    normalized = {team: probability / total for team, probability in raw.items()}
    weight = sum(weights) / len(weights) if weights else default_weight
    return normalized, clamp(weight, 0.0, 0.65), warnings


def tournament_year(row: Dict[str, str]) -> Optional[int]:
    tournament_id = row.get("tournament_id", "")
    match = re.search(r"WC-(\d{4})", tournament_id)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d{4})", row.get("tournament_name", ""))
    return int(match.group(1)) if match else None


def is_mens_tournament(row: Dict[str, str]) -> bool:
    return "FIFA Men's World Cup" in row.get("tournament_name", "")


def load_historical_strength(base_url: Optional[str], current_year: int) -> Tuple[Dict[str, float], List[Dict[str, str]]]:
    rows = fetch_csv(fjelstul_url("tournament_standings", base_url))
    strength: Dict[str, float] = defaultdict(float)
    for row in rows:
        if not is_mens_tournament(row):
            continue
        year = tournament_year(row)
        if year is None:
            continue
        try:
            position = int(row["position"])
        except (KeyError, ValueError):
            continue
        weight = POSITION_POINTS.get(position, 0.0)
        if not weight:
            continue
        recency = max(0.25, 1.0 - max(0, current_year - year) / 100.0)
        strength[row["team_name"]] += weight * recency
    return dict(strength), rows


def completed_score(match: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    score = match.get("score")
    if not isinstance(score, dict):
        return None
    ft = score.get("ft")
    if not isinstance(ft, list) or len(ft) != 2:
        return None
    if ft[0] is None or ft[1] is None:
        return None
    return int(ft[0]), int(ft[1])


def group_letter(match: Dict[str, Any]) -> str:
    group = match.get("group") or ""
    return group.replace("Group ", "").strip()


def is_group_match(match: Dict[str, Any]) -> bool:
    return bool(match.get("group")) and str(match.get("round", "")).startswith("Matchday")


def apply_result(records: Dict[str, TeamRecord], team_a: str, team_b: str, group: str, goals_a: int, goals_b: int) -> None:
    for team in (team_a, team_b):
        records.setdefault(team, TeamRecord(team=team, group=group))
        if group and not records[team].group:
            records[team].group = group
    a = records[team_a]
    b = records[team_b]
    a.played += 1
    b.played += 1
    a.gf += goals_a
    a.ga += goals_b
    b.gf += goals_b
    b.ga += goals_a
    if goals_a > goals_b:
        a.wins += 1
        b.losses += 1
        a.points += 3
        a.recent.append(3)
        b.recent.append(0)
    elif goals_a < goals_b:
        b.wins += 1
        a.losses += 1
        b.points += 3
        b.recent.append(3)
        a.recent.append(0)
    else:
        a.draws += 1
        b.draws += 1
        a.points += 1
        b.points += 1
        a.recent.append(1)
        b.recent.append(1)


def build_current_records(matches: List[Dict[str, Any]]) -> Dict[str, TeamRecord]:
    records: Dict[str, TeamRecord] = {}
    for match in matches:
        if not is_group_match(match):
            continue
        team1 = match.get("team1")
        team2 = match.get("team2")
        group = group_letter(match)
        if not team1 or not team2:
            continue
        records.setdefault(team1, TeamRecord(team=team1, group=group))
        records.setdefault(team2, TeamRecord(team=team2, group=group))
        score = completed_score(match)
        if score:
            apply_result(records, team1, team2, group, score[0], score[1])
    return records


def top_scorers(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    totals: Counter[Tuple[str, str]] = Counter()
    for match in matches:
        if not completed_score(match):
            continue
        team1 = match.get("team1", "")
        team2 = match.get("team2", "")
        for goal in match.get("goals1") or []:
            if goal.get("owngoal"):
                continue
            name = goal.get("name")
            if name:
                totals[(name, team1)] += 1
        for goal in match.get("goals2") or []:
            if goal.get("owngoal"):
                continue
            name = goal.get("name")
            if name:
                totals[(name, team2)] += 1
    return [
        {"player": player, "team": team, "goals": goals}
        for (player, team), goals in sorted(totals.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    ]


def scorer_team_boost(matches: List[Dict[str, Any]]) -> Dict[str, float]:
    boost: Dict[str, float] = defaultdict(float)
    for row in top_scorers(matches):
        boost[row["team"]] += min(1.0, row["goals"] * 0.25)
    return dict(boost)


def public_rating_adjustment(team: str, public_ratings: Optional[PublicRatings]) -> float:
    if not public_ratings:
        return 0.0
    adjustment = 0.0
    elo = lookup_team(public_ratings.elo, team)
    if elo and elo.get("rating") is not None:
        adjustment += max(-8.0, min(10.0, (float(elo["rating"]) - 1650.0) / 45.0))
    fifa = lookup_team(public_ratings.fifa, team)
    if fifa:
        if fifa.get("points") is not None:
            adjustment += max(-5.0, min(7.0, (float(fifa["points"]) - 1350.0) / 85.0))
        elif fifa.get("rank") is not None:
            adjustment += max(0.0, (80.0 - float(fifa["rank"])) / 10.0)
    return adjustment


def team_rating(team: str, records: Dict[str, TeamRecord], historical: Dict[str, float], scorer_boost: Dict[str, float], public_ratings: Optional[PublicRatings] = None) -> float:
    record = records.get(team, TeamRecord(team=team))
    sample_weight = min(1.0, record.played / 3.0)
    ppg = record.points / record.played if record.played else 1.0
    gdpg = record.gd / record.played if record.played else 0.0
    gfpg = record.gf / record.played if record.played else 1.0
    recent = sum(record.recent[-3:]) / max(1, len(record.recent[-3:]))
    historical_value = max(historical.get(team, 0.0), historical.get(TEAM_ALIASES.get(team, ""), 0.0))
    rating = 50.0
    rating += min(18.0, historical_value * 0.55)
    rating += (ppg - 1.0) * 5.0 * sample_weight
    rating += gdpg * 2.0 * sample_weight
    rating += (gfpg - 1.0) * 1.0 * sample_weight
    rating += (recent - 1.0) * 1.5 * sample_weight
    rating += scorer_boost.get(team, 0.0) * sample_weight
    rating += public_rating_adjustment(team, public_ratings)
    if team in HOST_TEAMS:
        rating += 0.5
    return rating


def probabilities(team_a: str, team_b: str, records: Dict[str, TeamRecord], historical: Dict[str, float], scorer_boost: Dict[str, float], allow_draw: bool, public_ratings: Optional[PublicRatings] = None) -> Dict[str, float]:
    delta = team_rating(team_a, records, historical, scorer_boost, public_ratings) - team_rating(team_b, records, historical, scorer_boost, public_ratings)
    p_a_no_draw = 1.0 / (1.0 + math.exp(-delta / 12.0))
    if not allow_draw:
        return {"team1": p_a_no_draw, "draw": 0.0, "team2": 1.0 - p_a_no_draw}
    draw = max(0.14, min(0.30, 0.26 - abs(delta) * 0.004))
    return {
        "team1": (1.0 - draw) * p_a_no_draw,
        "draw": draw,
        "team2": (1.0 - draw) * (1.0 - p_a_no_draw),
    }


def weighted_choice(rng: random.Random, choices: List[Tuple[Any, float]]) -> Any:
    total = sum(weight for _, weight in choices)
    pick = rng.random() * total
    running = 0.0
    for value, weight in choices:
        running += weight
        if pick <= running:
            return value
    return choices[-1][0]


def simulate_score(rng: random.Random, team_a: str, team_b: str, records: Dict[str, TeamRecord], historical: Dict[str, float], scorer_boost: Dict[str, float], allow_draw: bool, public_ratings: Optional[PublicRatings] = None) -> Tuple[int, int]:
    probs = probabilities(team_a, team_b, records, historical, scorer_boost, allow_draw, public_ratings)
    outcome = weighted_choice(rng, [("a", probs["team1"]), ("d", probs["draw"]), ("b", probs["team2"])])
    if outcome == "d":
        goals = weighted_choice(rng, [(0, 0.22), (1, 0.54), (2, 0.20), (3, 0.04)])
        return goals, goals
    winner_goals = weighted_choice(rng, [(1, 0.36), (2, 0.42), (3, 0.17), (4, 0.05)])
    loser_goals = weighted_choice(rng, [(0, 0.45), (1, 0.40), (2, 0.15)])
    if loser_goals >= winner_goals:
        winner_goals = loser_goals + 1
    return (winner_goals, loser_goals) if outcome == "a" else (loser_goals, winner_goals)


def sorted_group(records: Dict[str, TeamRecord], group: str, historical: Dict[str, float], scorer_boost: Dict[str, float], public_ratings: Optional[PublicRatings] = None) -> List[TeamRecord]:
    teams = [record for record in records.values() if record.group == group]
    return sorted(
        teams,
        key=lambda r: (r.points, r.gd, r.gf, team_rating(r.team, records, historical, scorer_boost, public_ratings), r.team),
        reverse=True,
    )


def all_groups(records: Dict[str, TeamRecord]) -> List[str]:
    return sorted({record.group for record in records.values() if record.group})


def simulate_group_stage(rng: random.Random, matches: List[Dict[str, Any]], base_records: Dict[str, TeamRecord], historical: Dict[str, float], scorer_boost: Dict[str, float], public_ratings: Optional[PublicRatings]) -> Dict[str, TeamRecord]:
    records = {team: record.copy() for team, record in base_records.items()}
    for match in matches:
        if not is_group_match(match) or completed_score(match):
            continue
        team1 = match.get("team1")
        team2 = match.get("team2")
        if not team1 or not team2:
            continue
        score = simulate_score(rng, team1, team2, records, historical, scorer_boost, allow_draw=True, public_ratings=public_ratings)
        apply_result(records, team1, team2, group_letter(match), score[0], score[1])
    return records


def group_rank_maps(records: Dict[str, TeamRecord], historical: Dict[str, float], scorer_boost: Dict[str, float], public_ratings: Optional[PublicRatings] = None) -> Tuple[Dict[str, Dict[int, str]], Dict[str, str]]:
    ranks: Dict[str, Dict[int, str]] = {}
    third: Dict[str, str] = {}
    for group in all_groups(records):
        ordered = sorted_group(records, group, historical, scorer_boost, public_ratings)
        ranks[group] = {idx + 1: row.team for idx, row in enumerate(ordered)}
        if len(ordered) >= 3:
            third[group] = ordered[2].team
    return ranks, third


def best_thirds(records: Dict[str, TeamRecord], historical: Dict[str, float], scorer_boost: Dict[str, float], public_ratings: Optional[PublicRatings] = None) -> Dict[str, str]:
    rows: List[TeamRecord] = []
    for group in all_groups(records):
        ordered = sorted_group(records, group, historical, scorer_boost, public_ratings)
        if len(ordered) >= 3:
            rows.append(ordered[2])
    rows.sort(key=lambda r: (r.points, r.gd, r.gf, team_rating(r.team, records, historical, scorer_boost, public_ratings), r.team), reverse=True)
    return {row.group: row.team for row in rows[:8]}


def third_slot_groups(slot: str) -> List[str]:
    match = THIRD_RE.match(slot)
    return match.group(1).split("/") if match else []


def assign_third_slots(matches: List[Dict[str, Any]], advanced_thirds: Dict[str, str]) -> Dict[str, str]:
    slots: List[str] = []
    for match in matches:
        if match.get("round") != "Round of 32":
            continue
        for side in (match.get("team1", ""), match.get("team2", "")):
            if THIRD_RE.match(str(side)):
                slots.append(str(side))
    unique_slots = list(dict.fromkeys(slots))
    groups = set(advanced_thirds)
    candidates = {slot: [group for group in third_slot_groups(slot) if group in groups] for slot in unique_slots}
    ordered_slots = sorted(unique_slots, key=lambda slot: len(candidates[slot]))

    def search(index: int, used: set[str], assignment: Dict[str, str]) -> Optional[Dict[str, str]]:
        if index == len(ordered_slots):
            return dict(assignment)
        slot = ordered_slots[index]
        for group in candidates[slot]:
            if group in used:
                continue
            assignment[slot] = advanced_thirds[group]
            found = search(index + 1, used | {group}, assignment)
            if found:
                return found
        assignment.pop(slot, None)
        return None

    found = search(0, set(), {})
    if found:
        return found

    assignment = {}
    used = set()
    for slot in ordered_slots:
        for group in candidates[slot]:
            if group not in used:
                assignment[slot] = advanced_thirds[group]
                used.add(group)
                break
    return assignment


def resolve_side(side: str, ranks: Dict[str, Dict[int, str]], third_assignment: Dict[str, str], previous: Dict[int, Dict[str, str]]) -> Optional[str]:
    side = str(side)
    match = GROUP_RE.match(side)
    if match:
        return ranks.get(match.group(2), {}).get(int(match.group(1)))
    if THIRD_RE.match(side):
        return third_assignment.get(side)
    match = WL_RE.match(side)
    if match:
        result = previous.get(int(match.group(2)))
        if not result:
            return None
        return result["winner"] if match.group(1) == "W" else result["loser"]
    if side and not any(char.isdigit() for char in side):
        return side
    return None


def simulate_knockouts(rng: random.Random, matches: List[Dict[str, Any]], records: Dict[str, TeamRecord], historical: Dict[str, float], scorer_boost: Dict[str, float], public_ratings: Optional[PublicRatings]) -> Dict[str, str]:
    ranks, _ = group_rank_maps(records, historical, scorer_boost, public_ratings)
    third_assignment = assign_third_slots(matches, best_thirds(records, historical, scorer_boost, public_ratings))
    previous: Dict[int, Dict[str, str]] = {}
    final_result: Dict[str, str] = {}
    for index, match in enumerate(matches, start=1):
        if is_group_match(match):
            continue
        team1 = resolve_side(match.get("team1", ""), ranks, third_assignment, previous)
        team2 = resolve_side(match.get("team2", ""), ranks, third_assignment, previous)
        if not team1 or not team2:
            continue
        score = completed_score(match)
        if score:
            winner, loser = (team1, team2) if score[0] >= score[1] else (team2, team1)
        else:
            goals1, goals2 = simulate_score(rng, team1, team2, records, historical, scorer_boost, allow_draw=False, public_ratings=public_ratings)
            winner, loser = (team1, team2) if goals1 > goals2 else (team2, team1)
        previous[index] = {"winner": winner, "loser": loser}
        if match.get("round") == "Final":
            final_result["champion"] = winner
            final_result["runner_up"] = loser
        elif match.get("round") == "Match for third place":
            final_result["third"] = winner
            final_result["fourth"] = loser
    return final_result


def historical_rows(rows: List[Dict[str, str]], since: int, positions: int) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        if not is_mens_tournament(row):
            continue
        year = tournament_year(row)
        if year is None or year < since:
            continue
        try:
            position = int(row["position"])
        except (KeyError, ValueError):
            continue
        if position <= positions:
            out.append(
                {
                    "year": year,
                    "position": position,
                    "team": row.get("team_name", ""),
                    "code": row.get("team_code", ""),
                    "tournament": row.get("tournament_name", ""),
                }
            )
    return sorted(out, key=lambda row: (row["year"], row["position"]))


def markdown_table(headers: List[str], rows: Iterable[Iterable[Any]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header, divider] + body)


def display_team(team: Any, lang: str) -> str:
    name = "" if team is None else str(team)
    if lang != "zh":
        return name
    return TEAM_ZH.get(name, name)


def render_history(rows: List[Dict[str, Any]], fmt: str, lang: str) -> str:
    if fmt == "json":
        return json.dumps({"historical_rankings": rows}, ensure_ascii=False, indent=2)
    t = TEXT[lang]
    return markdown_table([t["year"], t["position"], t["team"], t["code"]], ((r["year"], r["position"], display_team(r["team"], lang), r["code"]) for r in rows))


def render_warnings(warnings: Iterable[str], lang: str) -> str:
    rows = [(index, warning) for index, warning in enumerate(warnings, start=1) if warning]
    if not rows:
        return ""
    t = TEXT[lang]
    return f"## {t['warnings']}\n" + markdown_table(["#", t["warning"]], rows)


def team_names_from_matches(matches: List[Dict[str, Any]]) -> List[str]:
    teams = set()
    for match in matches:
        for side in (match.get("team1"), match.get("team2")):
            if side and not GROUP_RE.match(str(side)) and not THIRD_RE.match(str(side)) and not WL_RE.match(str(side)):
                teams.add(str(side))
    return sorted(teams)


def rating_rows_for_teams(teams: Iterable[str], public_ratings: Optional[PublicRatings]) -> List[Dict[str, Any]]:
    rows = []
    if not public_ratings:
        return rows
    for team in teams:
        elo = lookup_team(public_ratings.elo, team) or {}
        fifa = lookup_team(public_ratings.fifa, team) or {}
        if not elo and not fifa:
            continue
        rows.append(
            {
                "team": team,
                "elo_rank": elo.get("rank"),
                "elo_rating": elo.get("rating"),
                "fifa_rank": fifa.get("rank"),
                "fifa_points": fifa.get("points"),
            }
        )
    return sorted(rows, key=lambda row: (row["elo_rank"] is None, row["elo_rank"] or 9999, row["team"]))


def current_summary(data: Dict[str, Any], season: int, public_ratings: Optional[PublicRatings] = None) -> Dict[str, Any]:
    matches = data.get("matches", [])
    records = build_current_records(matches)
    completed = [m for m in matches if completed_score(m)]
    upcoming = [m for m in matches if not completed_score(m)]
    groups = {}
    for group in all_groups(records):
        groups[group] = [
            {
                "team": row.team,
                "played": row.played,
                "points": row.points,
                "wins": row.wins,
                "draws": row.draws,
                "losses": row.losses,
                "gf": row.gf,
                "ga": row.ga,
                "gd": row.gd,
            }
            for row in sorted_group(records, group, {}, {})
        ]
    return {
        "season": season,
        "competition": data.get("name", f"World Cup {season}"),
        "completed_matches": len(completed),
        "remaining_matches": len(upcoming),
        "top_scorers": top_scorers(matches)[:20],
        "groups": groups,
        "public_ratings": rating_rows_for_teams(team_names_from_matches(matches), public_ratings),
        "rating_sources": public_ratings.sources if public_ratings else [],
        "rating_warnings": public_ratings.warnings if public_ratings else [],
        "next_unplayed_round": upcoming[0].get("round") if upcoming else None,
        "next_unplayed_date": upcoming[0].get("date") if upcoming else None,
    }


def render_current(summary: Dict[str, Any], fmt: str, lang: str) -> str:
    if fmt == "json":
        return json.dumps(summary, ensure_ascii=False, indent=2)
    t = TEXT[lang]
    lines = [
        f"# {t['current_summary'].format(competition=summary['competition'])}",
        "",
        markdown_table(
            [t["item"], t["value"]],
            [
                (t["completed_matches"], summary["completed_matches"]),
                (t["remaining_matches"], summary["remaining_matches"]),
                (t["next_unplayed_round"], summary.get("next_unplayed_round") or t["none"]),
                (t["next_unplayed_date"], summary.get("next_unplayed_date") or t["none"]),
            ],
        ),
        "",
        f"## {t['top_scorers']}",
    ]
    scorers = summary["top_scorers"]
    lines.append(markdown_table([t["player"], t["team"], t["goals"]], ((s["player"], display_team(s["team"], lang), s["goals"]) for s in scorers)) if scorers else t["no_scorers"])
    lines.append("")
    lines.append(f"## {t['group_tables']}")
    for group, rows in summary["groups"].items():
        lines.append(f"### {t['group'].format(group=group)}")
        lines.append(markdown_table([t["team"], t["played"], t["points"], t["wins"], t["draws"], t["losses"], t["gf"], t["ga"], t["gd"]], ((display_team(r["team"], lang), r["played"], r["points"], r["wins"], r["draws"], r["losses"], r["gf"], r["ga"], r["gd"]) for r in rows)))
        lines.append("")
    if summary.get("public_ratings"):
        lines.append(f"## {t['public_ratings']}")
        lines.append(
            markdown_table(
                [t["team"], t["elo_rank"], t["elo_rating"], t["fifa_rank"], t["fifa_points"]],
                (
                    (
                        row["team"],
                        row.get("elo_rank") or "",
                        row.get("elo_rating") or "",
                        row.get("fifa_rank") or "",
                        row.get("fifa_points") or "",
                    )
                    for row in summary["public_ratings"]
                ),
            )
        )
        lines.append("")
    if summary.get("rating_sources"):
        lines.append(markdown_table([t["item"], t["value"]], [(t["rating_sources"], ", ".join(summary["rating_sources"]))]))
        lines.append("")
    warnings = render_warnings(summary.get("rating_warnings", []), lang)
    if warnings:
        lines.append(warnings)
        lines.append("")
    return "\n".join(lines).rstrip()


def next_round_predictions(
    data: Dict[str, Any],
    season: int,
    historical: Dict[str, float],
    public_ratings: Optional[PublicRatings],
    market_signals: Optional[MarketSignals] = None,
    market_weight: float = 0.35,
) -> Dict[str, Any]:
    matches = data.get("matches", [])
    records = build_current_records(matches)
    scorers = scorer_team_boost(matches)
    market_signals = market_signals or MarketSignals()
    upcoming = [m for m in matches if not completed_score(m)]
    round_name = upcoming[0].get("round") if upcoming else None
    round_matches = [m for m in upcoming if m.get("round") == round_name]
    predictions = []
    for match in round_matches:
        team1 = match.get("team1")
        team2 = match.get("team2")
        unresolved = not team1 or not team2 or bool(WL_RE.match(str(team1))) or bool(WL_RE.match(str(team2))) or bool(THIRD_RE.match(str(team1))) or bool(THIRD_RE.match(str(team2)))
        if unresolved:
            predictions.append({"date": match.get("date"), "round": match.get("round"), "team1": team1, "team2": team2, "status": "unresolved placeholder"})
            continue
        model_probs = probabilities(team1, team2, records, historical, scorers, allow_draw=is_group_match(match), public_ratings=public_ratings)
        market = find_market_match(market_signals, str(team1), str(team2), market_weight)
        probs = blend_probabilities(model_probs, market["probabilities"], market["weight"]) if market else model_probs
        predictions.append(
            {
                "date": match.get("date"),
                "round": match.get("round"),
                "team1": team1,
                "team2": team2,
                "team1_probability": round(probs["team1"], 3),
                "draw_probability": round(probs["draw"], 3),
                "team2_probability": round(probs["team2"], 3),
                "model_team1_probability": round(model_probs["team1"], 3),
                "model_draw_probability": round(model_probs["draw"], 3),
                "model_team2_probability": round(model_probs["team2"], 3),
                "market_team1_probability": round(market["probabilities"]["team1"], 3) if market else None,
                "market_draw_probability": round(market["probabilities"]["draw"], 3) if market else None,
                "market_team2_probability": round(market["probabilities"]["team2"], 3) if market else None,
                "market_weight": round(market["weight"], 3) if market else 0.0,
                "market_source": market["source"] if market else None,
                "market_updated_at": market.get("updated_at") if market else None,
                "status": "forecast",
            }
        )
    return {
        "season": season,
        "target": "next-round",
        "round": round_name,
        "predictions": predictions,
        "rating_sources": public_ratings.sources if public_ratings else [],
        "rating_warnings": public_ratings.warnings if public_ratings else [],
        "market_sources": market_signals.sources,
        "market_warnings": market_signals.warnings,
    }


def final_predictions(
    data: Dict[str, Any],
    season: int,
    historical: Dict[str, float],
    runs: int,
    seed: int,
    public_ratings: Optional[PublicRatings],
    market_signals: Optional[MarketSignals] = None,
    market_weight: float = 0.35,
) -> Dict[str, Any]:
    matches = data.get("matches", [])
    base_records = build_current_records(matches)
    scorers = scorer_team_boost(matches)
    market_signals = market_signals or MarketSignals()
    counters = {
        "champion": Counter(),
        "runner_up": Counter(),
        "third": Counter(),
        "fourth": Counter(),
    }
    podium_counter: Counter[Tuple[str, str, str]] = Counter()
    for offset in range(runs):
        rng = random.Random(seed + offset)
        records = simulate_group_stage(rng, matches, base_records, historical, scorers, public_ratings)
        result = simulate_knockouts(rng, matches, records, historical, scorers, public_ratings)
        for key, value in result.items():
            counters[key][value] += 1
        podium = (result.get("champion"), result.get("runner_up"), result.get("third"))
        if all(podium) and len(set(podium)) == 3:
            podium_counter[podium] += 1
    rankings = {}
    for key, counter in counters.items():
        rankings[key] = [
            {"team": team, "probability": round(count / runs, 4), "count": count}
            for team, count in counter.most_common(12)
        ]
    market_futures, futures_weight, futures_warnings = champion_market_probabilities(market_signals, market_weight)
    if market_futures:
        model_champion = {team: count / runs for team, count in counters["champion"].items()}
        teams = set(model_champion) | set(market_futures)
        blended = []
        for team in teams:
            probability = (1.0 - futures_weight) * model_champion.get(team, 0.0) + futures_weight * market_futures.get(team, 0.0)
            blended.append(
                {
                    "team": team,
                    "probability": round(probability, 4),
                    "model_probability": round(model_champion.get(team, 0.0), 4),
                    "market_probability": round(market_futures.get(team, 0.0), 4),
                    "market_weight": round(futures_weight, 3),
                    "count": counters["champion"].get(team, 0),
                }
            )
        rankings["champion"] = sorted(blended, key=lambda row: row["probability"], reverse=True)[:12]
    return {
        "season": season,
        "target": "final",
        "runs": runs,
        "seed": seed,
        "rankings": rankings,
        "podiums": [
            {
                "champion": champion,
                "runner_up": runner_up,
                "third": third,
                "probability": round(count / runs, 4),
                "count": count,
            }
            for (champion, runner_up, third), count in podium_counter.most_common(12)
        ],
        "method": "Transparent heuristic plus Monte Carlo simulation over remaining fixtures.",
        "rating_sources": public_ratings.sources if public_ratings else [],
        "rating_warnings": public_ratings.warnings if public_ratings else [],
        "market_sources": market_signals.sources,
        "market_warnings": market_signals.warnings + futures_warnings,
    }


def render_prediction(result: Dict[str, Any], fmt: str, lang: str) -> str:
    if fmt == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)
    t = TEXT[lang]
    if result["target"] == "next-round":
        rows = []
        for row in result["predictions"]:
            if row["status"] != "forecast":
                rows.append((row.get("date", ""), display_team(row.get("team1", ""), lang), display_team(row.get("team2", ""), lang), t["unresolved_placeholder"], "", "", "", ""))
            else:
                market_signal = t["none"]
                if row.get("market_source"):
                    market_signal = f"{row['market_source']} / w={row.get('market_weight', 0):.0%}"
                rows.append(
                    (
                        row["date"],
                        display_team(row["team1"], lang),
                        display_team(row["team2"], lang),
                        t["forecast"],
                        f"{row['team1_probability']:.1%}",
                        f"{row['draw_probability']:.1%}",
                        f"{row['team2_probability']:.1%}",
                        market_signal,
                    )
                )
        title = result.get("round") or t["no_upcoming_round"]
        info_rows = [
            (t["round"], title),
            (t["rating_sources"], ", ".join(result.get("rating_sources") or []) or t["none"]),
            (t["market_sources"], ", ".join(result.get("market_sources") or []) or t["none"]),
        ]
        output = (
            f"# {t['next_round_forecast']}\n\n"
            + markdown_table([t["item"], t["value"]], info_rows)
            + "\n\n"
            + markdown_table([t["date"], t["team1"], t["team2"], t["status"], t["team1"], t["draw"], t["team2"], t["market_signal"]], rows)
        )
        warnings = render_warnings((result.get("rating_warnings") or []) + (result.get("market_warnings") or []), lang)
        return output + ("\n\n" + warnings if warnings else "")
    lines = [
        f"# {t['final_ranking_forecast']}",
        "",
        markdown_table(
            [t["item"], t["value"]],
            [
                (t["runs"], result["runs"]),
                (t["seed"], result["seed"]),
                (t["method"], t["method_text"]),
                (t["rating_sources"], ", ".join(result.get("rating_sources") or []) or t["none"]),
                (t["market_sources"], ", ".join(result.get("market_sources") or []) or t["none"]),
            ],
        ),
        "",
    ]
    if result.get("podiums"):
        lines.append(f"## {t['podiums']}")
        lines.append(
            markdown_table(
                [t["champion"], t["runner_up"], t["third"], t["probability"]],
                (
                    (
                        display_team(row["champion"], lang),
                        display_team(row["runner_up"], lang),
                        display_team(row["third"], lang),
                        f"{row['probability']:.1%}",
                    )
                    for row in result["podiums"]
                ),
            )
        )
        lines.append("")
    labels = {"champion": t["champion"], "runner_up": t["runner_up"], "third": t["third"], "fourth": t["fourth"]}
    for key, label in labels.items():
        lines.append(f"## {label}")
        if key == "champion" and any("market_probability" in row for row in result["rankings"][key]):
            lines.append(
                markdown_table(
                    [t["team"], t["blended_probability"], t["model_probability"], t["market_probability"]],
                    (
                        (
                            display_team(row["team"], lang),
                            f"{row['probability']:.1%}",
                            f"{row.get('model_probability', 0.0):.1%}",
                            f"{row.get('market_probability', 0.0):.1%}",
                        )
                        for row in result["rankings"][key]
                    ),
                )
            )
        else:
            lines.append(markdown_table([t["team"], t["probability"]], ((display_team(row["team"], lang), f"{row['probability']:.1%}") for row in result["rankings"][key])))
        lines.append("")
    warnings = render_warnings((result.get("rating_warnings") or []) + (result.get("market_warnings") or []), lang)
    if warnings:
        lines.append(warnings)
        lines.append("")
    return "\n".join(lines).rstrip()


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Output format.")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="Markdown output language. Defaults to Chinese. JSON keys stay stable.")
    parser.add_argument("--openfootball-url", help="Override OpenFootball URL template. Use {season} for the year.")
    parser.add_argument("--fjelstul-base-url", help="Override Fjelstul CSV base URL.")
    parser.add_argument("--no-elo", action="store_true", help="Disable public Elo ratings enhancement.")
    parser.add_argument("--elo-url", help="Override World Football Elo ratings URL.")
    parser.add_argument("--use-fifa-ranking", action="store_true", help="Fetch FIFA rankings for tournament teams. Slower because FIFA pages are loaded per team.")
    parser.add_argument("--fifa-url-template", help="Override FIFA team ranking URL template. Use {code} for the country code.")
    parser.add_argument("--market-signals-file", help="Optional JSON file with match odds or prediction-market probabilities to blend into forecasts.")
    parser.add_argument("--market-weight", type=float, default=0.35, help="Default market blend weight for usable market signals.")


def load_ratings_for_args(data: Dict[str, Any], args: argparse.Namespace) -> PublicRatings:
    teams = team_names_from_matches(data.get("matches", []))
    return load_public_ratings(
        teams,
        args.fjelstul_base_url,
        args.elo_url,
        args.fifa_url_template,
        use_elo=not args.no_elo,
        use_fifa=args.use_fifa_ranking,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="World Cup historical summaries and forecasts.")
    sub = parser.add_subparsers(dest="command", required=True)

    history = sub.add_parser("history", help="Show historical World Cup rankings.")
    add_common_args(history)
    history.add_argument("--since", type=int, default=1926, help="Earliest tournament year to include.")
    history.add_argument("--positions", type=int, default=4, help="Final ranking positions to include.")

    current = sub.add_parser("current", help="Show current tournament tables and top scorers.")
    add_common_args(current)
    current.add_argument("--season", type=int, default=2026, help="World Cup season.")

    predict = sub.add_parser("predict", help="Forecast next round or final ranking.")
    add_common_args(predict)
    predict.add_argument("--season", type=int, default=2026, help="World Cup season.")
    predict.add_argument("--target", choices=["next-round", "final"], required=True, help="Prediction target.")
    predict.add_argument("--runs", type=int, default=2000, help="Monte Carlo runs for final forecasts.")
    predict.add_argument("--seed", type=int, default=20260614, help="Deterministic random seed.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "history":
            _, rows = load_historical_strength(args.fjelstul_base_url, current_year=2026)
            print(render_history(historical_rows(rows, args.since, args.positions), args.format, args.lang))
            return 0

        data = fetch_json(season_url(args.season, args.openfootball_url))
        public_ratings = load_ratings_for_args(data, args)
        if args.command == "current":
            print(render_current(current_summary(data, args.season, public_ratings), args.format, args.lang))
            return 0

        historical, _ = load_historical_strength(args.fjelstul_base_url, current_year=args.season)
        market_signals = load_market_signals(args.market_signals_file)
        market_weight = clamp(args.market_weight, 0.0, 0.65)
        if args.target == "next-round":
            print(render_prediction(next_round_predictions(data, args.season, historical, public_ratings, market_signals, market_weight), args.format, args.lang))
        else:
            if args.runs <= 0:
                raise DataError("--runs must be positive")
            print(render_prediction(final_predictions(data, args.season, historical, args.runs, args.seed, public_ratings, market_signals, market_weight), args.format, args.lang))
        return 0
    except DataError as exc:
        print(f"worldcup_forecast: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
