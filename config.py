"""
India Mobile Pulse - Configuration
印度手机圈热点搜集分析工具 配置文件
支持环境变量覆盖，便于 Docker 部署
"""

import os

# ============================================================
# 采集源配置
# ============================================================

# Reddit 子版块（精简以避免频率限制，每次采集间隔 2 秒）
REDDIT_SUBREDDITS = [
    "Android",
    "oneplus",
    "GooglePixel",
    "smartphones",
    "iphone",
]

# Reddit 搜索关键词（跨版块搜索）
REDDIT_SEARCH_QUERIES = [
    "India smartphone",
    "India mobile 5G",
]

# YouTube 频道 ID（印度科技博主）
# 获取方式：访问频道页面 → 查看源码 → 搜索 "channelId"
YOUTUBE_CHANNEL_IDS = [
    "UCOhHO2ICt0ti9KAh-QHvttQ",  # Technical Guruji
    "UCEPL07qzVsOcHd3sMUws65g",  # Trakin Tech
    "UCO2WJZKQoDW4Te6NHx4KfTg",  # Geekyranjit
    "UClVIlK8QHZ2PFkXF97bA0lg",  # C4ETech Hindi
    "UCXUJJNoP1QupwsYIWFXmsZg",  # Tech Burner
]

# Google News RSS 搜索关键词（综合热点）
NEWS_QUERIES = [
    "smartphone India",
    "mobile phone India launch 5G",
    "Android India",
    "iPhone India price",
]

# ============================================================
# 官方渠道 & 权威科技媒体
# ============================================================

# 品牌/OS 官方博客 RSS（已验证可用）
OFFICIAL_RSS_SOURCES = [
    # --- OS 官方 ---
    {
        "name": "Google Android Blog",
        "url": "https://blog.google/products/android/rss/",
        "brand": "Google",
    },
    {
        "name": "Apple Newsroom",
        "url": "https://www.apple.com/newsroom/rss-feed.rss",
        "brand": "Apple",
    },
    # --- 权威科技媒体（覆盖品牌官方发布） ---
    {
        "name": "9to5Google",
        "url": "https://9to5google.com/feed/",
        "brand": "",
    },
    {
        "name": "Android Authority",
        "url": "https://www.androidauthority.com/feed/",
        "brand": "",
    },
    {
        "name": "FoneArena (India)",
        "url": "https://www.fonearena.com/blog/feed/",
        "brand": "",
    },
]

# 品牌官方公告 Google News 定向搜索
OFFICIAL_NEWS_QUERIES = [
    "Samsung official announcement India smartphone",
    "Xiaomi Redmi launch India official",
    "OnePlus official India launch",
    "Realme official India announcement",
    "Nothing Phone official India",
    "Oppo official India smartphone",
    "Vivo official India launch",
    "Motorola official India smartphone",
    "iOS Android OS update India official",
    "HarmonyOS official announcement",
]

# ============================================================
# 品牌与关键词配置
# ============================================================

# 品牌 → 关联关键词映射（用于自动打标）
BRAND_KEYWORDS = {
    "Samsung":   ["samsung", "galaxy", "one ui", "exynos"],
    "Apple":     ["apple", "iphone", "ios", "ipad", "macbook"],
    "OnePlus":   ["oneplus", "1+", "oxygenos"],
    "Xiaomi":    ["xiaomi", "redmi", "poco", "miui", "hyperos"],
    "Realme":    ["realme", "realme ui"],
    "Oppo":      ["oppo", "coloros"],
    "Vivo":      ["vivo", "funos", "originos"],
    "Nothing":   ["nothing phone", "nothing os"],
    "Google":    ["pixel", "google pixel", "stock android"],
    "Motorola":  ["motorola", "moto", "moto g", "moto edge"],
    "Nokia":     ["nokia", "hmd"],
    "iQOO":      ["iqoo"],
    "Tecno":     ["tecno", "hios"],
    "Infinix":   ["infinix", "xos"],
    "Lava":      ["lava", "agni"],
    "Micromax":  ["micromax"],
}

# 操作系统关键词
OS_KEYWORDS = {
    "Android":     ["android", "stock android", "one ui", "miui", "hyperos",
                    "coloros", "realme ui", "oxygenos", "funos", "nothing os"],
    "iOS":         ["ios", "iphone os", "ipados"],
    "HarmonyOS":   ["harmonyos", "harmony os"],
}

# 硬件关键词
HARDWARE_KEYWORDS = [
    "snapdragon", "mediatek", "dimensity", "exynos", "tensor",
    "5g", "4g", "lte", "amoled", "oled", "lcd",
    "megapixel", "camera", "battery", "charging", "fast charge",
    "ram", "storage", "processor", "chipset", "sox",
    "foldable", "flip", "notch", "refresh rate", "hz",
    "under display", "fingerprint", "face id",
]

# ============================================================
# 情感分析词典（规则引擎兜底用）
# ============================================================

POSITIVE_WORDS = [
    "great", "amazing", "excellent", "awesome", "best", "love", "fantastic",
    "impressive", "perfect", "beautiful", "smooth", "fast", "powerful",
    "innovative", "breakthrough", "stunning", "superior", "outstanding",
    "reliable", "value", "affordable", "premium", "flagship killer",
    "game changer", "upgrade", "improve", "impressive",
]

NEGATIVE_WORDS = [
    "worst", "terrible", "bad", "hate", "disappointing", "overpriced",
    "expensive", "slow", "laggy", "buggy", "heating", "battery drain",
    "poor", "cheap", "fraud", "scam", "waste", "issue", "problem",
    "defect", "broken", "crash", "fail", "return", "refund",
    "downgrade", "regret", "mediocre",
]

# ============================================================
# LLM 分析配置
# ============================================================

# LLM 提供商: "openai_compatible" | "gemini" | "none"(仅规则引擎)
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "none")

# OpenAI 兼容接口配置（适用于 OpenAI / Groq / Ollama 等）
LLM_OPENAI_API_KEY = os.environ.get("LLM_OPENAI_API_KEY", "")
LLM_OPENAI_BASE_URL = os.environ.get("LLM_OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_OPENAI_MODEL = os.environ.get("LLM_OPENAI_MODEL", "gpt-4o-mini")

# Google Gemini 配置
LLM_GEMINI_API_KEY = os.environ.get("LLM_GEMINI_API_KEY", "")
LLM_GEMINI_MODEL = os.environ.get("LLM_GEMINI_MODEL", "gemini-2.0-flash")

# 分析提示词
ANALYSIS_SYSTEM_PROMPT = """You are an expert analyst specializing in the Indian mobile phone market. 
You track smartphone hardware, mobile operating systems, brand competition, and consumer trends in India.

Analyze the provided social media posts and news articles. Respond in the following JSON format:
{
    "summary": "3-5 sentence executive summary of the most important trends",
    "hot_topics": [
        {"topic": "Topic name", "description": "Brief description", "heat": "high/medium/low"}
    ],
    "brand_sentiment": {
        "BrandName": {"sentiment": "positive/negative/neutral", "reason": "Brief reason"}
    },
    "key_insights": ["Insight 1", "Insight 2", "Insight 3"],
    "trending_keywords": ["keyword1", "keyword2", "keyword3"]
}

Focus on the Indian market context. Identify launches, price changes, consumer reactions, and competitive dynamics.
Write the summary and insights in Chinese (简体中文), but keep brand names and technical terms in English."""

# ============================================================
# 调度配置
# ============================================================

# 每日采集时间（24小时制），格式 "HH:MM"
DAILY_COLLECTION_TIME = os.environ.get("DAILY_COLLECTION_TIME", "12:00")

# 每次采集每个来源的最大帖子数
MAX_POSTS_PER_SOURCE = 25

# 分析时回溯的小时数
ANALYSIS_LOOKBACK_HOURS = 24

# ============================================================
# 数据库配置
# ============================================================

DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/pulse.db")

# ============================================================
# Flask 配置
# ============================================================

FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
