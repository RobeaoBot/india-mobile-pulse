"""
India Mobile Pulse - Base Collector
采集器基类，提供品牌/OS/硬件标签自动打标功能
"""

import json
import re
import logging
from abc import ABC, abstractmethod
from datetime import datetime

import config

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """采集器基类"""

    # 来源名称
    SOURCE_NAME = "base"

    @abstractmethod
    def collect(self) -> list:
        """执行采集，返回帖子列表"""
        pass

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

        # 基础情感分析
        post["sentiment"] = self._basic_sentiment(text)

        return post

    def _basic_sentiment(self, text: str) -> str:
        """基于词典的简单情感判断"""
        pos_count = sum(1 for w in config.POSITIVE_WORDS if w in text)
        neg_count = sum(1 for w in config.NEGATIVE_WORDS if w in text)

        if pos_count > neg_count + 1:
            return "positive"
        elif neg_count > pos_count + 1:
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
