"""
India Mobile Pulse - Flask Web App
印度手机圈热点搜集分析工具 - Web 服务
"""

import json
import logging
import threading
from flask import Flask, jsonify, render_template, request

import config
import models
from scheduler import start_scheduler, stop_scheduler, get_scheduler_status, run_collection, run_analysis

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 初始化数据库
models.init_db()

# 创建 Flask 应用
app = Flask(__name__)

# 启动调度器（Zeabur/Gunicorn 模式下模块导入时即启动）
start_scheduler()


# ============================================================
# 页面路由
# ============================================================

@app.route("/")
def index():
    """首页 - Dashboard"""
    return render_template("index.html")


# ============================================================
# API 路由
# ============================================================

@app.route("/api/dashboard")
def api_dashboard():
    """Dashboard 数据概览"""
    stats = models.get_post_stats()
    latest_analysis = models.get_latest_analysis()
    recent_runs = models.get_recent_runs(10)
    scheduler_status = get_scheduler_status()
    recent_posts = models.get_posts(limit=30)

    return jsonify({
        "stats": stats,
        "latest_analysis": latest_analysis,
        "recent_posts": recent_posts,
        "recent_runs": recent_runs,
        "scheduler": scheduler_status,
    })


@app.route("/api/posts")
def api_posts():
    """帖子列表（支持筛选）"""
    source = request.args.get("source")
    brand = request.args.get("brand")
    period = request.args.get("period", "all")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    posts = models.get_posts(
        source=source, brand=brand,
        period=period, limit=limit, offset=offset,
    )
    return jsonify({"posts": posts, "count": len(posts)})


@app.route("/api/analyses")
def api_analyses():
    """分析报告列表"""
    limit = request.args.get("limit", 10, type=int)
    analyses = models.get_analyses(limit)
    return jsonify({"analyses": analyses})


@app.route("/api/brands")
def api_brands():
    """品牌提及统计"""
    stats = models.get_post_stats()
    return jsonify({"brands": stats.get("brand_mentions", {})})


@app.route("/api/collect", methods=["POST"])
def api_collect():
    """手动触发采集"""
    source = request.args.get("source", "all")
    thread = threading.Thread(target=run_collection, args=(source,))
    thread.daemon = True
    thread.start()
    return jsonify({"status": "started", "source": source})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """手动触发分析"""
    thread = threading.Thread(target=run_analysis)
    thread.daemon = True
    thread.start()
    return jsonify({"status": "started"})


# ============================================================
# 启动
# ============================================================

def main():
    """启动应用（本地开发用）"""
    import os
    port = int(os.environ.get("PORT", config.FLASK_PORT))
    logger.info(f"India Mobile Pulse starting on http://0.0.0.0:{port}")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=config.FLASK_DEBUG,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
