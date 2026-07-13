"""
India Mobile Pulse - YouTube Collector
YouTube 采集器：通过 RSS Feed 获取频道最新视频（无需 API Key）
"""

import logging
from datetime import datetime

import feedparser

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class YouTubeCollector(BaseCollector):
    SOURCE_NAME = "youtube"

    def collect(self) -> list:
        """采集 YouTube 频道最新视频"""
        all_posts = []

        for channel_id in config.YOUTUBE_CHANNEL_IDS:
            try:
                posts = self._fetch_channel(channel_id)
                all_posts.extend(posts)
                logger.info(f"[YouTube] 频道 {channel_id}: 获取 {len(posts)} 条")
            except Exception as e:
                logger.error(f"[YouTube] 频道 {channel_id} 采集失败: {e}")

        # 去重
        seen = set()
        unique_posts = []
        for post in all_posts:
            if post["source_id"] not in seen:
                seen.add(post["source_id"])
                unique_posts.append(post)

        return [self.tag_post(p) for p in unique_posts]

    def _fetch_channel(self, channel_id: str) -> list:
        """通过 RSS Feed 获取频道最新视频"""
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning(f"[YouTube] 频道 {channel_id} RSS 解析失败")
            return []

        posts = []
        limit = min(15, config.MAX_POSTS_PER_SOURCE)

        for entry in feed.entries[:limit]:
            # 提取视频 ID
            video_id = getattr(entry, "yt_videoid", "")
            if not video_id:
                # 从链接中提取
                video_id = entry.get("id", "").split(":")[-1]

            # 提取观看数
            views = 0
            media_community = getattr(entry, "media_community", {})
            if media_community:
                star_rating = media_community.get("starRating", {})
                if isinstance(star_rating, dict):
                    views = int(star_rating.get("count", 0))
                elif hasattr(star_rating, "get"):
                    views = int(star_rating.get("count", 0))

            # 解析发布时间
            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6]).isoformat()
                except (TypeError, ValueError):
                    pass

            posts.append({
                "source": self.SOURCE_NAME,
                "source_id": video_id or entry.get("id", ""),
                "title": entry.get("title", ""),
                "content": self._clean_summary(entry.get("summary", "")),
                "author": entry.get("author", ""),
                "url": entry.get("link", f"https://youtube.com/watch?v={video_id}"),
                "score": views,
                "published_at": published_at,
            })

        return posts

    @staticmethod
    def _clean_summary(summary: str) -> str:
        """清理 YouTube RSS 的 HTML 摘要"""
        import re
        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', summary)
        # 合并空白
        text = re.sub(r'\s+', ' ', text).strip()
        # 截断
        if len(text) > 500:
            text = text[:500] + "..."
        return text
