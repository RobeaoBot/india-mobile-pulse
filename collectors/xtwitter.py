"""
India Mobile Pulse - X (Twitter) Collector

X 平台采集器。

背景：X 官方 API 已全面收费，免费层无法读取时间线；Nitter、RSSHub、
syndication 等非官方通道实测均已失效（详见 config.X_QUERIES 注释）。
因此本采集器通过 Google News 的 `site:x.com` 检索被搜索引擎收录的推文。

这些被收录的通常是被媒体引用或引发广泛讨论的高热度内容，
与本项目"热点监测"的定位契合；实测手机领域相关性约 94%。

局限（重要）：
- 只能覆盖被 Google 收录的推文，不是完整的实时数据流；
- 收录存在延迟，时效性弱于直连 API。

替换指南：若日后获得官方 API 配额，只需重写 `_search()` 返回同样结构的
帖子列表，打分、去重、相关性过滤、打标等流程均无需改动。
"""

import logging
import re
from urllib.parse import quote_plus

import config
from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# 手机领域通用词，与品牌词、OS 词共同构成相关性过滤条件
GENERIC_MOBILE_WORDS = [
    "smartphone", "smart phone", "mobile", "phone", "phones",
    "android", "ios", "iphone", "ipad", "tablet", "foldable",
    "5g", "4g", "lte", "handset", "feature phone",
    "launch", "launched", "launching", "price", "pricing",
    "spec", "specs", "chipset", "camera", "battery", "display",
    "update", "upgrade", "unboxing", "review",
]


class XTwitterCollector(BaseCollector):
    SOURCE_NAME = "xtwitter"

    def __init__(self):
        super().__init__()
        self._strong_keywords = self._build_strong_keywords()

    @staticmethod
    def _build_strong_keywords():
        """构造强相关词库：品牌词 + OS 词，命中即判定为手机领域内容"""
        kws = set()
        for words in config.BRAND_KEYWORDS.values():
            kws.update(w.lower() for w in words)
        for words in config.OS_KEYWORDS.values():
            kws.update(w.lower() for w in words)
        return sorted(kws)

    def collect(self) -> list:
        """采集 X 上被收录的手机领域推文"""
        all_posts = []

        for query in config.X_QUERIES:
            try:
                posts = self._search(query)
                all_posts.extend(posts)
                logger.info(f"[X] '{query}': {len(posts)} 条")
            except Exception as e:
                logger.error(f"[X] 搜索 '{query}' 失败: {e}")

        unique = self._dedupe_by_title(self.dedupe(all_posts))

        # Google News 的 site: 检索会混入无关推文，按手机领域词过滤
        related = [p for p in unique if self._is_mobile_related(p)]
        logger.info(f"[X] 去重后 {len(unique)} 条 → 手机相关 {len(related)} 条")

        return [self.tag_post(p) for p in related]

    def _search(self, query: str, limit: int = 30) -> list:
        """通过 Google News 检索 site:x.com 的推文"""
        url = (
            f"https://news.google.com/rss/search"
            f"?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        )

        posts = self.fetch_rss_feed(
            url=url, limit=limit, source_label="X", id_prefix="x_"
        )

        for p in posts:
            p["title"] = self._strip_source_suffix(p.get("title", ""))
        return posts

    @staticmethod
    def _strip_source_suffix(title: str) -> str:
        """去掉 Google News 标题尾部的 " - x.com" 来源后缀"""
        for suffix in (" - x.com", " - X", " - Twitter", " - x"):
            if title.endswith(suffix):
                return title[: -len(suffix)].strip()
        return title

    @staticmethod
    def _dedupe_by_title(posts: list) -> list:
        """
        按标题去重。

        Google News 对同一条推文在不同检索词下可能返回不同的 entry id，
        仅靠 source_id 去重会残留重复项，因此再按标题兜底去重一次。
        """
        seen = set()
        result = []
        for p in posts:
            key = (p.get("title") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(p)
        return result

    def _is_mobile_related(self, post: dict) -> bool:
        """
        判断推文是否属于手机领域。

        采用两级判定。只用"命中任一关键词"过松——"phone"/"mobile" 属于高频词，
        会把 "Make in India"、政治发言、社会新闻这类仅偶然提到 phone 的内容放进来。

        1) 命中品牌词或 OS 词 → 强信号，直接保留；
        2) 否则需累计命中 ≥2 个手机领域通用词。
        """
        text = f"{post.get('title', '')} {post.get('content', '')}".lower()

        def hit(kw):
            return re.search(r'\b' + re.escape(kw) + r'\b', text) is not None

        if any(hit(kw) for kw in self._strong_keywords):
            return True

        return sum(1 for kw in GENERIC_MOBILE_WORDS if hit(kw)) >= 2
