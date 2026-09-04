"""
India Mobile Pulse - LLM Analyzer
支持 OpenAI 兼容接口 / Google Gemini / 规则引擎兜底
"""

import json
import logging
from datetime import datetime

import config
import models

logger = logging.getLogger(__name__)


def _load_tags(value, default=None):
    """
    兼容标签字段的两种形态：
    - 数据库读出的是 JSON 字符串 '["Apple"]'
    - 采集器内存中的是 Python 列表 ["Apple"]
    """
    if isinstance(value, (list, dict)):
        return value
    if not value:
        return [] if default is None else default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return [] if default is None else default


def analyze_posts(hours: int = None, posts: list = None) -> dict:
    """
    分析最近一段时间的帖子，生成摘要报告
    优先使用 LLM，失败时回退到规则引擎

    :param posts: 直接传入帖子列表（优先）。用于 GitHub Actions 等
                  刚采集完、尚未从数据库读取的场景。
    :param hours: 未传 posts 时，从数据库读取最近 N 小时的帖子
    """
    hours = hours or config.ANALYSIS_LOOKBACK_HOURS
    if posts is None:
        posts = models.get_posts_for_analysis(hours)

    if not posts:
        logger.info("[Analyzer] 没有帖子可供分析")
        return None

    # 时间字段可能缺失，做兜底避免 min/max 取到 None 报错
    def _ts(p):
        return p.get("published_at") or p.get("collected_at") or ""

    period_start = min(_ts(p) for p in posts)
    period_end = max(_ts(p) for p in posts)

    analysis = {
        "period_start": period_start,
        "period_end": period_end,
        "posts_analyzed": len(posts),
        "provider": "rule",
        "summary": "",
        "hot_topics": [],
        "brand_sentiment": {},
        "key_insights": [],
        "trending_keywords": [],
    }

    # 尝试 LLM 分析
    if config.LLM_PROVIDER != "none":
        try:
            llm_result = _llm_analyze(posts)
            if llm_result:
                analysis.update(llm_result)
                analysis["provider"] = config.LLM_PROVIDER
                logger.info(f"[Analyzer] LLM 分析完成 ({config.LLM_PROVIDER})")
        except Exception as e:
            logger.error(f"[Analyzer] LLM 分析失败，回退到规则引擎: {e}")

    # 规则引擎兜底（如果 LLM 未提供结果）
    if not analysis["summary"]:
        rule_result = _rule_analyze(posts)
        analysis.update(rule_result)
        analysis["provider"] = "rule"
        logger.info("[Analyzer] 规则引擎分析完成")

    # 保存分析结果
    analysis_id = models.insert_analysis(analysis)
    analysis["id"] = analysis_id

    return analysis


def _llm_analyze(posts: list) -> dict:
    """使用 LLM 进行分析"""

    # 构建帖子文本
    posts_text = ""
    for i, p in enumerate(posts[:50], 1):  # 限制帖子数量以控制 token
        brands = ", ".join(_load_tags(p.get("brands"))) if p.get("brands") else ""
        posts_text += f"\n---\n[{i}] [{p['source'].upper()}] {p['title']}\n"
        if p.get("content"):
            posts_text += f"Content: {p['content'][:200]}\n"
        if brands:
            posts_text += f"Brands: {brands}\n"
        posts_text += f"Score: {p.get('score', 0)}\n"

    prompt = f"""Analyze the following {len(posts)} social media posts and news articles about the Indian mobile phone market:

{posts_text}

Provide your analysis in the JSON format specified in the system prompt."""

    if config.LLM_PROVIDER == "openai_compatible":
        return _call_openai(prompt)
    elif config.LLM_PROVIDER == "gemini":
        return _call_gemini(prompt)
    else:
        raise ValueError(f"Unknown LLM provider: {config.LLM_PROVIDER}")


def _call_openai(prompt: str, system_prompt: str = None) -> dict:
    """调用 OpenAI 兼容接口，返回按分析格式解析后的结果"""
    content = _openai_text(prompt, system_prompt)
    return _parse_llm_response(content) if content else None


def _openai_text(prompt: str, system_prompt: str = None) -> str:
    """调用 OpenAI 兼容接口，返回原始文本（供不同任务自行解析）"""
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai 包未安装，请运行: pip install openai")
        return ""

    client = OpenAI(
        api_key=config.LLM_OPENAI_API_KEY,
        base_url=config.LLM_OPENAI_BASE_URL,
    )

    response = client.chat.completions.create(
        model=config.LLM_OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt or config.ANALYSIS_SYSTEM_PROMPT,
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    return (response.choices[0].message.content or "").strip()


def _call_gemini(prompt: str, system_prompt: str = None) -> dict:
    """调用 Google Gemini API，返回按分析格式解析后的结果"""
    content = _gemini_text(prompt, system_prompt)
    return _parse_llm_response(content) if content else None


def _gemini_text(prompt: str, system_prompt: str = None) -> str:
    """调用 Google Gemini API，返回原始文本（供不同任务自行解析）"""
    try:
        import google.generativeai as genai
    except ImportError:
        logger.error("google-generativeai 包未安装，请运行: pip install google-generativeai")
        return ""

    genai.configure(api_key=config.LLM_GEMINI_API_KEY)
    model = genai.GenerativeModel(config.LLM_GEMINI_MODEL)

    response = model.generate_content(
        f"{system_prompt or config.ANALYSIS_SYSTEM_PROMPT}\n\n{prompt}",
        generation_config={"temperature": 0.3, "max_output_tokens": 2000},
    )

    return (response.text or "").strip()


def _call_llm_text(prompt: str, system_prompt: str = None) -> str:
    """按当前配置的 provider 调用 LLM，返回原始文本"""
    if config.LLM_PROVIDER == "openai_compatible":
        return _openai_text(prompt, system_prompt)
    if config.LLM_PROVIDER == "gemini":
        return _gemini_text(prompt, system_prompt)
    raise ValueError(f"Unknown LLM provider: {config.LLM_PROVIDER}")


def _parse_llm_response(content: str) -> dict:
    """解析 LLM 返回的 JSON"""
    # 尝试提取 JSON（可能被 markdown 代码块包裹）
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(content)
        return {
            "summary": result.get("summary", ""),
            "hot_topics": result.get("hot_topics", []),
            "brand_sentiment": result.get("brand_sentiment", {}),
            "key_insights": result.get("key_insights", []),
            "trending_keywords": result.get("trending_keywords", []),
        }
    except json.JSONDecodeError:
        logger.warning("[Analyzer] LLM 返回非 JSON 格式，使用文本作为摘要")
        return {"summary": content[:500]}


def _rule_analyze(posts: list) -> dict:
    """
    基于规则的分析引擎（无需 API Key）
    - 统计品牌提及和情感
    - 提取热门话题（基于标题关键词频率）
    - 生成简要文本摘要
    """
    from collections import Counter

    # 品牌提及统计
    brand_mentions = Counter()
    brand_sentiments = {}

    for p in posts:
        brands = _load_tags(p.get("brands"))
        sentiment = p.get("sentiment", "neutral")

        for brand in brands:
            brand_mentions[brand] += 1
            if brand not in brand_sentiments:
                brand_sentiments[brand] = {"positive": 0, "negative": 0, "neutral": 0}
            brand_sentiments[brand][sentiment] += 1

    # 生成品牌情感摘要
    brand_sentiment_summary = {}
    for brand, counts in brand_sentiments.items():
        total = sum(counts.values())
        if counts["positive"] > counts["negative"]:
            dominant = "positive"
        elif counts["negative"] > counts["positive"]:
            dominant = "negative"
        else:
            dominant = "neutral"
        brand_sentiment_summary[brand] = {
            "sentiment": dominant,
            "reason": f"正面{counts['positive']}条/负面{counts['negative']}条/中性{counts['neutral']}条 (共{total}条提及)",
        }

    # 热门话题（基于标题关键词）
    title_words = Counter()
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "about", "like",
        "through", "after", "over", "between", "out", "against", "during",
        "without", "before", "under", "around", "among", "it", "its",
        "this", "that", "these", "those", "i", "me", "my", "we", "our",
        "you", "your", "he", "him", "his", "she", "her", "they", "them",
        "their", "what", "which", "who", "when", "where", "why", "how",
        "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "no", "not", "only", "own", "same", "so", "than",
        "too", "very", "just", "because", "but", "and", "or", "if", "then",
        "also", "new", "one", "two", "get", "got", "any", "how", "much",
        "many", "still", "even", "way", "need", "use", "make", "know",
        "think", "see", "look", "come", "take", "want", "give", "first",
        "well", "back", "been", "call", "who", "its", "now", "long",
        "down", "day", "get", "has", "him", "her", "than", "them", "what",
        "their", "which", "will", "up", "out", "there", "here", "just",
        "don", "didn", "doesn", "won", "wasn", "weren", "isn", "aren",
        "hasn", "haven", "hadn", "couldn", "shouldn", "wouldn",
        "phone", "phones", "device", "devices", "india", "indian",
    }

    for p in posts:
        words = p.get("title", "").lower().split()
        for w in words:
            w = w.strip(".,!?;:'\"()[]{}").lower()
            if len(w) > 2 and w not in stop_words:
                title_words[w] += 1

    # OS 提及统计
    os_mentions = Counter()
    for p in posts:
        for os_name in _load_tags(p.get("os_tags")):
            os_mentions[os_name] += 1

    # 热门话题（取前10个高频词组）
    hot_topics = []
    top_keywords = title_words.most_common(10)
    for kw, count in top_keywords:
        # 找到包含该关键词的高分帖子
        related_posts = [
            p for p in posts if kw in p.get("title", "").lower()
        ]
        related_posts.sort(key=lambda x: x.get("score", 0), reverse=True)
        description = related_posts[0]["title"][:80] if related_posts else ""
        heat = "high" if count >= 5 else "medium" if count >= 3 else "low"
        hot_topics.append({
            "topic": kw,
            "description": description,
            "heat": heat,
            "count": count,
        })

    # 生成摘要
    summary_parts = []

    top_brands = brand_mentions.most_common(5)
    if top_brands:
        brands_str = "、".join(
            [f"{b}({c}次提及)" for b, c in top_brands]
        )
        summary_parts.append(f"本期监测到最受关注的品牌为：{brands_str}。")

    top_os = os_mentions.most_common(3)
    if top_os:
        os_str = "、".join([f"{o}({c}次)" for o, c in top_os])
        summary_parts.append(f"操作系统讨论热度：{os_str}。")

    if hot_topics:
        top_3 = hot_topics[:3]
        topics_str = "、".join([t["topic"] for t in top_3])
        summary_parts.append(f"热门讨论话题包括：{topics_str}等。")

    # 情感概况
    sentiment_counts = Counter(p.get("sentiment", "neutral") for p in posts)
    total_sent = sum(sentiment_counts.values())
    if total_sent > 0:
        pos_pct = sentiment_counts.get("positive", 0) / total_sent * 100
        neg_pct = sentiment_counts.get("negative", 0) / total_sent * 100
        summary_parts.append(
            f"整体情感倾向：正面{pos_pct:.0f}%、负面{neg_pct:.0f}%、"
            f"中性{100-pos_pct-neg_pct:.0f}%。"
        )

    summary = "".join(summary_parts) if summary_parts else "本期无显著热点。"

    # 关键洞察
    key_insights = []
    if top_brands:
        key_insights.append(f"品牌声量前三：{', '.join([b for b, _ in top_brands[:3]])}")
    if hot_topics:
        key_insights.append(f"讨论最热的关键词：{', '.join([t['topic'] for t in hot_topics[:5]])}")
    if top_os:
        key_insights.append(f"OS 话题热度：{', '.join([o for o, _ in top_os])}")

    return {
        "summary": summary,
        "hot_topics": hot_topics,
        "brand_sentiment": brand_sentiment_summary,
        "key_insights": key_insights,
        "trending_keywords": [kw for kw, _ in title_words.most_common(15)],
    }


# ============================================================
# LLM 情感增强（可选）
# ============================================================

SENTIMENT_SYSTEM_PROMPT = """You are a sentiment classifier for tech news, reviews, and social posts about the Indian mobile phone market.

Classify each item as exactly one of: positive, negative, neutral.

Rules:
- positive: expresses praise, satisfaction, excitement, or a clearly favorable judgment (e.g. "excellent battery life", "great value for money", "best phone this year").
- negative: expresses criticism, disappointment, complaints, defects, or a clearly unfavorable judgment (e.g. "buggy update ruins it", "overpriced for what you get", "severe battery drain").
- neutral: purely factual reporting — product launches, spec leaks, price announcements, release dates, official statements, partnership news. Marketing or promotional wording WITHOUT explicit evaluative language is still neutral.

Be strict: most tech news is factual and should be neutral. Do not infer positive sentiment merely from the existence of a product announcement.

Respond with JSON only, no explanation, in this exact shape:
{"<id>": "positive", "<id>": "neutral", ...}"""


def enhance_sentiment(posts: list) -> dict:
    """
    用 LLM 批量精修情感标签。

    :return: {source_id: "positive"/"negative"/"neutral"}，仅含 LLM 成功判定的条目。
             未配置 LLM 或调用失败时返回空 dict —— 调用方应保持词典法结果，
             这样即使没有 API Key，流程也能正常跑完（自动降级到词典法）。
    """
    if not posts:
        return {}

    if config.LLM_PROVIDER == "none":
        logger.info("[Sentiment] 未配置 LLM_PROVIDER，跳过情感增强（沿用词典法）")
        return {}

    batch_size = max(1, getattr(config, "LLM_SENTIMENT_BATCH_SIZE", 25))
    min_score = getattr(config, "LLM_SENTIMENT_MIN_SCORE", 0)

    targets = [p for p in posts if (p.get("score") or 0) >= min_score]
    if not targets:
        return {}

    # 热度高的优先：调用预算不足时，至少覆盖最重要的内容
    targets.sort(key=lambda p: p.get("score") or 0, reverse=True)

    result = {}
    total_batches = (len(targets) + batch_size - 1) // batch_size
    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]
        try:
            mapping = _llm_sentiment_batch(batch)
            result.update(mapping)
            logger.info(
                f"[Sentiment] 批次 {i // batch_size + 1}/{total_batches}: "
                f"{len(mapping)}/{len(batch)} 条"
            )
        except Exception as e:
            logger.warning(f"[Sentiment] 批次 {i // batch_size + 1} 失败: {e}")

    return result


def _llm_sentiment_batch(batch: list) -> dict:
    """对单个批次调用 LLM 做情感分类"""
    lines = []
    valid_ids = set()
    for p in batch:
        sid = str(p.get("source_id") or "")
        title = (p.get("title") or "").strip()
        if not sid or not title:
            continue
        lines.append(f"{sid}\t{title}")
        valid_ids.add(sid)

    if not lines:
        return {}

    prompt = (
        "Classify the sentiment of each item below.\n"
        'Respond with JSON only: {"<id>": "positive|negative|neutral", ...}\n\n'
        + "\n".join(lines)
    )

    raw = _call_llm_text(prompt, SENTIMENT_SYSTEM_PROMPT)
    if not raw:
        return {}

    return _parse_sentiment_response(raw, valid_ids)


def _parse_sentiment_response(raw: str, valid_ids: set) -> dict:
    """解析 LLM 返回的情感 JSON，丢弃非法值与未知 id"""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[Sentiment] LLM 返回非 JSON，忽略该批次")
        return {}

    valid = {"positive", "negative", "neutral"}
    result = {}
    for k, v in data.items():
        key, val = str(k), str(v).strip().lower()
        if key in valid_ids and val in valid:
            result[key] = val
    return result
