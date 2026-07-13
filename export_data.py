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
    recent_posts = models.get_posts(limit=100)
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
