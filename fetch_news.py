#!/usr/bin/env python3
"""
每日游戏新闻聚合脚本
数据源：游民星空(爬虫) + 3DMGame(爬虫) + 游戏大观(RSS)
"""

import hashlib
import os
import re
import zoneinfo
from datetime import date, datetime
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

# 使用北京时间 (Asia/Shanghai)
BEIJING_TZ = zoneinfo.ZoneInfo("Asia/Shanghai")
TODAY = datetime.now(BEIJING_TZ).date()

NEWS_DIR = Path(__file__).parent / "news"
TODAY_STR = TODAY.strftime("%Y-%m-%d")
TODAY_CN = f"{TODAY.year}年{TODAY.month}月{TODAY.day}日"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

# 非游戏类新闻关键词过滤
NON_GAMING_KEYWORDS = [
    "交警", "车祸", "中毒", "法院", "逮捕", "被判", "杀人", "死亡",
    "二手房", "房价", "股市", "基金", "理财",
    "高温", "暴雨", "地震", "台风", "洪水",
    "纯电车", "法拉利", "油价", "新能源车",
    "谷歌AI搜索", "大模型", "OpenAI", "ChatGPT",
    "脱口秀", "综艺", "电影", "电视剧", "演唱会",
    # 只过滤明确非游戏的，宁缺毋滥
]


def is_gaming_related(title):
    """判断标题是否与游戏相关"""
    title_lower = title.lower()
    for kw in NON_GAMING_KEYWORDS:
        if kw in title:
            # 有些关键词也可能是游戏内容，再判断一下
            game_indicators = ["游戏", "NS", "PS", "Xbox", "Steam", "Switch",
                               "发售", "DLC", "预告", "试玩", "关卡"]
            # 如果同时包含游戏关键词，放行
            if any(indicator in title for indicator in game_indicators):
                continue
            return False
    return True


def clean_title(title):
    """清理标题，去掉来源前缀等"""
    # 去掉 "游戏新闻" 前缀 (3DMGame 常见)
    title = re.sub(r"^游戏新闻", "", title).strip()
    return title


def extract_articles_from_html(html, base_url, source_name):
    """从 HTML 中提取文章标题和链接"""
    soup = BeautifulSoup(html, "lxml")
    items = []
    seen_links = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        title = a.get_text(strip=True)
        if len(title) < 12:
            continue

        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = base_url.rstrip("/") + href

        if href in seen_links:
            continue
        seen_links.add(href)

        title = clean_title(title)

        items.append({
            "title": title,
            "link": href,
            "desc": "",
            "source": source_name,
            "time": "",
        })
    return items


def fetch_gamersky():
    """抓取游民星空新闻"""
    url = "https://www.gamersky.com/news/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        items = extract_articles_from_html(r.text, "https://www.gamersky.com", "游民星空")
        items = [
            it for it in items
            if re.search(r"gamersky\.com/news/(202605|202606)/", it["link"])
            and is_gaming_related(it["title"])
        ]
        print(f"  [OK] 游民星空: {len(items)} 条")
        return items[:18]
    except Exception as e:
        print(f"  [WARN] 游民星空 抓取失败: {e}")
        return []


def fetch_3dmgame():
    """抓取 3DMGame 新闻"""
    url = "https://www.3dmgame.com/news/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
        items = []

        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            title = a.get_text(strip=True)
            if len(title) < 12:
                continue
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = "https://www.3dmgame.com" + href

            if not re.search(r"3dmgame\.com/news/(202605|202606)/", href):
                continue

            title = clean_title(title)
            if not is_gaming_related(title):
                continue

            items.append({
                "title": title,
                "link": href,
                "desc": "",
                "source": "3DMGame",
                "time": "",
            })

        seen = set()
        unique = []
        for it in items:
            if it["link"] not in seen:
                seen.add(it["link"])
                unique.append(it)

        print(f"  [OK] 3DMGame: {len(unique)} 条")
        return unique[:18]
    except Exception as e:
        print(f"  [WARN] 3DMGame 抓取失败: {e}")
        return []


def fetch_gamelook():
    """抓取游戏大观行业新闻"""
    url = "http://www.gamelook.com.cn/feed/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        feed = feedparser.parse(r.text)
        items = []
        for entry in feed.entries[:18]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            desc = BeautifulSoup(entry.get("description", ""), "html.parser").get_text(strip=True)
            items.append({
                "title": clean_title(title),
                "link": link,
                "desc": desc[:200],
                "source": "游戏大观",
                "time": "",
            })
        print(f"  [OK] 游戏大观: {len(items)} 条")
        return items
    except Exception as e:
        print(f"  [WARN] 游戏大观 抓取失败: {e}")
        return []


def deduplicate(items):
    """基于标题去重"""
    seen = set()
    unique = []
    for item in items:
        key = hashlib.md5(item["title"].encode("utf-8")).hexdigest()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def interleave(items):
    """按来源轮替排序，让 Top 20 覆盖更多源"""
    groups = {}
    for it in items:
        s = it["source"]
        groups.setdefault(s, []).append(it)

    result = []
    i = 0
    while True:
        done = True
        for s in sorted(groups.keys()):
            if i < len(groups[s]):
                result.append(groups[s][i])
                done = False
        if done:
            break
        i += 1
    return result


def format_markdown(items):
    """生成 Markdown 文件"""
    lines = []
    lines.append(f"# 游戏圈日报 {TODAY_CN}")
    lines.append(f"")
    lines.append(f"> **数据源**: 游民星空 / 3DMGame / 游戏大观")
    lines.append(f"> **更新时间**: {datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"")
    lines.append("---")
    lines.append("")

    for i, item in enumerate(items[:20], 1):
        title = item["title"]
        source = item["source"]
        desc = item.get("desc", "")
        link = item.get("link", "")

        lines.append(f"### {i}. {title}")
        lines.append(f"")
        lines.append(f"- **来源**: {source}")
        if desc:
            lines.append(f"- {desc}")
        if link:
            lines.append(f"- [🔗 阅读原文]({link})")
        lines.append("")

    lines.append("---")
    lines.append(f"> 共聚合 {len(items)} 条 | 精选 20 条 | {TODAY_CN}")
    lines.append(f"> 由 GitHub Actions 自动生成")
    return "\n".join(lines)


def get_source_stats(items):
    """统计各来源条数"""
    stats = {}
    for it in items:
        s = it.get("source", "未知")
        stats[s] = stats.get(s, 0) + 1
    return stats


def main():
    print(f"[INFO] 开始抓取游戏新闻 ({TODAY_CN})...")

    all_items = []
    all_items.extend(fetch_gamersky())
    all_items.extend(fetch_3dmgame())
    all_items.extend(fetch_gamelook())

    print(f"\n[INFO] 原始共 {len(all_items)} 条")

    unique = deduplicate(all_items)
    interleaved = interleave(unique)
    print(f"[INFO] 去重后 {len(unique)} 条")
    print(f"[INFO] 来源分布: {get_source_stats(unique)}")

    if not unique:
        print("[ERROR] 所有源均抓取失败！")
        return

    os.makedirs(NEWS_DIR, exist_ok=True)
    output_path = NEWS_DIR / f"gaming-news-{TODAY_STR}.md"
    content = format_markdown(interleaved)
    output_path.write_text(content, encoding="utf-8")
    print(f"[OK] 已保存: {output_path}")


if __name__ == "__main__":
    main()
