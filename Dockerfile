FROM python:3.11-slim

LABEL maintainer="India Mobile Pulse"
LABEL description="Indian Mobile Market Pulse Monitor"

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

# Hugging Face Spaces 使用 7860 端口
ENV PORT=7860
EXPOSE 7860

# 数据持久化卷
VOLUME ["/app/data"]

# 健康检查
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s \
    CMD curl -f http://localhost:7860/api/dashboard || exit 1

# 使用 Gunicorn 运行（单 worker，因 APScheduler + SQLite 限制）
CMD ["gunicorn", \
     "--workers", "1", \
     "--bind", "0.0.0.0:7860", \
     "--timeout", "300", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "wsgi:app"]
