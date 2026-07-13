"""
India Mobile Pulse - Google News Collector
新闻采集器：通过 Google News RSS 获取印度手机市场相关新闻（无需 API Key）
"""

import logging
from datetime import datetime
from urllib.parse import quote_plus

import feedparser

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class NewsCollector(BaseCollector):
    SOURCE_NAME = "news"

    def collect(self) -> list:
        """采集 Google News 印度手机相关新闻"""
        all_posts = []

        for query in config.NEWS_QUERIES:
            try:
                posts = self._fetch_news(query)
                all_posts.extend(posts)
                logger.info(f"[News] 搜索 '{query}': 获取 {len(posts)} 条")
            except Exception as e:
                logger.error(f"[News] 搜索 '{query}' 失败: {e}")

        # 去重（基于 URL）
        seen_urls = set()
        unique_posts = []
        for post in all_posts:
            url = post.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                unique_posts.append(post)

        return [self.tag_post(p) for p in unique_posts]

    def _fetch_news(self, query: str) -> list:
        """获取 Google News RSS"""
        # Google News RSS 印度英文版
        encoded_query = quote_plus(query)
        url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded_query}"
            f"&hl=en-IN&gl=IN&ceid=IN:en"
        )

        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning(f"[News] RSS 解析失败: {query}")
            return []

        posts = []
        limit = min(20, config.MAX_POSTS_PER_SOURCE)

        for entry in feed.entries[:limit]:
            # 解析发布时间
            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6]).isoformat()
                except (TypeError, ValueError):
                    pass

            # 提取来源
            source_name = "Unknown"
            source_tag = getattr(entry, "source", None)
            if source_tag:
                if isinstance(source_tag, dict):
                    source_name = source_tag.get("title", "Unknown")
                elif hasattr(source_tag, "title"):
                    source_name = source_tag.title
                else:
                    source_name = str(source_tag)

            # 清理标题（Google News 标题常带 " - Source Name" 后缀）
            title = entry.get("title", "")
            if " - " in title and source_name != "Unknown":
                title = title.rsplit(f" - {source_name}", 1)[0].strip()

            posts.append({
                "source": self.SOURCE_NAME,
                "source_id": entry.get("id", entry.get("link", "")),
                "title": title,
                "content": self._clean_summary(entry.get("summary", "")),
                "author": source_name,
                "url": entry.get("link", ""),
                "score": 0,  # Google News RSS 无评分
                "published_at": published_at,
            })

        return posts

    @staticmethod
    def _clean_summary(summary: str) -> str:
        """清理 HTML 摘要"""
        import re
        text = re.sub(r'<[^>]+>', ' ', summary)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 500:
            text = text[:500] + "..."
        return text
