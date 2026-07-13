"""
India Mobile Pulse - Official News Collector
官方渠道 & 权威科技媒体采集器
包含：品牌官方博客 RSS、权威科技媒体 RSS、品牌公告 Google News 搜索
"""

import hashlib
import logging
import re
from datetime import datetime
from urllib.parse import quote_plus

import requests
import feedparser

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class OfficialCollector(BaseCollector):
    SOURCE_NAME = "official"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xml,application/rss+xml;q=0.9,*/*;q=0.7",
        })

    def collect(self) -> list:
        """采集官方渠道和权威科技媒体"""
        all_posts = []

        # 1. 品牌官方博客 / 权威科技媒体 RSS
        for source in config.OFFICIAL_RSS_SOURCES:
            try:
                posts = self._fetch_rss(source)
                all_posts.extend(posts)
                logger.info(f"[Official] {source['name']}: {len(posts)} posts")
            except Exception as e:
                logger.error(f"[Official] {source['name']} failed: {e}")

        # 2. 品牌官方公告 Google News 搜索
        for query in config.OFFICIAL_NEWS_QUERIES:
            try:
                posts = self._fetch_brand_news(query)
                all_posts.extend(posts)
                logger.info(f"[Official] brand news '{query}': {len(posts)} posts")
            except Exception as e:
                logger.error(f"[Official] brand news '{query}' failed: {e}")

        # 去重
        seen = set()
        unique_posts = []
        for post in all_posts:
            if post["source_id"] not in seen:
                seen.add(post["source_id"])
                unique_posts.append(post)

        return [self.tag_post(p) for p in unique_posts]

    def _fetch_rss(self, source: dict) -> list:
        """从 RSS 源获取文章"""
        name = source["name"]
        url = source["url"]
        brand = source.get("brand", "")
        limit = source.get("limit", config.MAX_POSTS_PER_SOURCE)

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[Official] RSS request failed {name}: {e}")
            return []

        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            logger.warning(f"[Official] RSS parse failed {name}")
            return []

        posts = []
        for entry in feed.entries[:limit]:
            published_at = self._parse_time(entry)

            author = entry.get("author", name)
            if isinstance(author, dict):
                author = author.get("name", name)

            content = entry.get("summary", entry.get("description", ""))
            content = self._clean_html(content)

            source_id = entry.get("id", entry.get("link", ""))
            if len(source_id) > 200:
                source_id = hashlib.md5(source_id.encode()).hexdigest()

            posts.append({
                "source": self.SOURCE_NAME,
                "source_id": f"official_{source_id}",
                "title": entry.get("title", ""),
                "content": self._truncate(content, 500),
                "author": author,
                "url": entry.get("link", ""),
                "score": 0,
                "published_at": published_at,
                "_brand_hint": brand,
            })

        return posts

    def _fetch_brand_news(self, query: str) -> list:
        """通过 Google News 搜索品牌官方公告"""
        encoded = quote_plus(query)
        url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded}"
            f"&hl=en-IN&gl=IN&ceid=IN:en"
        )

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[Official] brand news RSS failed '{query}': {e}")
            return []

        feed = feedparser.parse(resp.text)
        posts = []

        for entry in feed.entries[:15]:
            published_at = self._parse_time(entry)

            source_name = self._extract_source_name(entry)
            title = entry.get("title", "")
            if " - " in title and source_name != "Unknown":
                title = title.rsplit(f" - {source_name}", 1)[0].strip()

            source_id = entry.get("id", entry.get("link", ""))
            if len(source_id) > 200:
                source_id = hashlib.md5(source_id.encode()).hexdigest()

            content = self._clean_html(entry.get("summary", ""))

            posts.append({
                "source": self.SOURCE_NAME,
                "source_id": f"official_gn_{source_id}",
                "title": title,
                "content": self._truncate(content, 500),
                "author": source_name,
                "url": entry.get("link", ""),
                "score": 0,
                "published_at": published_at,
            })

        return posts

    @staticmethod
    def _parse_time(entry) -> str:
        """解析发布时间"""
        for attr in ["published_parsed", "updated_parsed"]:
            val = getattr(entry, attr, None)
            if val:
                try:
                    return datetime(*val[:6]).isoformat()
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _extract_source_name(entry) -> str:
        """提取来源名称"""
        tag = getattr(entry, "source", None)
        if tag:
            if isinstance(tag, dict):
                return tag.get("title", "Unknown")
            if hasattr(tag, "title"):
                return tag.title
            return str(tag)
        return "Unknown"

    @staticmethod
    def _clean_html(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."
