# India Mobile Pulse - 部署指南

## 方案一：VPS 直接部署（Python + Gunicorn + Nginx）

适用场景：有一台 Linux 服务器（VPS/云主机），直接部署，无需 Docker。

---

## 📋 前置要求

| 项目 | 最低要求 |
|------|---------|
| 服务器 | 1核 1GB 内存即可（非常轻量） |
| 系统 | Ubuntu 20.04+ / Debian 11+ |
| 网络 | 能访问外网（Google News 等 RSS 源） |
| 域名 | 可选，没有也能用 IP 访问 |

**推荐云服务商（低价 VPS）：**

| 服务商 | 最低价格 | 特点 |
|--------|---------|------|
| Vultr | $2.5/月 | 全球机房，按小时计费 |
| DigitalOcean | $4/月 | 稳定，新用户有 $200 额度 |
| Racknerd | $10/年 | 超低价，适合轻量应用 |
| Lightsail (AWS) | $3.5/月 | AWS 出品，稳定 |
| Bandwagon (搬瓦工) | $49.99/年 | CN2 线路，国内访问快 |

---

## 🚀 方式一：一键部署（推荐）

### 第 1 步：上传项目到服务器

```bash
# 在本地执行（macOS）
scp -r /Users/80264278/WorkBuddy/Claw/india-mobile-pulse root@YOUR_SERVER_IP:/tmp/india-mobile-pulse

# 或者用 rsync（更快，支持增量）
rsync -avz --exclude='data' --exclude='__pycache__' --exclude='.git' \
    /Users/80264278/WorkBuddy/Claw/india-mobile-pulse/ \
    root@YOUR_SERVER_IP:/tmp/india-mobile-pulse/
```

### 第 2 步：SSH 登录服务器并运行部署脚本

```bash
ssh root@YOUR_SERVER_IP

# 运行一键部署
cd /tmp/india-mobile-pulse
sudo bash deploy.sh
```

### 第 3 步：访问

部署完成后，浏览器打开：
- 有域名：`http://your-domain.com`
- 无域名：`http://YOUR_SERVER_IP`

---

## 🔧 方式二：手动部署（分步操作）

如果一键脚本有问题，可以手动操作：

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx curl
```

### 2. 创建应用用户

```bash
sudo useradd -r -m -s /bin/bash pulse
```

### 3. 上传代码到 /opt

```bash
sudo mkdir -p /opt/india-mobile-pulse
# 将项目文件复制到此处
sudo chown -R pulse:pulse /opt/india-mobile-pulse
```

### 4. 创建虚拟环境并安装依赖

```bash
cd /opt/india-mobile-pulse
sudo -u pulse python3 -m venv venv
sudo -u pulse venv/bin/pip install -r requirements.txt gunicorn
```

### 5. 配置环境变量

```bash
sudo -u pulse nano /opt/india-mobile-pulse/.env
```

写入：
```
PORT=5000
TZ=Asia/Kolkata
DAILY_COLLECTION_TIME=12:00
LLM_PROVIDER=none
```

### 6. 配置 systemd 服务

```bash
sudo cp /opt/india-mobile-pulse/india-mobile-pulse.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable india-mobile-pulse
sudo systemctl start india-mobile-pulse
```

### 7. 配置 Nginx 反向代理

```bash
sudo cp /opt/india-mobile-pulse/nginx.conf.example /etc/nginx/sites-available/india-mobile-pulse
# 编辑配置，修改 server_name 为你的域名或 IP
sudo nano /etc/nginx/sites-available/india-mobile-pulse
sudo ln -s /etc/nginx/sites-available/india-mobile-pulse /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 8. 配置防火墙

```bash
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw --force enable
```

---

## 🔒 配置 HTTPS（有域名时推荐）

```bash
# 安装 certbot
sudo apt install -y certbot python3-certbot-nginx

# 自动配置 HTTPS（自动修改 Nginx 配置）
sudo certbot --nginx -d your-domain.com

# 自动续期已内置，验证：
sudo certbot renew --dry-run
```

---

## 📊 日常运维

### 服务管理

```bash
# 查看状态
sudo systemctl status india-mobile-pulse

# 重启服务
sudo systemctl restart india-mobile-pulse

# 停止服务
sudo systemctl stop india-mobile-pulse

# 查看实时日志
sudo journalctl -u india-mobile-pulse -f

# 查看最近 100 行日志
sudo journalctl -u india-mobile-pulse -n 100
```

### 更新代码

```bash
# 方式一：从本地上传新代码
rsync -avz --exclude='data' --exclude='__pycache__' --exclude='.git' \
    ./india-mobile-pulse/ root@SERVER_IP:/opt/india-mobile-pulse/

# 方式二：服务器上 git pull（如果用 git 管理）
cd /opt/india-mobile-pulse && sudo -u pulse git pull

# 重启服务
sudo systemctl restart india-mobile-pulse
```

### 数据备份

```bash
# SQLite 数据库备份
sudo -u pulse cp /opt/india-mobile-pulse/data/pulse.db \
    /opt/india-mobile-pulse/data/pulse.db.bak.$(date +%Y%m%d)

# 定时备份（加入 crontab）
# 每天凌晨 3 点自动备份
echo "0 3 * * * pulse cp /opt/india-mobile-pulse/data/pulse.db /opt/india-mobile-pulse/data/pulse.db.bak.\$(date +\%Y\%m\%d)" | sudo tee /etc/cron.d/pulse-backup
```

### 查看数据

```bash
# 进入数据库
sudo -u pulse sqlite3 /opt/india-mobile-pulse/data/pulse.db

# 常用查询
SELECT COUNT(*) FROM posts;                    -- 总帖子数
SELECT source, COUNT(*) FROM posts GROUP BY source;  -- 按来源统计
SELECT * FROM analyses ORDER BY created_at DESC LIMIT 1;  -- 最新分析
```

---

## 🧪 健康检查

```bash
# 检查服务是否运行
curl -sf http://127.0.0.1:5000/api/dashboard | python3 -m json.tool | head -5

# 检查 Nginx 代理
curl -sf http://localhost/api/dashboard | head -20
```

---

## ❓ 常见问题

### Q: 端口 5000 被 AirPlay 占用（macOS 本地测试）
```bash
lsof -ti:5000 | xargs kill -9
```

### Q: 采集量很少 / 采集失败
- 检查服务器是否能访问外网：`curl -I https://news.google.com`
- RSS 源可能有频率限制，服务器 IP 可能被暂时屏蔽
- 查看详细错误：`journalctl -u india-mobile-pulse -f` 然后手动触发采集

### Q: 如何修改采集时间？
编辑 `/opt/india-mobile-pulse/.env` 中的 `DAILY_COLLECTION_TIME`，然后重启服务。

### Q: 如何启用 LLM 分析？
编辑 `.env`，修改 `LLM_PROVIDER=openai_compatible`，添加 API Key，重启服务。

### Q: 数据库损坏怎么办？
```bash
# 停止服务
sudo systemctl stop india-mobile-pulse

# 恢复备份
sudo -u pulse cp /opt/india-mobile-pulse/data/pulse.db.bak.YYYYMMDD /opt/india-mobile-pulse/data/pulse.db

# 重启服务
sudo systemctl start india-mobile-pulse
```
