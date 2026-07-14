"""
India Mobile Pulse - Report Generator
从数据库中提取数据，生成 Markdown 格式的内部报告

用法：
    python report_generator.py                 # 生成最新报告
    python report_generator.py --hours 48      # 指定回溯小时数
    python report_generator.py --output custom.md  # 指定输出文件名
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import models


def generate_report(hours: int = None, output: str = None) -> str:
    """生成 Markdown 格式的市场报告"""

    hours = hours or 24 * 30  # 默认回溯30天
    now = datetime.now()

    # ── 获取数据 ──
    stats = models.get_post_stats()
    posts = models.get_posts(limit=500)
    analyses = models.get_analyses(1)
    runs = models.get_recent_runs(10)

    # ── 品牌统计 ──
    brand_counter = Counter()
    brand_sentiments = {}
    for p in posts:
        try:
            brands = json.loads(p.get("brands", "[]"))
        except (json.JSONDecodeError, TypeError):
            brands = []
        sentiment = p.get("sentiment", "neutral")
        for b in brands:
            brand_counter[b] += 1
            if b not in brand_sentiments:
                brand_sentiments[b] = {"positive": 0, "negative": 0, "neutral": 0}
            brand_sentiments[b][sentiment] = brand_sentiments[b].get(sentiment, 0) + 1

    # ── OS 统计 ──
    os_counter = Counter()
    for p in posts:
        try:
            os_tags = json.loads(p.get("os_tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            os_tags = []
        for o in os_tags:
            os_counter[o] += 1

    # ── 硬件统计 ──
    hw_counter = Counter()
    for p in posts:
        try:
            hw_tags = json.loads(p.get("hardware_tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            hw_tags = []
        for h in hw_tags:
            hw_counter[h] += 1

    # ── 情感统计 ──
    sentiment_counter = Counter(p.get("sentiment", "neutral") for p in posts)
    total_sent = sum(sentiment_counter.values()) or 1

    # ── 来源统计 ──
    source_counter = Counter(p.get("source", "unknown") for p in posts)

    # ── 构建报告 ──
    lines = []
    w = lines.append

    w(f"# 印度手机市场走访 · 内部报告")
    w("")
    w(f"> **报告编号**：IMP-{now.strftime('%Y-W%W')}")
    w(f"> **数据采集日期**：{now.strftime('%Y-%m-%d')}")
    w(f"> **报告输出日期**：{now.strftime('%Y年%m月%d日')}")
    w(f"> **数据来源**：India Mobile Pulse 监测系统（Reddit / YouTube / Google News / 官方RSS）")
    w(f"> **分析样本**：{len(posts)} 条帖子/新闻/视频，覆盖 {len(brand_counter)} 个品牌")
    w(f"> **密级**：内部使用")
    w("")
    w("---")
    w("")

    # === 一、执行摘要 ===
    w("## 一、执行摘要")
    w("")
    top_brands = brand_counter.most_common(5)
    brand_str = "、".join([f"{b}({c}次)" for b, c in top_brands])
    w(f"本期监测到 {len(posts)} 条内容，覆盖 {len(brand_counter)} 个品牌。")
    w(f"声量最高的品牌为：{brand_str}。")
    w("")
    if analyses:
        latest = analyses[0]
        summary = latest.get("summary", "")
        if summary:
            w(f"**系统分析摘要**：{summary}")
            w("")
    w("---")
    w("")

    # === 二、数据采集概况 ===
    w("## 二、数据采集概况")
    w("")
    w("| 采集来源 | 采集条数 | 占比 |")
    w("|---------|---------|------|")
    for source, count in source_counter.most_common():
        pct = count / len(posts) * 100
        w(f"| {source} | {count} | {pct:.1f}% |")
    w(f"| **合计** | **{len(posts)}** | **100%** |")
    w("")

    if runs:
        w("**最近采集运行记录**：")
        w("")
        w("| 来源 | 状态 | 采集条数 | 新增条数 | 时间 |")
        w("|-----|------|---------|---------|------|")
        for r in runs[:5]:
            w(f"| {r['source']} | {'✅' if r['status']=='success' else '❌'} {r['status']} | {r['posts_count']} | {r['new_posts']} | {r['started_at'][:19]} |")
        w("")
    w("---")
    w("")

    # === 三、品牌竞争格局 ===
    w("## 三、品牌竞争格局")
    w("")
    w("### 3.1 品牌声量排行")
    w("")
    w("| 排名 | 品牌 | 提及次数 | 占比 | 情感倾向 |")
    w("|-----|------|---------|------|---------|")
    for i, (brand, count) in enumerate(brand_counter.most_common(15), 1):
        pct = count / len(posts) * 100
        s = brand_sentiments.get(brand, {})
        pos, neg, neu = s.get("positive", 0), s.get("negative", 0), s.get("neutral", 0)
        if pos > neg:
            sentiment = "正面"
        elif neg > pos:
            sentiment = "负面"
        else:
            sentiment = "中性"
        w(f"| {i} | **{brand}** | {count} | {pct:.1f}% | {sentiment} |")
    w("")
    w("---")
    w("")

    # === 四、操作系统格局 ===
    w("## 四、操作系统与生态格局")
    w("")
    if os_counter:
        w("| 操作系统 | 提及次数 | 占比 |")
        w("|---------|---------|------|")
        for os_name, count in os_counter.most_common():
            pct = count / len(posts) * 100
            w(f"| {os_name} | {count} | {pct:.1f}% |")
    else:
        w("暂无 OS 标签数据。")
    w("")
    w("---")
    w("")

    # === 五、硬件技术趋势 ===
    w("## 五、硬件技术趋势")
    w("")
    if hw_counter:
        w("| 硬件关键词 | 提及次数 |")
        w("|-----------|---------|")
        for hw, count in hw_counter.most_common(10):
            w(f"| {hw} | {count} |")
    else:
        w("暂无硬件标签数据。")
    w("")
    w("---")
    w("")

    # === 六、消费者情感分析 ===
    w("## 六、消费者情感分析")
    w("")
    w("| 情感类型 | 帖子数 | 占比 |")
    w("|---------|-------|------|")
    for s in ["positive", "negative", "neutral"]:
        count = sentiment_counter.get(s, 0)
        pct = count / total_sent * 100
        label = {"positive": "正面", "negative": "负面", "neutral": "中性"}[s]
        w(f"| {label} | {count} | {pct:.1f}% |")
    w("")
    w("---")
    w("")

    # === 七、热门话题 ===
    w("## 七、热门帖子 TOP 10")
    w("")
    w("| # | 来源 | 标题 | 品牌 | 情感 | 发布时间 |")
    w("|---|------|------|------|------|---------|")
    sorted_posts = sorted(
        posts,
        key=lambda x: (x.get("score", 0), x.get("published_at") or x.get("collected_at", "")),
        reverse=True,
    )
    for i, p in enumerate(sorted_posts[:10], 1):
        title = p.get("title", "")[:60]
        brands = json.loads(p.get("brands", "[]")) if p.get("brands") else []
        brand_str = ", ".join(brands) if brands else "—"
        sentiment = p.get("sentiment", "neutral")
        pub = (p.get("published_at") or "")[:10]
        w(f"| {i} | {p.get('source', '')} | {title} | {brand_str} | {sentiment} | {pub} |")
    w("")
    w("---")
    w("")

    # === 八、关键洞察 ===
    w("## 八、关键洞察")
    w("")
    insights = []
    if top_brands:
        insights.append(f"品牌声量前三：{', '.join([b for b, _ in top_brands[:3]])}")
    if os_counter:
        top_os = os_counter.most_common(3)
        insights.append(f"OS 热度排名：{', '.join([f'{o}({c}次)' for o, c in top_os])}")
    if hw_counter:
        top_hw = hw_counter.most_common(3)
        insights.append(f"硬件热点：{', '.join([f'{h}({c}次)' for h, c in top_hw])}")
    pos_pct = sentiment_counter.get("positive", 0) / total_sent * 100
    neg_pct = sentiment_counter.get("negative", 0) / total_sent * 100
    insights.append(f"整体情感：正面 {pos_pct:.1f}% / 负面 {neg_pct:.1f}% / 中性 {100-pos_pct-neg_pct:.1f}%")

    for i, insight in enumerate(insights, 1):
        w(f"{i}. {insight}")
    w("")
    w("---")
    w("")

    # === 附录 ===
    w("## 附录：数据来源配置")
    w("")
    w(f"- Reddit 子版块：{', '.join(config.REDDIT_SUBREDDITS)}")
    w(f"- YouTube 频道：{len(config.YOUTUBE_CHANNEL_IDS)} 个印度科技博主")
    w(f"- Google News 关键词：{len(config.NEWS_QUERIES)} 组")
    w(f"- 官方 RSS 源：{len(config.OFFICIAL_RSS_SOURCES)} 个")
    w(f"- 品牌/关键词覆盖：{len(config.BRAND_KEYWORDS)} 个品牌")
    w("")
    w("---")
    w("")
    w(f"*本报告由 India Mobile Pulse 监测系统自动采集数据并生成。生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}*")

    report = "\n".join(lines)

    # ── 写入文件 ──
    if output is None:
        output = f"印度手机市场走访内部报告_{now.strftime('%Y-%m-%d')}.md"

    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, output)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ 报告已生成：{report_path}")
    print(f"   样本量：{len(posts)} 条 | 品牌：{len(brand_counter)} 个 | 来源：{len(source_counter)} 个")
    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="印度手机市场报告生成器")
    parser.add_argument("--hours", type=int, default=None, help="回溯小时数（默认30天）")
    parser.add_argument("--output", type=str, default=None, help="输出文件名")
    args = parser.parse_args()

    generate_report(hours=args.hours, output=args.output)
