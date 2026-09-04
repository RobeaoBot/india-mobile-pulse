"""
India Mobile Pulse - Tech Media Collector
科技媒体采集器：聚合全球 + 印度本地权威手机媒体的 RSS（无需 API Key）

覆盖：
  - 印度本地：Gadgets360 / NDTV Gadgets（最爱印度市场信号）
  - 全球手机：GSMArena / XDA / Android Central / 9to5Mac / TechCrunch
"""

import logging

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class TechMediaCollector(BaseCollector):
    SOURCE_NAME = "techmedia"

    def collect(self) -> list:
        """聚合所有科技媒体 RSS"""
        all_posts = []

        for source in config.TECH_MEDIA_RSS_SOURCES:
            name = source["name"]
            try:
                posts = self.fetch_rss_feed(
                    url=source["url"],
                    limit=source.get("limit", config.MAX_POSTS_PER_SOURCE),
                    source_label=name,
                    brand=source.get("brand", ""),
                    id_prefix="tm_",
                )
                all_posts.extend(posts)
                logger.info(f"[TechMedia] {name}: {len(posts)} 条")
            except Exception as e:
                logger.error(f"[TechMedia] {name} 采集失败: {e}")

        unique = self.dedupe(all_posts)
        return [self.tag_post(p) for p in unique]
