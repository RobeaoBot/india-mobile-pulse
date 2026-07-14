"""
India Mobile Pulse - Hugging Face Spaces 入口
通过 Gradio SDK 启动，内部运行 Flask 应用
"""

import os
import threading
import time
import gradio as gr
import requests

# 初始化数据库和调度器
import models
from scheduler import start_scheduler, run_collection, run_analysis

models.init_db()
start_scheduler()


def get_dashboard_html():
    """从 Flask 内部获取 Dashboard HTML"""
    try:
        # 启动 Flask 在后台端口
        resp = requests.get("http://127.0.0.1:7861/", timeout=5)
        return resp.text
    except Exception:
        return "<h2>⏳ 服务启动中，请稍等几秒后刷新...</h2>"


def get_dashboard_data():
    """获取 Dashboard 数据摘要"""
    try:
        resp = requests.get("http://127.0.0.1:7861/api/dashboard", timeout=5)
        data = resp.json()
        stats = data.get("stats", {})
        scheduler = data.get("scheduler", {})
        return (
            f"📊 **总帖子**: {stats.get('total', 0)} | "
            f"**今日**: {stats.get('today', 0)} | "
            f"**Reddit**: {stats.get('by_source', {}).get('reddit', 0)} | "
            f"**YouTube**: {stats.get('by_source', {}).get('youtube', 0)} | "
            f"**News**: {stats.get('by_source', {}).get('news', 0)} | "
            f"**Official**: {stats.get('by_source', {}).get('official', 0)}\n\n"
            f"⏰ 调度器: {'✅ 运行中' if scheduler.get('running') else '❌ 停止'} | "
            f"下次采集: {scheduler.get('next_run', '--')}"
        )
    except Exception as e:
        return f"⏳ 服务启动中... ({e})"


def trigger_collect(source):
    """手动触发采集"""
    try:
        resp = requests.post(
            f"http://127.0.0.1:7861/api/collect?source={source}", timeout=5
        )
        return "✅ 采集已启动，数据将在1-2分钟后更新"
    except Exception as e:
        return f"❌ 采集失败: {e}"


def trigger_analyze():
    """手动触发分析"""
    try:
        resp = requests.post("http://127.0.0.1:7861/api/analyze", timeout=5)
        return "✅ 分析已启动"
    except Exception as e:
        return f"❌ 分析失败: {e}"


# 在后台线程启动 Flask 应用
def run_flask():
    from app import app
    app.run(host="127.0.0.1", port=7861, use_reloader=False)


flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
time.sleep(2)  # 等 Flask 启动


# ============================================================
# Gradio 界面
# ============================================================

with gr.Blocks(
    title="India Mobile Pulse",
    theme=gr.themes.Soft(primary_hue="teal"),
    css="""
    .main-title { text-align: center; margin-bottom: 10px; }
    .iframe-container { width: 100%; height: 80vh; border: none; }
    """
) as demo:
    gr.Markdown(
        "# 📡 India Mobile Pulse\n"
        "### 印度手机圈热点监测 | Indian Mobile Market Pulse Monitor",
        elem_classes=["main-title"]
    )

    with gr.Row():
        refresh_btn = gr.Button("⟳ 刷新数据", variant="secondary")
        collect_btn = gr.Button("📥 采集数据", variant="primary")
        analyze_btn = gr.Button("🧠 智能分析", variant="stop")

    status_box = gr.Markdown(value=get_dashboard_data())

    # 内嵌 Flask Dashboard
    gr.HTML(
        value=lambda: f'<iframe src="http://127.0.0.1:7861/" '
                      f'style="width:100%;height:80vh;border:1px solid #333;border-radius:8px;"></iframe>'
    )

    # 按钮事件
    refresh_btn.click(
        fn=get_dashboard_data,
        outputs=status_box
    )
    collect_btn.click(
        fn=lambda: (trigger_collect("all"), get_dashboard_data())[1],
        outputs=status_box
    )
    analyze_btn.click(
        fn=lambda: (trigger_analyze(), get_dashboard_data())[1],
        outputs=status_box
    )

    # 每 60 秒自动刷新状态
    demo.load(fn=get_dashboard_data, outputs=status_box, every=60)


demo.launch(server_name="0.0.0.0", server_port=7860)
