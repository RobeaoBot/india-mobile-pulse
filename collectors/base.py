"""
India Mobile Pulse - Base Collector
采集器基类，提供品牌/OS/硬件标签自动打标功能
"""

import json
import re
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime

import requests
import feedparser

import config

logger = logging.getLogger(__name__)

# 通用 User-Agent
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class BaseCollector(ABC):
    """采集器基类"""

    # 来源名称
    SOURCE_NAME = "base"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xml,application/rss+xml;q=0.9,*/*;q=0.7",
        })

    @abstractmethod
    def collect(self) -> list:
        """执行采集，返回帖子列表"""
        pass

    # ==========================================================
    # 通用 RSS 抓取能力（供子类复用）
    # ==========================================================

    def fetch_rss_feed(self, url: str, limit: int = 25, source_label: str = "",
                       brand: str = "", id_prefix: str = "") -> list:
        """
        通用 RSS 抓取，返回标准化帖子列表。

        对请求失败 / 解析失败做优雅降级（返回空列表），避免单源故障中断整体采集。
        """
        limit = limit or config.MAX_POSTS_PER_SOURCE
        try:
            resp = self.session.get(url, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"[{self.SOURCE_NAME}] RSS 请求失败 {source_label or url}: {e}")
            return []

        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            logger.warning(f"[{self.SOURCE_NAME}] RSS 解析失败 {source_label or url}")
            return []

        posts = []
        for entry in feed.entries[:limit]:
            content = entry.get("summary", entry.get("description", ""))
            content = self._clean_html(content)

            author = entry.get("author", source_label)
            if isinstance(author, dict):
                author = author.get("name", source_label)

            source_id = entry.get("id", entry.get("link", ""))
            if not source_id:
                source_id = hashlib.md5(
                    (entry.get("title", "") + url).encode()
                ).hexdigest()
            elif len(source_id) > 200:
                source_id = hashlib.md5(source_id.encode()).hexdigest()

            posts.append({
                "source": self.SOURCE_NAME,
                "source_id": f"{id_prefix}{source_id}",
                "title": entry.get("title", "").strip(),
                "content": self._truncate(content, 500),
                "author": author or source_label,
                "url": entry.get("link", ""),
                "score": 0,
                "published_at": self._parse_entry_time(entry),
                "_brand_hint": brand,
            })

        return posts

    @staticmethod
    def _parse_entry_time(entry) -> str:
        """解析 RSS entry 的发布时间"""
        for attr in ("published_parsed", "updated_parsed"):
            val = getattr(entry, attr, None)
            if val:
                try:
                    return datetime(*val[:6]).isoformat()
                except (TypeError, ValueError):
                    pass
        return None

    @staticmethod
    def _clean_html(text: str) -> str:
        """清理 HTML 标签"""
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """截断文本"""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."

    def dedupe(self, posts: list) -> list:
        """按 source_id 去重"""
        seen = set()
        result = []
        for p in posts:
            key = p.get("source_id") or p.get("url", "")
            if key and key not in seen:
                seen.add(key)
                result.append(p)
        return result

    def tag_post(self, post: dict) -> dict:
        """
        为帖子自动打标：品牌、操作系统、硬件关键词
        同时计算基础情感倾向
        """
        text = f"{post.get('title', '')} {post.get('content', '')}".lower()

        # 品牌打标
        brands = []
        for brand, keywords in config.BRAND_KEYWORDS.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    brands.append(brand)
                    break
        post["brands"] = list(set(brands))

        # OS 打标
        os_tags = []
        for os_name, keywords in config.OS_KEYWORDS.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', text):
                    os_tags.append(os_name)
                    break
        post["os_tags"] = list(set(os_tags))

        # 硬件关键词打标
        hw_tags = []
        for kw in config.HARDWARE_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                hw_tags.append(kw)
        post["hardware_tags"] = list(set(hw_tags))

        # 基础情感分析（标题与正文分开加权）
        post["sentiment"] = self._basic_sentiment(
            post.get("title", ""), post.get("content", "")
        )

        return post

    @staticmethod
    def _count_keywords(words, text: str) -> int:
        """
        用词边界统计关键词命中数。

        用 \b 而非朴素子串匹配，避免 "lag" 命中 "lagoon"、
        "deal" 命中 "dealer" 这类误判。
        """
        if not text:
            return 0
        return sum(
            1 for w in words
            if re.search(r'\b' + re.escape(w) + r'\b', text)
        )

    def _basic_sentiment(self, title: str = "", content: str = "") -> str:
        """
        基于加权词典的情感判断。

        标题权重高于正文：标题通常凝练核心态度（如 "Excellent Battery Life"），
        而正文多是客观参数描述。旧实现把两者拼接后等权计数，导致明显的
        正面/负面内容被中性正文稀释，需要命中 2 个以上情感词才会被判定，
        最终 97% 的帖子都落到 neutral。
        """
        title_l = (title or "").lower()
        content_l = (content or "").lower()

        tw = getattr(config, "SENTIMENT_TITLE_WEIGHT", 2)
        cw = getattr(config, "SENTIMENT_CONTENT_WEIGHT", 1)

        pos = (tw * self._count_keywords(config.POSITIVE_WORDS, title_l)
               + cw * self._count_keywords(config.POSITIVE_WORDS, content_l))
        neg = (tw * self._count_keywords(config.NEGATIVE_WORDS, title_l)
               + cw * self._count_keywords(config.NEGATIVE_WORDS, content_l))

        if pos > neg:
            return "positive"
        if neg > pos:
            return "negative"
        return "neutral"

    def _format_datetime(self, dt) -> str:
        """格式化日期时间"""
        if dt is None:
            return None
        if isinstance(dt, datetime):
            return dt.isoformat()
        if isinstance(dt, str):
            return dt
        return str(dt)
