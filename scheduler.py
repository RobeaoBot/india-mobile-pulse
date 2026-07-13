"""
India Mobile Pulse - Task Scheduler
定时任务调度器：每天 12:00 自动采集 + 分析
"""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config
import models
from collectors.reddit import RedditCollector
from collectors.youtube import YouTubeCollector
from collectors.news import NewsCollector
from collectors.official import OfficialCollector
from analyzer.llm import analyze_posts

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def run_collection(source: str = "all"):
    """执行数据采集"""
    collectors = {
        "reddit": RedditCollector,
        "youtube": YouTubeCollector,
        "news": NewsCollector,
        "official": OfficialCollector,
    }

    if source == "all":
        targets = list(collectors.items())
    elif source in collectors:
        targets = [(source, collectors[source])]
    else:
        logger.error(f"未知采集源: {source}")
        return

    for name, CollectorClass in targets:
        started_at = datetime.now().isoformat()
        try:
            logger.info(f"[Scheduler] 开始采集: {name}")
            collector = CollectorClass()
            posts = collector.collect()
            new_count = models.insert_posts(posts)
            models.log_collection_run(
                source=name, status="success",
                posts_count=len(posts), new_posts=new_count,
                started_at=started_at,
            )
            logger.info(f"[Scheduler] {name} 采集完成: {len(posts)}条, 新增{new_count}条")
        except Exception as e:
            logger.error(f"[Scheduler] {name} 采集失败: {e}")
            models.log_collection_run(
                source=name, status="error",
                error_message=str(e), started_at=started_at,
            )


def run_analysis():
    """执行分析"""
    try:
        logger.info("[Scheduler] 开始分析")
        result = analyze_posts()
        if result:
            logger.info(f"[Scheduler] 分析完成, ID={result.get('id')}")
        else:
            logger.info("[Scheduler] 无数据可供分析")
    except Exception as e:
        logger.error(f"[Scheduler] 分析失败: {e}")


def run_collect_and_analyze():
    """采集 + 分析（串行执行）"""
    run_collection("all")
    run_analysis()


def start_scheduler():
    """启动定时任务调度器"""
    hour, minute = map(int, config.DAILY_COLLECTION_TIME.split(":"))

    # 每天 12:00 定时采集+分析
    scheduler.add_job(
        run_collect_and_analyze,
        CronTrigger(hour=hour, minute=minute),
        id="daily_collect_and_analyze",
        name=f"每日采集与分析 ({config.DAILY_COLLECTION_TIME})",
        replace_existing=True,
    )

    # 启动时若数据库为空，立即执行首次采集
    try:
        stats = models.get_post_stats()
        if stats.get("total", 0) == 0:
            scheduler.add_job(
                run_collect_and_analyze,
                id="initial_collect",
                name="首次采集（数据库为空）",
                replace_existing=True,
            )
            logger.info("[Scheduler] 数据库为空，将执行首次采集")
    except Exception:
        scheduler.add_job(
            run_collect_and_analyze,
            id="initial_collect",
            name="首次采集",
            replace_existing=True,
        )

    scheduler.start()
    logger.info(
        f"[Scheduler] 调度器已启动，每日 {config.DAILY_COLLECTION_TIME} 自动采集"
    )


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[Scheduler] 调度器已停止")


def get_scheduler_status():
    """获取调度状态"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return {
        "running": scheduler.running,
        "jobs": jobs,
    }
