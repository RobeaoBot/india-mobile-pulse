#!/usr/bin/env python3
"""
数据导出脚本 - 供 GitHub Actions 调用
运行所有采集器 + 分析器，将结果导出为 JSON 供静态站点使用
"""

import json
import os
import sys
from datetime import datetime

# 确保能 import 项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import models
from collectors.reddit import RedditCollector
from collectors.youtube import YouTubeCollector
from collectors.news import NewsCollector
from collectors.official import OfficialCollector
from analyzer.llm import analyze_posts


def run_all_collectors():
    """运行所有采集器"""
    collectors = [
        ("reddit", RedditCollector()),
        ("youtube", YouTubeCollector()),
        ("news", NewsCollector()),
        ("official", OfficialCollector()),
    ]
    
    results = {}
    for name, collector in collectors:
        try:
            print(f"  采集 {name}...", flush=True)
            posts = collector.collect()
            results[name] = {"status": "success", "count": len(posts), "posts": posts}
            print(f"  ✅ {name}: {len(posts)} 条", flush=True)
        except Exception as e:
            results[name] = {"status": "error", "error": str(e), "posts": []}
            print(f"  ❌ {name}: {e}", flush=True)
    
    return results


def run_analysis():
    """运行分析"""
    try:
        print("  运行分析...", flush=True)
        result = analyze_posts()
        print(f"  ✅ 分析完成", flush=True)
        return result
    except Exception as e:
        print(f"  ❌ 分析失败: {e}", flush=True)
        return None


def generate_os_daily(posts):
    """生成 OS 日报数据：按操作系统分类，整理归纳，输出中文摘要"""
    from collections import Counter, defaultdict

    OS_CONFIG = {
        "Android": {
            "icon": "🤖",
            "name_cn": "安卓",
            "color": "#3DDC84",
            "keywords": ["android", "pixel", "samsung one ui", "one ui", "miui", "coloros", "funtoo", "oxygenos", "realme ui", "nothing os"],
        },
        "iOS": {
            "icon": "🍎",
            "name_cn": "苹果 iOS",
            "color": "#007AFF",
            "keywords": ["ios", "iphone", "ipad", "ipados"],
        },
        "HarmonyOS": {
            "icon": "🔮",
            "name_cn": "鸿蒙",
            "color": "#CE0E2D",
            "keywords": ["harmonyos", "harmony", "huawei os", "emui"],
        },
    }

    # 按 OS 分类帖子
    os_posts = defaultdict(list)
    os_sentiment = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0})
    os_brands = defaultdict(Counter)
    os_hot_topics = defaultdict(Counter)

    for p in posts:
        os_tags = p.get("os_tags", "[]")
        if isinstance(os_tags, str):
            try:
                os_tags = json.loads(os_tags)
            except:
                os_tags = []

        if not os_tags:
            # 通过标题关键词补充识别
            title_lower = (p.get("title", "") + " " + p.get("content", "")).lower()
            for os_name, cfg in OS_CONFIG.items():
                if any(kw in title_lower for kw in cfg["keywords"]):
                    os_tags = [os_name]
                    break

        for os_name in os_tags:
            os_posts[os_name].append(p)
            # 情感统计
            sent = p.get("sentiment", "neutral")
            if sent in os_sentiment[os_name]:
                os_sentiment[os_name][sent] += 1
            # 品牌统计
            brands = p.get("brands", "[]")
            if isinstance(brands, str):
                try:
                    brands = json.loads(brands)
                except:
                    brands = []
            for b in brands:
                os_brands[os_name][b] += 1
            # 热词统计
            title = p.get("title", "")
            for word in title.split():
                if len(word) > 4:
                    os_hot_topics[os_name][word] += 1

    # 生成每个 OS 的中文日报
    reports = []
    for os_name in ["Android", "iOS", "HarmonyOS"]:
        cfg = OS_CONFIG.get(os_name, {"icon": "📱", "name_cn": os_name, "color": "#58a6ff"})
        posts_list = os_posts.get(os_name, [])
        sent = os_sentiment.get(os_name, {"positive": 0, "negative": 0, "neutral": 0})
        brands = os_brands.get(os_name, Counter())
        total_sent = sent["positive"] + sent["negative"] + sent["neutral"]

        # 生成中文摘要
        summary = _generate_os_summary(os_name, cfg, posts_list, sent, brands, total_sent)

        # 精选帖子（取评分最高或最新的5条）
        top_posts = sorted(posts_list, key=lambda p: p.get("score", 0), reverse=True)[:5]
        if not top_posts:
            top_posts = posts_list[:5]

        report = {
            "os_name": os_name,
            "icon": cfg["icon"],
            "name_cn": cfg["name_cn"],
            "color": cfg["color"],
            "total_posts": len(posts_list),
            "sentiment": sent,
            "sentiment_pct": {
                "positive": round(sent["positive"] / total_sent * 100) if total_sent else 0,
                "negative": round(sent["negative"] / total_sent * 100) if total_sent else 0,
                "neutral": round(sent["neutral"] / total_sent * 100) if total_sent else 0,
            },
            "top_brands": [{"name": b, "count": c} for b, c in brands.most_common(8)],
            "summary": summary,
            "highlights": _extract_highlights(posts_list),
            "top_posts": [
                {
                    "title": p.get("title", ""),
                    "url": p.get("url", ""),
                    "source": p.get("source", ""),
                    "score": p.get("score", 0),
                    "author": p.get("author", ""),
                    "published_at": p.get("published_at", p.get("collected_at", "")),
                }
                for p in top_posts
            ],
        }
        reports.append(report)

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "title": f"📱 印度手机操作系统日报 — {datetime.now().strftime('%Y年%m月%d日')}",
        "reports": reports,
        "last_updated": datetime.now().isoformat(),
    }


def _generate_os_summary(os_name, cfg, posts, sentiment, brands, total):
    """生成中文摘要"""
    name = cfg["name_cn"]
    count = len(posts)

    if count == 0:
        return f"今日暂无{name}相关动态。"

    # 情感判断
    if total > 0:
        pos_pct = sentiment["positive"] / total * 100
        if pos_pct >= 50:
            mood = "整体氛围积极乐观"
        elif pos_pct >= 30:
            mood = "舆论态度偏中性"
        else:
            mood = "以中性讨论为主"
    else:
        mood = "暂无情感数据"

    # 品牌提及
    top_brands = [b for b, _ in brands.most_common(3)]
    brand_str = "、".join(top_brands) if top_brands else "多个品牌"

    # 话题提取
    key_topics = []
    for p in posts[:8]:
        title = p.get("title", "")
        # 提取关键信息（简化版，取标题前30字）
        if len(key_topics) < 3:
            key_topics.append(title[:40])

    summary = f"{name}生态今日共有 {count} 条相关讨论，{mood}。"
    if top_brands:
        summary += f"热门品牌：{brand_str}。"
    if key_topics:
        summary += f"关注焦点：{key_topics[0]}"

    return summary


def _extract_highlights(posts):
    """从帖子中提取亮点（中文归纳）"""
    highlights = []

    # 按关键词分类亮点
    CATEGORIES = {
        "🆕 新品发布": ["launch", "release", "announce", "unveil", "reveal", "发布", "推出"],
        "🔄 系统更新": ["update", "upgrade", "beta", "stable", "rollout", "更新", "升级"],
        "🐛 问题反馈": ["bug", "issue", "problem", "fix", "crash", "error", "问题", "故障"],
        "📊 市场数据": ["market", "share", "sales", "growth", "report", "份额", "销量"],
        "🔐 安全隐私": ["security", "privacy", "vulnerability", "patch", "安全", "隐私"],
        "🎮 功能体验": ["feature", "camera", "battery", "performance", "ai", "功能", "体验"],
    }

    for p in posts:
        title_lower = (p.get("title", "") + " " + p.get("content", "")).lower()
        for cat_name, keywords in CATEGORIES.items():
            if any(kw in title_lower for kw in keywords):
                highlight = {
                    "category": cat_name,
                    "title": p.get("title", ""),
                    "source": p.get("source", ""),
                    "url": p.get("url", ""),
                }
                # 去重
                if not any(h["title"] == highlight["title"] for h in highlights):
                    highlights.append(highlight)
                break

    # 最多返回 8 条
    return highlights[:8]


def export_data():
    """主导出流程"""
    print("=" * 50, flush=True)
    print(f"India Mobile Pulse - 数据导出", flush=True)
    print(f"时间: {datetime.now().isoformat()}", flush=True)
    print("=" * 50, flush=True)
    
    # 初始化数据库
    models.init_db()
    
    # 1. 采集（如果设置了 COLLECT 环境变量才采集，默认只导出已有数据）
    collect_results = {}
    if os.environ.get("COLLECT", "0") == "1":
        print("\n📥 开始采集...", flush=True)
        collect_results = run_all_collectors()
    else:
        print("\n📥 跳过采集（设置 COLLECT=1 启用）", flush=True)
    
    # 2. 分析（如果设置了 ANALYZE 环境变量才分析）
    analysis = None
    if os.environ.get("ANALYZE", "0") == "1":
        print("\n🧠 开始分析...", flush=True)
        analysis = run_analysis()
    else:
        print("\n🧠 跳过分析（设置 ANALYZE=1 启用）", flush=True)
    
    # 3. 获取统计数据
    print("\n📊 生成数据...", flush=True)
    stats = models.get_post_stats()
    recent_posts = models.get_posts(limit=500)
    recent_runs = models.get_recent_runs(20)
    latest_analysis = models.get_latest_analysis()
    analyses = models.get_analyses(5)
    
    # 4. 导出 JSON
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    os.makedirs(output_dir, exist_ok=True)
    
    # Dashboard 数据
    dashboard_data = {
        "stats": stats,
        "latest_analysis": latest_analysis,
        "recent_runs": recent_runs,
        "last_updated": datetime.now().isoformat(),
    }
    
    with open(os.path.join(output_dir, "dashboard.json"), "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ dashboard.json", flush=True)
    
    # 帖子数据
    posts_data = {
        "posts": recent_posts,
        "count": len(recent_posts),
    }
    with open(os.path.join(output_dir, "posts.json"), "w", encoding="utf-8") as f:
        json.dump(posts_data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ posts.json ({len(recent_posts)} 条)", flush=True)
    
    # 分析数据
    with open(os.path.join(output_dir, "analyses.json"), "w", encoding="utf-8") as f:
        json.dump({"analyses": analyses}, f, ensure_ascii=False, indent=2)
    print(f"  ✅ analyses.json", flush=True)
    
    # 品牌数据
    with open(os.path.join(output_dir, "brands.json"), "w", encoding="utf-8") as f:
        json.dump({"brands": stats.get("brand_mentions", {})}, f, ensure_ascii=False, indent=2)
    print(f"  ✅ brands.json", flush=True)
    
    # OS 日报数据
    os_daily = generate_os_daily(recent_posts)
    with open(os.path.join(output_dir, "os-daily.json"), "w", encoding="utf-8") as f:
        json.dump(os_daily, f, ensure_ascii=False, indent=2)
    print(f"  ✅ os-daily.json", flush=True)
    
    # 采集结果
    collect_summary = {}
    for name, result in collect_results.items():
        collect_summary[name] = {"status": result["status"], "count": result.get("count", 0)}
    
    print("\n" + "=" * 50, flush=True)
    print(f"✅ 导出完成！总帖子: {stats.get('total', 0)}", flush=True)
    print(f"   采集结果: {collect_summary}", flush=True)
    print("=" * 50, flush=True)


if __name__ == "__main__":
    export_data()
