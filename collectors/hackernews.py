"""
India Mobile Pulse - Hacker News Collector
Hacker News 采集器：通过 Algolia 官方搜索 API 获取科技圈讨论（无需 API Key）

用途：捕捉开发者/极客圈对手机、操作系统、芯片的英文讨论，
      作为 Reddit 被限速（429）时的稳定替代源。
"""

import logging
from datetime import datetime

import requests

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
ALGOLIA_SEARCH_BY_DATE = "https://hn.algolia.com/api/v1/search_by_date"


class HackerNewsCollector(BaseCollector):
    SOURCE_NAME = "hackernews"

    def collect(self) -> list:
        """按关键词搜索 HN 故事"""
        all_posts = []

        for query in config.HN_QUERIES:
            try:
                posts = self._search(query)
                all_posts.extend(posts)
                logger.info(f"[HackerNews] '{query}': {len(posts)} 条")
            except Exception as e:
                logger.error(f"[HackerNews] 搜索 '{query}' 失败: {e}")

        unique = self.dedupe(all_posts)
        return [self.tag_post(p) for p in unique]

    def _search(self, query: str, hits_per_page: int = 20) -> list:
        """调用 Algolia 搜索接口"""
        params = {
            "query": query,
            "tags": "story",
            "hitsPerPage": min(hits_per_page, config.MAX_POSTS_PER_SOURCE),
        }

        try:
            resp = self.session.get(ALGOLIA_SEARCH_URL, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"[HackerNews] 请求失败 '{query}': {e}")
            return []

        posts = []
        for hit in data.get("hits", []):
            title = (hit.get("title") or "").strip()
            if not title:
                continue

            object_id = hit.get("objectID", "")
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"

            published_at = None
            created_at = hit.get("created_at")
            if created_at:
                try:
                    published_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    ).isoformat()
                except (ValueError, AttributeError):
                    pass

            posts.append({
                "source": self.SOURCE_NAME,
                "source_id": f"hn_{object_id}",
                "title": title,
                "content": self._truncate(self._clean_html(hit.get("story_text") or ""), 500),
                "author": hit.get("author", ""),
                "url": url,
                "score": hit.get("points") or 0,
                "published_at": published_at,
            })

        return posts
