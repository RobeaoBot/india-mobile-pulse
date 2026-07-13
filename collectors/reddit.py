"""
India Mobile Pulse - Reddit Collector
Reddit 采集器：通过 RSS Feed 获取热帖（无需 API Key）
"""

import logging
import re
import time
from datetime import datetime
from urllib.parse import quote_plus

import requests
import feedparser

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class RedditCollector(BaseCollector):
    SOURCE_NAME = "reddit"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xml,application/rss+xml;q=0.9,*/*;q=0.7",
        })

    def collect(self) -> list:
        """采集 Reddit 帖子"""
        all_posts = []

        for subreddit in config.REDDIT_SUBREDDITS:
            try:
                posts = self._fetch_subreddit_rss(subreddit)
                all_posts.extend(posts)
                logger.info(f"[Reddit] r/{subreddit}: {len(posts)} posts")
                time.sleep(2)  # 避免 429 限速
            except Exception as e:
                logger.error(f"[Reddit] r/{subreddit} failed: {e}")
                time.sleep(5)  # 出错后等待更久

        for query in config.REDDIT_SEARCH_QUERIES:
            try:
                posts = self._fetch_search_rss(query)
                all_posts.extend(posts)
                logger.info(f"[Reddit] search '{query}': {len(posts)} posts")
                time.sleep(3)
            except Exception as e:
                logger.error(f"[Reddit] search '{query}' failed: {e}")
                time.sleep(5)

        seen = set()
        unique_posts = []
        for post in all_posts:
            if post["source_id"] not in seen:
                seen.add(post["source_id"])
                unique_posts.append(post)

        return [self.tag_post(p) for p in unique_posts]

    def _fetch_subreddit_rss(self, subreddit: str, limit: int = None) -> list:
        """通过 RSS 获取子版块热帖"""
        limit = limit or config.MAX_POSTS_PER_SOURCE
        url = f"https://www.reddit.com/r/{subreddit}/hot/.rss"

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[Reddit] RSS request failed r/{subreddit}: {e}")
            return []

        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            logger.warning(f"[Reddit] RSS parse failed r/{subreddit}")
            return []

        posts = []
        for entry in feed.entries[:limit]:
            if not self._is_relevant(entry, subreddit):
                continue

            source_id = self._extract_id(entry)
            published_at = self._parse_time(entry)
            content = self._clean_html(entry.get("summary", ""))
            score = self._extract_score(content)
            link = entry.get("link", "")

            if link and "/comments/" not in link:
                link = f"https://www.reddit.com/r/{subreddit}/comments/{source_id}"

            posts.append({
                "source": self.SOURCE_NAME,
                "source_id": source_id,
                "title": entry.get("title", ""),
                "content": self._truncate(content, 500),
                "author": entry.get("author", ""),
                "url": link,
                "score": score,
                "published_at": published_at,
            })

        return posts[:limit]

    def _fetch_search_rss(self, query: str, limit: int = None) -> list:
        """Reddit 搜索 RSS"""
        limit = limit or config.MAX_POSTS_PER_SOURCE
        encoded_query = quote_plus(query)
        url = f"https://www.reddit.com/search.rss?q={encoded_query}&sort=hot&t=week"

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[Reddit] search RSS failed '{query}': {e}")
            return []

        feed = feedparser.parse(resp.text)

        posts = []
        for entry in feed.entries[:limit]:
            source_id = self._extract_id(entry)
            published_at = self._parse_time(entry)
            content = self._clean_html(entry.get("summary", ""))

            posts.append({
                "source": self.SOURCE_NAME,
                "source_id": source_id,
                "title": entry.get("title", ""),
                "content": self._truncate(content, 500),
                "author": entry.get("author", ""),
                "url": entry.get("link", ""),
                "score": self._extract_score(content),
                "published_at": published_at,
            })

        return posts[:limit]

    def _is_relevant(self, entry, subreddit: str) -> bool:
        """判断帖子是否与印度手机市场相关"""
        text = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
        mobile_subs = [
            "android", "oneplus", "galaxys23fe", "pocophones",
            "realme", "xiaomi", "googlepixel", "nothingtech",
            "smartphones", "iphone",
        ]
        if subreddit.lower() in mobile_subs:
            return True

        india_kw = ["india", "indian", "desi"]
        mobile_kw = []
        for kws in config.BRAND_KEYWORDS.values():
            mobile_kw.extend(kws)
        mobile_kw.extend(["smartphone", "mobile", "phone", "android", "iphone"])
        has_india = any(kw in text for kw in india_kw)
        has_mobile = any(kw in text for kw in mobile_kw)
        return has_india and has_mobile

    @staticmethod
    def _extract_id(entry) -> str:
        """从 RSS entry 提取 Reddit 帖子 ID"""
        source_id = entry.get("id", entry.get("link", ""))
        match = re.search(r't3_(\w+)', source_id)
        if match:
            return match.group(1)
        parts = source_id.split("/")
        for i, part in enumerate(parts):
            if part == "comments" and i + 1 < len(parts):
                return parts[i + 1]
        return source_id.split("/")[-1] if "/" in source_id else source_id

    @staticmethod
    def _parse_time(entry) -> str:
        """解析发布时间"""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6]).isoformat()
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _extract_score(content: str) -> int:
        """从内容中提取分数"""
        match = re.search(r'(\d+)\s*points?', content, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    @staticmethod
    def _clean_html(text: str) -> str:
        """清理 HTML 标签"""
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."
