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

TEMP_POSTS_FILE = "/tmp/collected_posts.json"


def run_all_collectors():
    """运行所有采集器"""
    collectors = [
        ("reddit", RedditCollector()),
        ("youtube", YouTubeCollector()),
        ("news", NewsCollector()),
        ("official", OfficialCollector()),
    ]

    results = {}
    all_posts = []
    for name, collector in collectors:
        try:
            print(f"  采集 {name}...", flush=True)
            posts = collector.collect()
            results[name] = {"status": "success", "count": len(posts), "posts": posts}
            all_posts.extend(posts)
            print(f"  ✅ {name}: {len(posts)} 条", flush=True)
        except Exception as e:
            results[name] = {"status": "error", "error": str(e), "posts": []}
            print(f"  ❌ {name}: {e}", flush=True)

    # 保存所有帖子到临时文件，供分析步骤使用（不依赖数据库）
    with open(TEMP_POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_posts, f, ensure_ascii=False)
    print(f"  📦 已保存 {len(all_posts)} 条帖子到临时文件", flush=True)

    return results


def run_analysis():
    """运行分析"""
    try:
        print("  运行分析...", flush=True)

        # 优先从临时 JSON 文件读取帖子（GitHub Actions 环境）
        posts = None
        if os.path.exists(TEMP_POSTS_FILE):
            try:
                with open(TEMP_POSTS_FILE, "r", encoding="utf-8") as f:
                    posts = json.load(f)
                print(f"  📖 从临时文件加载了 {len(posts)} 条帖子", flush=True)
            except Exception as e:
                print(f"  ⚠️ 临时文件读取失败: {e}", flush=True)

        result = analyze_posts(posts=posts)
        if result:
            print(f"  ✅ 分析完成（{result.get('posts_analyzed', 0)} 条帖子）", flush=True)
        else:
            print(f"  ⚠️ 没有帖子可供分析", flush=True)
        return result
    except Exception as e:
        print(f"  ❌ 分析失败: {e}", flush=True)
        import traceback
        traceback.print_exc()
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
                    "title_cn": _quick_translate(p.get("title", "")),
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
    """生成详细中文摘要 — 多维度归纳"""
    name = cfg["name_cn"]
    count = len(posts)

    if count == 0:
        return f"今日暂无{name}相关动态。"

    # ---- 1. 概况 ----
    if total > 0:
        pos_pct = round(sentiment["positive"] / total * 100)
        neg_pct = round(sentiment["negative"] / total * 100)
        if pos_pct >= 50:
            mood = "整体氛围积极乐观"
        elif pos_pct >= 30:
            mood = "舆论态度偏中性"
        else:
            mood = "以中性讨论为主"
    else:
        pos_pct = neg_pct = 0
        mood = "暂无情感数据"

    top_brands_list = [b for b, _ in brands.most_common(5)]
    brand_str = "、".join(top_brands_list) if top_brands_list else "多个品牌"

    lines = []
    lines.append(f"📊 {name}生态今日共有 {count} 条相关讨论，{mood}。")
    lines.append(f"📈 情感分布：正面 {pos_pct}% / 负面 {neg_pct}% / 中性 {100-pos_pct-neg_pct}%。")
    if top_brands_list:
        lines.append(f"🏷️ 热门品牌：{brand_str}。")

    # ---- 2. 按分类归纳亮点 ----
    CATEGORIES = {
        "新品发布": ["launch", "release", "announce", "unveil", "reveal", "发布", "推出"],
        "系统更新": ["update", "upgrade", "beta", "stable", "rollout", "更新", "升级"],
        "问题反馈": ["bug", "issue", "problem", "fix", "crash", "error", "问题", "故障"],
        "市场数据": ["market", "share", "sales", "growth", "report", "份额", "销量"],
        "安全隐私": ["security", "privacy", "vulnerability", "patch", "安全", "隐私"],
        "功能体验": ["feature", "camera", "battery", "performance", "ai", "功能", "体验"],
    }

    cat_posts = {}
    for p in posts:
        text = (p.get("title", "") + " " + p.get("content", "")).lower()
        for cat_name, keywords in CATEGORIES.items():
            if any(kw in text for kw in keywords):
                cat_posts.setdefault(cat_name, []).append(p)
                break

    for cat_name, cat_list in cat_posts.items():
        cat_count = len(cat_list)
        # 取前3条最相关标题，翻译为中文摘要
        sample_titles = [p.get("title", "") for p in cat_list[:3]]
        sample_cn = [_quick_translate(t) for t in sample_titles]
        detail = "；".join(sample_cn)
        if cat_count > 3:
            detail += f"等{cat_count}条相关报道"
        icon_map = {
            "新品发布": "🆕", "系统更新": "🔄", "问题反馈": "🐛",
            "市场数据": "📊", "安全隐私": "🔐", "功能体验": "🎮",
        }
        icon = icon_map.get(cat_name, "📌")
        lines.append(f"{icon} 【{cat_name}】共{cat_count}条 — {detail}")

    # ---- 3. 关注焦点 ----
    # 取得分最高或最新2条
    focus_posts = sorted(posts, key=lambda p: p.get("score", 0), reverse=True)[:3]
    if not focus_posts:
        focus_posts = posts[:3]
    focus_strs = []
    for fp in focus_posts:
        focus_strs.append(_quick_translate(fp.get("title", "")))
    if focus_strs:
        lines.append(f"🔥 关注焦点：{'；'.join(focus_strs)}")

    return "\n".join(lines)


def _quick_translate(title):
    """英文标题翻译为中文简述（基于实体+动作的结构化翻译，不做逐词替换）"""
    if not title:
        return ""
    
    # 实体识别
    entities = []
    entity_map = [
        # OS 版本（长词优先）
        ("Android 17", "Android 17"), ("Android 16", "Android 16"),
        ("iOS 27", "iOS 27"), ("iOS 26.3", "iOS 26.3"), ("iOS 26", "iOS 26"),
        ("HarmonyOS 6", "鸿蒙6"), ("HarmonyOS 5.1", "鸿蒙5.1"),
        ("HarmonyOS 5.0", "鸿蒙5.0"), ("HarmonyOS 3", "鸿蒙3"),
        # 品牌
        ("Samsung", "三星"), ("Google", "谷歌"), ("Apple", "苹果"),
        ("OnePlus", "一加"), ("Xiaomi", "小米"), ("Huawei", "华为"),
        ("Motorola", "摩托罗拉"), ("Pixel", "Pixel"), ("Honor", "荣耀"),
        ("Oppo", "OPPO"), ("Vivo", "vivo"), ("Realme", "真我"),
        ("Nothing", "Nothing"), ("Infinix", "传音"), ("Tecno", "Tecno"),
        ("Toyota", "丰田"),
        # OS 定制系统
        ("OxygenOS 16", "OxygenOS 16"), ("OxygenOS", "OxygenOS"),
        ("OriginOS 6", "OriginOS 6"), ("OriginOS", "OriginOS"),
        ("One UI", "One UI"), ("ColorOS", "ColorOS"), ("MIUI", "MIUI"),
        ("FunTouch OS", "FunTouch OS"), ("Realme UI", "Realme UI"),
        ("Nothing OS", "Nothing OS"),
        # 通用 OS
        ("HarmonyOS", "鸿蒙"), ("Android", "Android"), ("iOS", "iOS"),
        # 产品线
        ("iPhone 17 Pro", "iPhone 17 Pro"), ("iPhone", "iPhone"),
        ("Ultimate Design", "至尊版"),
        ("Galaxy S26", "Galaxy S26"),
        # 应用/产品
        ("XChat", "XChat"), ("BGMI", "BGMI"), ("Amazfit", "Amazfit"),
        ("Kagi News", "Kagi News"), ("Google News", "Google News"),
        ("Apple TV", "Apple TV"),
        ("Qi2", "Qi2"),
    ]
    
    title_lower = title.lower()
    for en, cn in entity_map:
        if en.lower() in title_lower and cn not in entities:
            entities.append(cn)
    
    # 动作识别
    action = ""
    action_map = [
        # 长短语优先
        ("preparing to officially launch", "准备正式发布"),
        ("set to launch", "即将发布"),
        ("is coming to", "即将登陆"),
        ("is in the works", "正在开发中"),
        ("could finally fix", "终于有望修复"),
        ("gets official rollout date", "获官方推送日期"),
        ("made new installation record", "创下安装新纪录"),
        ("officially announces", "正式宣布"),
        ("announces", "宣布"),
        ("reveals", "公布"), ("revealed", "公布"),
        ("launching", "即将发布"), ("launch", "发布"),
        ("announced", "宣布"), ("announce", "宣布"),
        ("unveiled", "发布"), ("unveil", "发布"),
        ("released", "发布"), ("release", "发布"),
        ("update", "更新"), ("upgrade", "升级"),
        ("rollout", "推送"), ("rolling out", "推送"),
        ("fix", "修复"),
        ("confirmed", "确认"), ("confirms", "确认"),
        ("introduces", "引入"),
        ("refreshed with", "更新获得"),
        ("added to", "添加至"),
    ]
    
    for kw, cn in action_map:
        if kw in title_lower:
            action = cn
            break
    
    # 主题/对象识别
    topic = ""
    topic_map = [
        ("smartphone os guide", "智能手机操作系统指南"),
        ("smartphone", "智能手机"), ("phone", "手机"), ("pc", "电脑"),
        ("tablet", "平板"), ("foldable", "折叠屏"),
        ("battery", "电池"), ("camera", "相机"), ("display", "屏幕"),
        ("security", "安全功能"), ("privacy", "隐私"),
        ("encrypted chats", "加密聊天"), ("encrypted", "加密"),
        ("market share", "市场份额"), ("sales", "销量"),
        ("open source", "开源"),
        ("wireless charging", "无线充电"),
        ("ui upgrades", "UI升级"),
        ("feature pack", "功能包"), ("features", "功能"),
        ("beta", "测试版"), ("stable", "稳定版"),
        ("timeline", "时间表"),
        ("eligible devices", "适配机型"), ("eligible phones", "适配机型"),
        ("skins, ranked", "定制系统排名"), ("skins", "定制系统"),
        ("smart ecosystem", "智能生态"),
        ("notification forwarding", "通知转发"),
        ("live pro sports", "职业体育直播"),
        ("messaging", "消息互通"),
    ]
    
    for kw, cn in topic_map:
        if kw in title_lower:
            topic = cn
            break
    
    # 地区/范围
    region = ""
    region_map = [
        ("for india", "印度"), ("in india", "印度"),
        ("for eu", "欧盟"), ("for smartphones", "智能手机版"),
    ]
    for kw, cn in region_map:
        if kw in title_lower:
            region = cn
            break
    
    # 组装中文简述
    parts = []
    if entities:
        parts.append("".join(entities[:3]))  # 最多3个实体
    if action:
        parts.append(action)
    if topic:
        parts.append(topic)
    if region:
        parts.append(f"（{region}）")
    
    if parts:
        # 用自然语言连接各部分
        result = ""
        # 实体之间用顿号分隔，去重
        seen = set()
        unique_ents = []
        for e in entities[:3]:
            if e not in seen:
                seen.add(e)
                unique_ents.append(e)
        ent_str = "、".join(unique_ents) if unique_ents else ""
        if ent_str and action and topic:
            result = f"{ent_str}{action}{topic}{f'（{region}）' if region else ''}"
        elif ent_str and action:
            result = f"{ent_str}{action}{f'（{region}）' if region else ''}"
        elif ent_str and topic:
            result = f"{ent_str}{topic}{f'（{region}）' if region else ''}"
        elif ent_str:
            result = f"{ent_str}相关动态{f'（{region}）' if region else ''}"
        else:
            result = "".join(parts)
    else:
        # 兜底：保留原文前50字符
        result = title[:50] + ("..." if len(title) > 50 else "")
    
    return result


def _extract_highlights(posts):
    """从帖子中提取亮点（中文归纳 + 中文标题翻译）"""
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
                title_en = p.get("title", "")
                title_cn = _quick_translate(title_en)
                highlight = {
                    "category": cat_name,
                    "title": title_en,
                    "title_cn": title_cn,
                    "source": p.get("source", ""),
                    "url": p.get("url", ""),
                }
                # 去重
                if not any(h["title"] == highlight["title"] for h in highlights):
                    highlights.append(highlight)
                break

    # 最多返回 10 条
    return highlights[:10]


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
    
    # 包含本次刚生成的分析结果（如果 DB 中没有则用内存中的）
    if analysis and analysis not in analyses:
        analyses = [analysis] + analyses[:4]  # 最多保留5条
    latest_analysis = analysis or latest_analysis

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
    
    # 分析数据（包含本次分析）
    with open(os.path.join(output_dir, "analyses.json"), "w", encoding="utf-8") as f:
        json.dump({"analyses": analyses}, f, ensure_ascii=False, indent=2)
    print(f"  ✅ analyses.json ({len(analyses)} 条)", flush=True)
    
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
