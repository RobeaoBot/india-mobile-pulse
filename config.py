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
# 注意：以下 ID 已陆续失效（RSS 返回 404），采集器会优雅降级。
# 主要数据由 TechMedia / HackerNews / News / Official 四个稳定源提供。
YOUTUBE_CHANNEL_IDS = [
    "UCOhHO2ICt0ti9KAh-QHvttQ",  # Technical Guruji  (已失效 404)
    "UCEPL07qzVsOcHd3sMUws65g",  # Trakin Tech       (已失效 404)
    "UCO2WJZKQoDW4Te6NHx4KfTg",  # Geekyranjit       (已失效 404)
    "UClVIlK8QHZ2PFkXF97bA0lg",  # C4ETech Hindi     (已失效 404)
    "UCXUJJNoP1QupwsYIWFXmsZg",  # Tech Burner       (已失效 404)
]

# Google News RSS 搜索关键词（综合热点）
NEWS_QUERIES = [
    "smartphone India",
    "mobile phone India launch 5G",
    "Android India",
    "iPhone India price",
]

# ============================================================
# 科技媒体 RSS（新增稳定源：替代失效的 YouTube / 被限速的 Reddit）
# ============================================================

TECH_MEDIA_RSS_SOURCES = [
    # --- 印度本地（最贴近目标市场）---
    {
        "name": "Gadgets360",
        "url": "https://feeds.feedburner.com/gadgets360-latest",
        "brand": "",
        "limit": 30,
    },
    # --- 全球手机/系统权威 ---
    {
        "name": "GSMArena",
        "url": "https://www.gsmarena.com/rss-news-reviews.php3",
        "brand": "",
        "limit": 20,
    },
    {
        "name": "XDA Developers",
        "url": "https://www.xda-developers.com/feed/",
        "brand": "",
        "limit": 15,
    },
    {
        "name": "Android Central",
        "url": "https://www.androidcentral.com/feeds/all",
        "brand": "",
        "limit": 20,
    },
    {
        "name": "9to5Mac",
        "url": "https://9to5mac.com/feed/",
        "brand": "Apple",
        "limit": 20,
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "brand": "",
        "limit": 15,
    },
]

# Hacker News 搜索关键词（Algolia API，Reddit 被 429 限速时的稳定替代）
HN_QUERIES = [
    "smartphone India",
    "Android",
    "iPhone",
    "Google Pixel",
    "mobile operating system",
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

# 说明：匹配时使用词边界（\b），因此多词短语和复数变体需显式列出。
# 已剔除 "cheap" / "return" / "fail" 等歧义过大的词（"cheap phone" 未必是贬义）。

POSITIVE_WORDS = [
    # 通用赞美
    "great", "amazing", "excellent", "awesome", "best", "love", "fantastic",
    "impressive", "perfect", "beautiful", "outstanding", "superb", "stellar",
    "brilliant", "stunning", "superior", "wonderful", "delightful", "solid",
    # 性能体验
    "smooth", "fast", "snappy", "responsive", "buttery", "powerful",
    "efficient", "seamless", "fluid", "reliable", "capable", "versatile",
    # 品质做工
    "premium", "durable", "rugged", "sleek", "polished", "refined", "crisp",
    "sharp", "vibrant", "lightweight", "flagship",
    # 价值与推荐
    "affordable", "value", "worth", "recommended", "bargain", "deal",
    "value for money", "bang for buck", "game changer", "must-buy",
    "price cut", "discount", "cheaper", "inexpensive",
    # 进步与创新
    "upgrade", "improve", "improved", "enhanced", "boost", "innovative",
    "breakthrough", "top-tier", "best-in-class", "unbeatable",
]

NEGATIVE_WORDS = [
    # 通用批评
    "worst", "terrible", "bad", "hate", "awful", "horrible", "poor",
    "disappointing", "disappointed", "underwhelming", "lackluster",
    "mediocre", "subpar", "inferior", "useless", "waste", "regret",
    # 性能问题
    "slow", "sluggish", "laggy", "stutter", "buggy", "glitch", "glitchy",
    "unstable", "unreliable", "crash", "crashes", "freeze", "throttling",
    # 硬件缺陷
    "heating", "overheating", "battery drain", "defect", "defective",
    "faulty", "broken", "flawed", "plasticky",
    # 体验不佳
    "annoying", "frustrating", "bloatware", "dim", "dull", "weak",
    # 价格与商业
    "overpriced", "pricey", "costly", "expensive", "scam", "fraud",
    # 负面事件
    "complaint", "complaints", "criticism", "backlash", "controversy",
    "issue", "issues", "problem", "problems", "concern", "concerns",
    "delay", "delayed", "cancelled", "canceled", "downgrade", "worse",
]

# 情感权重：标题凝练核心态度，正文多为客观描述，因此标题权重更高。
# 例：标题命中 1 个正面词（权重2）即判为正面，无需像旧逻辑那样命中 2 个。
SENTIMENT_TITLE_WEIGHT = int(os.environ.get("SENTIMENT_TITLE_WEIGHT", "2"))
SENTIMENT_CONTENT_WEIGHT = int(os.environ.get("SENTIMENT_CONTENT_WEIGHT", "1"))

# LLM 情感增强（可选）。开启后会用 LLM 覆写部分帖子的情感标签，
# 需先配置 LLM_PROVIDER 与对应 API Key，否则自动回退到词典法。
LLM_SENTIMENT_ENABLED = os.environ.get("LLM_SENTIMENT_ENABLED", "0") == "1"
# 每批发给 LLM 的帖子数（控制单次 token 消耗）
LLM_SENTIMENT_BATCH_SIZE = int(os.environ.get("LLM_SENTIMENT_BATCH_SIZE", "25"))
# 只分析热度 >= 该值的帖子，避免对海量低热帖子浪费调用；0 表示不限
LLM_SENTIMENT_MIN_SCORE = int(os.environ.get("LLM_SENTIMENT_MIN_SCORE", "0"))

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

# 默认跳过的数据源（已确认失效，避免每次运行白跑）
# YouTube: 5 个频道 ID 的 RSS 均返回 404，已失效
# 在代码层面兜底，这样即使不修改 workflow 配置也不会浪费时间
# 如需强制启用某源，可用环境变量覆盖（设为留空则不默认跳过任何源）
DEFAULT_SKIP_SOURCES = os.environ.get("DEFAULT_SKIP_SOURCES", "youtube")

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
