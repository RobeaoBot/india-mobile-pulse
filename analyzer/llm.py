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


def analyze_posts(hours: int = None) -> dict:
    """
    分析最近一段时间的帖子，生成摘要报告
    优先使用 LLM，失败时回退到规则引擎
    """
    hours = hours or config.ANALYSIS_LOOKBACK_HOURS
    posts = models.get_posts_for_analysis(hours)

    if not posts:
        logger.info("[Analyzer] 没有帖子可供分析")
        return None

    period_start = min(p["published_at"] or p.get("collected_at", "") for p in posts)
    period_end = max(p["published_at"] or p.get("collected_at", "") for p in posts)

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
        brands = ", ".join(json.loads(p.get("brands", "[]"))) if p.get("brands") else ""
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


def _call_openai(prompt: str) -> dict:
    """调用 OpenAI 兼容接口"""
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai 包未安装，请运行: pip install openai")
        return None

    client = OpenAI(
        api_key=config.LLM_OPENAI_API_KEY,
        base_url=config.LLM_OPENAI_BASE_URL,
    )

    response = client.chat.completions.create(
        model=config.LLM_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": config.ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    content = response.choices[0].message.content.strip()

    # 尝试解析 JSON
    return _parse_llm_response(content)


def _call_gemini(prompt: str) -> dict:
    """调用 Google Gemini API"""
    try:
        import google.generativeai as genai
    except ImportError:
        logger.error("google-generativeai 包未安装，请运行: pip install google-generativeai")
        return None

    genai.configure(api_key=config.LLM_GEMINI_API_KEY)
    model = genai.GenerativeModel(config.LLM_GEMINI_MODEL)

    response = model.generate_content(
        f"{config.ANALYSIS_SYSTEM_PROMPT}\n\n{prompt}",
        generation_config={"temperature": 0.3, "max_output_tokens": 2000},
    )

    content = response.text.strip()
    return _parse_llm_response(content)


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
        try:
            brands = json.loads(p.get("brands", "[]"))
        except (json.JSONDecodeError, TypeError):
            brands = []

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
        try:
            os_tags = json.loads(p.get("os_tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            os_tags = []
        for os_name in os_tags:
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
