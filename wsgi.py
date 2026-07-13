"""
India Mobile Pulse - Production WSGI Entry
使用 Gunicorn 运行的生产入口
"""

import logging

import models
from scheduler import start_scheduler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# 初始化数据库
models.init_db()

# 启动调度器
start_scheduler()

# 导入 Flask 应用
from app import app

# Gunicorn 启动命令:
# gunicorn -w 1 -b 0.0.0.0:5000 --timeout 300 wsgi:app
# 注意: 只能用 1 worker，因为 APScheduler 和 SQLite 不支持多进程
