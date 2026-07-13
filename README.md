# India Mobile Pulse 🇮🇳📱

印度手机圈热点搜集分析工具 - 自动追踪印度手机市场的热门话题和品牌动态

## 功能

- 🔍 **4源自动采集**: Reddit / YouTube / Google News / 官方渠道
- 🧠 **智能分析**: 规则引擎 + LLM 可选
- 📊 **暗色 Dashboard**: 品牌/来源筛选，一键查看
- ⏰ **定时任务**: 每日自动采集+分析
- 🐳 **一键部署**: Docker / Render / Hugging Face Spaces

## 快速开始

```bash
pip install -r requirements.txt
python app.py
```

访问 http://localhost:5000

## 部署

详见 [DEPLOY.md](DEPLOY.md)

## 数据来源

| 来源 | 类型 | 说明 |
|------|------|------|
| Reddit | 社区 | r/india, r/IndiaSpeaks 等子版 |
| YouTube | 视频 | 印度科技频道 |
| Google News | 新闻 | 印度手机相关新闻 |
| 官方渠道 | 公告 | 品牌官方新闻稿 |
