#!/usr/bin/env python3
"""
每日科技新闻聚合脚本
数据源：36氪 + 机器之心 + 开源中国
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

BEIJING_TZ = zoneinfo.ZoneInfo("Asia/Shanghai")
TODAY = datetime.now(BEIJING_TZ).date()
TODAY_STR = TODAY.strftime("%Y-%m-%d")
TODAY_CN = f"{TODAY.year}年{TODAY.month}月{TODAY.day}日"

NEWS_DIR = Path(__file__).parent / "news"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

# 非科技类关键词过滤
NON_TECH_KEYWORDS = [
    "二手房", "房价", "基金", "理财",
    "综艺", "电影", "电视剧", "演唱会",
    "高温", "暴雨", "地震", "台风",
    "纯电车", "法拉利", "油价",
]


def is_tech_related(title):
    """判断标题是否与科技相关"""
    for kw in NON_TECH_KEYWORDS:
        if kw in title:
            return False
    return True


def clean_title(title):
    """清理标题"""
    title = re.sub(r"^\s*[\[\(][^\]\)]*[\]\)]\s*", "", title).strip()
    return title


def fetch_36kr():
    """抓取 36氪 科技快讯"""
    url = "https://36kr.com/news"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
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
                href = "https://36kr.com" + href
            if not href.startswith("http"):
                continue
            if href in seen_links:
                continue
            seen_links.add(href)

            title = clean_title(title)
            if not is_tech_related(title):
                continue

            items.append({
                "title": title,
                "link": href,
                "desc": "",
                "source": "36氪",
                "time": "",
            })

        print(f"  [OK] 36氪: {len(items)} 条")
        return items[:20]
    except Exception as e:
        print(f"  [WARN] 36氪 抓取失败: {e}")
        return []


def fetch_jiqizhixin():
    """抓取机器之心（AI 新闻）"""
    url = "https://www.jiqizhixin.com/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
        items = []
        seen_links = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            title = a.get_text(strip=True)
            if len(title) < 10:
                continue
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = "https://www.jiqizhixin.com" + href
            if not href.startswith("http"):
                continue
            if href in seen_links:
                continue
            seen_links.add(href)

            title = clean_title(title)
            if not is_tech_related(title):
                continue

            items.append({
                "title": title,
                "link": href,
                "desc": "",
                "source": "机器之心",
                "time": "",
            })

        print(f"  [OK] 机器之心: {len(items)} 条")
        return items[:15]
    except Exception as e:
        print(f"  [WARN] 机器之心 抓取失败: {e}")
        return []


def fetch_oschina():
    """抓取开源中国（软件/开源资讯）"""
    url = "https://www.oschina.net/news"
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
                href = "https://www.oschina.net" + href
            if not href.startswith("http"):
                continue

            title = clean_title(title)
            if not is_tech_related(title):
                continue

            items.append({
                "title": title,
                "link": href,
                "desc": "",
                "source": "开源中国",
                "time": "",
            })

        seen = set()
        unique = []
        for it in items:
            if it["link"] not in seen:
                seen.add(it["link"])
                unique.append(it)

        print(f"  [OK] 开源中国: {len(unique)} 条")
        return unique[:15]
    except Exception as e:
        print(f"  [WARN] 开源中国 抓取失败: {e}")
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
    """按来源轮替排序"""
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
    lines.append(f"# 科技圈日报 {TODAY_CN}")
    lines.append("")
    lines.append("> **数据源**: 36氪 / 机器之心 / 开源中国")
    lines.append(f"> **更新时间**: {datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, item in enumerate(items[:20], 1):
        title = item["title"]
        source = item["source"]
        desc = item.get("desc", "")
        link = item.get("link", "")

        lines.append(f"### {i}. {title}")
        lines.append("")
        lines.append(f"- **来源**: {source}")
        if desc:
            lines.append(f"- {desc}")
        if link:
            lines.append(f"- [🔗 阅读原文]({link})")
        lines.append("")

    lines.append("---")
    lines.append(f"> 共聚合 {len(items)} 条 | 精选 20 条 | {TODAY_CN}")
    lines.append("> 由 GitHub Actions 自动生成")
    return "\n".join(lines)


def get_source_stats(items):
    """统计各来源条数"""
    stats = {}
    for it in items:
        s = it.get("source", "未知")
        stats[s] = stats.get(s, 0) + 1
    return stats


def main():
    print(f"[INFO] 开始抓取科技新闻 ({TODAY_CN})...")

    all_items = []
    all_items.extend(fetch_36kr())
    all_items.extend(fetch_jiqizhixin())
    all_items.extend(fetch_oschina())

    print(f"\n[INFO] 原始共 {len(all_items)} 条")

    unique = deduplicate(all_items)
    interleaved = interleave(unique)
    print(f"[INFO] 去重后 {len(unique)} 条")
    print(f"[INFO] 来源分布: {get_source_stats(unique)}")

    if not unique:
        print("[ERROR] 所有源均抓取失败！")
        return

    os.makedirs(NEWS_DIR, exist_ok=True)
    output_path = NEWS_DIR / f"tech-news-{TODAY_STR}.md"
    content = format_markdown(interleaved)
    output_path.write_text(content, encoding="utf-8")
    print(f"[OK] 已保存: {output_path}")


if __name__ == "__main__":
    main()
