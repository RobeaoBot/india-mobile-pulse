"""
India Mobile Pulse - Database Models & Operations
SQLite 数据模型与操作
"""

import os
import json
import hashlib
import sqlite3
from datetime import datetime
from contextlib import contextmanager

import config


def get_db_path():
    """获取数据库路径，确保目录存在"""
    db_dir = os.path.dirname(config.DATABASE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return config.DATABASE_PATH


@contextmanager
def get_connection():
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库表结构"""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                author TEXT DEFAULT '',
                url TEXT DEFAULT '',
                score INTEGER DEFAULT 0,
                brands TEXT DEFAULT '[]',
                os_tags TEXT DEFAULT '[]',
                hardware_tags TEXT DEFAULT '[]',
                sentiment TEXT DEFAULT 'neutral',
                published_at DATETIME,
                collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, source_id)
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_start DATETIME NOT NULL,
                period_end DATETIME NOT NULL,
                summary TEXT DEFAULT '',
                hot_topics TEXT DEFAULT '[]',
                brand_sentiment TEXT DEFAULT '{}',
                key_insights TEXT DEFAULT '[]',
                trending_keywords TEXT DEFAULT '[]',
                posts_analyzed INTEGER DEFAULT 0,
                provider TEXT DEFAULT 'rule',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS collection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                posts_count INTEGER DEFAULT 0,
                new_posts INTEGER DEFAULT 0,
                error_message TEXT DEFAULT '',
                started_at DATETIME NOT NULL,
                completed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source);
            CREATE INDEX IF NOT EXISTS idx_posts_collected ON posts(collected_at);
            CREATE INDEX IF NOT EXISTS idx_posts_published ON posts(published_at);
            CREATE INDEX IF NOT EXISTS idx_posts_brands ON posts(brands);
            CREATE INDEX IF NOT EXISTS idx_analyses_period ON analyses(period_start, period_end);
            CREATE INDEX IF NOT EXISTS idx_runs_source ON collection_runs(source);
        """)


# ============================================================
# Posts CRUD
# ============================================================

def insert_post(post: dict) -> bool:
    """插入单条帖子，返回是否为新记录"""
    with get_connection() as conn:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO posts 
                (source, source_id, title, content, author, url, score,
                 brands, os_tags, hardware_tags, sentiment, published_at, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post["source"],
                post["source_id"],
                post["title"],
                post.get("content", ""),
                post.get("author", ""),
                post.get("url", ""),
                post.get("score", 0),
                json.dumps(post.get("brands", []), ensure_ascii=False),
                json.dumps(post.get("os_tags", []), ensure_ascii=False),
                json.dumps(post.get("hardware_tags", []), ensure_ascii=False),
                post.get("sentiment", "neutral"),
                post.get("published_at"),
                datetime.now().isoformat(),
            ))
            return conn.total_changes > 0
        except sqlite3.IntegrityError:
            return False


def insert_posts(posts: list) -> int:
    """批量插入帖子，返回新增数量"""
    new_count = 0
    for post in posts:
        if insert_post(post):
            new_count += 1
    return new_count


def insert_posts_batch(posts: list) -> int:
    """
    批量插入帖子（单连接 executemany，性能远优于逐条 insert_posts）。
    返回实际新增数量（已存在的会被 INSERT OR IGNORE 跳过）。
    """
    if not posts:
        return 0

    now = datetime.now().isoformat()
    rows = []
    for p in posts:
        # source_id 兜底：为空时用 title+url 生成稳定哈希，避免唯一约束冲突
        source_id = p.get("source_id") or hashlib.md5(
            (p.get("title", "") + p.get("url", "")).encode("utf-8")
        ).hexdigest()
        rows.append((
            p["source"],
            source_id,
            p.get("title", ""),
            p.get("content", ""),
            p.get("author", ""),
            p.get("url", ""),
            p.get("score", 0),
            json.dumps(p.get("brands", []), ensure_ascii=False),
            json.dumps(p.get("os_tags", []), ensure_ascii=False),
            json.dumps(p.get("hardware_tags", []), ensure_ascii=False),
            p.get("sentiment", "neutral"),
            p.get("published_at"),
            now,
        ))

    with get_connection() as conn:
        before = conn.total_changes
        conn.executemany("""
            INSERT OR IGNORE INTO posts
            (source, source_id, title, content, author, url, score,
             brands, os_tags, hardware_tags, sentiment, published_at, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        return conn.total_changes - before


def get_posts(source=None, brand=None, period="all", limit=50, offset=0):
    """查询帖子列表"""
    query = "SELECT * FROM posts WHERE 1=1"
    params = []

    if source:
        query += " AND source = ?"
        params.append(source)

    if brand:
        query += " AND brands LIKE ?"
        params.append(f'%"{brand}"%')

    if period == "today":
        query += " AND date(collected_at) = date('now')"
    elif period == "yesterday":
        query += " AND date(collected_at) = date('now', '-1 day')"
    elif period == "week":
        query += " AND collected_at >= datetime('now', '-7 days')"

    query += " ORDER BY collected_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_all_for_sentiment():
    """获取全部帖子用于情感重算（只取必要字段，避免传输正文以外的大字段）"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT source, source_id, title, content, sentiment FROM posts"
        ).fetchall()
        return [dict(r) for r in rows]


def update_sentiments_batch(items: list) -> int:
    """
    批量更新情感标签。

    :param items: [(sentiment, source, source_id), ...]
    :return: 受影响行数
    """
    if not items:
        return 0
    with get_connection() as conn:
        before = conn.total_changes
        conn.executemany(
            "UPDATE posts SET sentiment = ? WHERE source = ? AND source_id = ?",
            items,
        )
        return conn.total_changes - before


def get_posts_for_analysis(hours=24):
    """获取指定时间范围内的帖子用于分析"""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT source, title, content, author, score, brands, sentiment, published_at
            FROM posts 
            WHERE collected_at >= datetime('now', ?)
            ORDER BY score DESC, collected_at DESC
        """, (f"-{hours} hours",)).fetchall()
        return [dict(r) for r in rows]


def get_post_stats():
    """获取帖子统计"""
    with get_connection() as conn:
        stats = {}
        
        # 总数 & 今日
        row = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN date(collected_at) = date('now') THEN 1 ELSE 0 END) as today
            FROM posts
        """).fetchone()
        stats["total"] = row["total"]
        stats["today"] = row["today"]

        # 按来源
        rows = conn.execute("""
            SELECT source, COUNT(*) as count 
            FROM posts 
            GROUP BY source
        """).fetchall()
        stats["by_source"] = {r["source"]: r["count"] for r in rows}

        # 品牌提及
        rows = conn.execute("SELECT brands FROM posts WHERE brands != '[]'").fetchall()
        brand_counts = {}
        for r in rows:
            try:
                brands = json.loads(r["brands"])
                for b in brands:
                    brand_counts[b] = brand_counts.get(b, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass
        stats["brand_mentions"] = dict(
            sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)
        )

        # 整体情感（近 24 小时）
        rows = conn.execute("""
            SELECT sentiment, COUNT(*) as count 
            FROM posts 
            WHERE collected_at >= datetime('now', '-24 hours')
            GROUP BY sentiment
        """).fetchall()
        stats["sentiment"] = {r["sentiment"]: r["count"] for r in rows}

        # "有态度"口径：绝大多数科技新闻是客观陈述（发布、参数、价格），
        # 本身并无情感倾向。若以全部帖子为分母，正面占比会被稀释到接近 0，
        # 指标就失去了意义。这里额外给出"仅在表达了倾向的帖子中"的比例，
        # 前端据此展示，避免误读为"全网口碑极差"。
        pos = stats["sentiment"].get("positive", 0)
        neg = stats["sentiment"].get("negative", 0)
        voiced = pos + neg
        stats["sentiment_voiced"] = {
            "total": voiced,
            "positive": pos,
            "negative": neg,
            "positive_pct": round(pos / voiced * 100) if voiced else 0,
            "negative_pct": round(neg / voiced * 100) if voiced else 0,
        }

        return stats


# ============================================================
# Analyses CRUD
# ============================================================

def insert_analysis(analysis: dict) -> int:
    """插入分析结果，返回ID"""
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO analyses 
            (period_start, period_end, summary, hot_topics, brand_sentiment,
             key_insights, trending_keywords, posts_analyzed, provider)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis["period_start"],
            analysis["period_end"],
            analysis.get("summary", ""),
            json.dumps(analysis.get("hot_topics", []), ensure_ascii=False),
            json.dumps(analysis.get("brand_sentiment", {}), ensure_ascii=False),
            json.dumps(analysis.get("key_insights", []), ensure_ascii=False),
            json.dumps(analysis.get("trending_keywords", []), ensure_ascii=False),
            analysis.get("posts_analyzed", 0),
            analysis.get("provider", "rule"),
        ))
        return cursor.lastrowid


def get_latest_analysis():
    """获取最新一条分析"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM analyses ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_analyses(limit=10):
    """获取分析列表"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# Collection Runs
# ============================================================

def log_collection_run(source: str, status: str, posts_count: int = 0,
                       new_posts: int = 0, error_message: str = "",
                       started_at: str = None):
    """记录采集运行日志"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO collection_runs 
            (source, status, posts_count, new_posts, error_message, started_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source, status, posts_count, new_posts, error_message,
              started_at or datetime.now().isoformat()))


def get_recent_runs(limit=20):
    """获取最近的采集运行记录"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM collection_runs ORDER BY started_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
