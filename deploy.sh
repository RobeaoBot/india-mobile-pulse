#!/bin/bash
# ============================================================
# India Mobile Pulse - 一键部署脚本（方案一：VPS 直接部署）
# 适用于 Ubuntu 20.04+ / Debian 11+ 的干净服务器
# 使用方法: sudo bash deploy.sh
# ============================================================

set -e

# ---- 配置区（按需修改） ----
APP_NAME="india-mobile-pulse"
APP_USER="pulse"                    # 运行应用的系统用户
APP_DIR="/opt/${APP_NAME}"          # 应用安装目录
APP_PORT=5000                       # Gunicorn 内部端口
DOMAIN=""                           # 你的域名（留空则用 IP 访问）
TZ="Asia/Kolkata"                   # 时区（印度时间）
DAILY_TIME="12:00"                  # 每日采集时间
LLM_PROVIDER="none"                 # LLM: none / openai_compatible / gemini
# LLM_OPENAI_API_KEY=""            # 如需 LLM，取消注释并填写
# LLM_OPENAI_BASE_URL=""
# LLM_OPENAI_MODEL=""
# LLM_GEMINI_API_KEY=""

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ---- 检查 root ----
if [ "$EUID" -ne 0 ]; then
    error "请使用 root 用户运行: sudo bash deploy.sh"
fi

info "============================================"
info "  India Mobile Pulse - VPS 部署"
info "============================================"
info "应用目录: ${APP_DIR}"
info "应用用户: ${APP_USER}"
info "内部端口: ${APP_PORT}"
info "时区: ${TZ}"
info "每日采集: ${DAILY_TIME}"
info "LLM: ${LLM_PROVIDER}"
info "============================================"
echo ""

# ============================================================
# 1. 系统更新 & 安装基础依赖
# ============================================================
info "步骤 1/8: 更新系统 & 安装基础依赖..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    nginx curl wget git \
    ufw certbot python3-certbot-nginx \
    > /dev/null 2>&1
ok "系统依赖安装完成"

# ============================================================
# 2. 设置时区
# ============================================================
info "步骤 2/8: 设置时区..."
timedatectl set-timezone "${TZ}" 2>/dev/null || \
    ln -sf /usr/share/zoneinfo/${TZ} /etc/localtime
ok "时区已设置为 ${TZ}"

# ============================================================
# 3. 创建应用用户
# ============================================================
info "步骤 3/8: 创建应用用户..."
if id "${APP_USER}" &>/dev/null; then
    ok "用户 ${APP_USER} 已存在"
else
    useradd -r -m -s /bin/bash "${APP_USER}"
    ok "用户 ${APP_USER} 已创建"
fi

# ============================================================
# 4. 部署应用代码
# ============================================================
info "步骤 4/8: 部署应用代码..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/app.py" ] && [ -f "${SCRIPT_DIR}/wsgi.py" ]; then
    info "从 ${SCRIPT_DIR} 复制项目文件..."
    mkdir -p "${APP_DIR}"
    rsync -av \
        --exclude='data/' \
        --exclude='__pycache__/' \
        --exclude='.git/' \
        --exclude='.env' \
        --exclude='*.pyc' \
        "${SCRIPT_DIR}/" "${APP_DIR}/"
    ok "项目文件已复制到 ${APP_DIR}"
else
    if [ -d "${APP_DIR}/.git" ]; then
        info "更新已有代码..."
        cd "${APP_DIR}" && git pull
    else
        warn "请将项目文件上传到 ${APP_DIR}"
        read -p "项目文件已准备好？(y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            error "请先准备好项目文件再继续"
        fi
    fi
fi

mkdir -p "${APP_DIR}/data"
chown -R ${APP_USER}:${APP_USER} "${APP_DIR}"
ok "应用目录已准备: ${APP_DIR}"

# ============================================================
# 5. 创建虚拟环境 & 安装依赖
# ============================================================
info "步骤 5/8: 创建虚拟环境 & 安装依赖..."
cd "${APP_DIR}"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    ok "虚拟环境已创建"
fi

source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt gunicorn -q
deactivate
ok "Python 依赖安装完成"

# ============================================================
# 6. 配置环境变量
# ============================================================
info "步骤 6/8: 配置环境变量..."

ENV_FILE="${APP_DIR}/.env"
cat > "${ENV_FILE}" << EOF
# India Mobile Pulse 环境变量 - 自动生成
PORT=${APP_PORT}
TZ=${TZ}
DAILY_COLLECTION_TIME=${DAILY_TIME}
LLM_PROVIDER=${LLM_PROVIDER}
EOF

if [ -n "${LLM_OPENAI_API_KEY:-}" ]; then
    echo "LLM_OPENAI_API_KEY=${LLM_OPENAI_API_KEY}" >> "${ENV_FILE}"
fi
if [ -n "${LLM_OPENAI_BASE_URL:-}" ]; then
    echo "LLM_OPENAI_BASE_URL=${LLM_OPENAI_BASE_URL}" >> "${ENV_FILE}"
fi
if [ -n "${LLM_OPENAI_MODEL:-}" ]; then
    echo "LLM_OPENAI_MODEL=${LLM_OPENAI_MODEL}" >> "${ENV_FILE}"
fi
if [ -n "${LLM_GEMINI_API_KEY:-}" ]; then
    echo "LLM_GEMINI_API_KEY=${LLM_GEMINI_API_KEY}" >> "${ENV_FILE}"
fi

chown ${APP_USER}:${APP_USER} "${ENV_FILE}"
chmod 600 "${ENV_FILE}"
ok "环境变量已配置: ${ENV_FILE}"

# ============================================================
# 7. 配置 systemd 服务
# ============================================================
info "步骤 7/8: 配置 systemd 服务..."

SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=India Mobile Pulse - 印度手机圈热点监测
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/gunicorn \\
    --workers 1 \\
    --bind 127.0.0.1:${APP_PORT} \\
    --timeout 300 \\
    --access-logfile - \\
    --error-logfile - \\
    wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${APP_NAME}
systemctl restart ${APP_NAME}
ok "systemd 服务已配置并启动"

# ============================================================
# 8. 配置 Nginx 反向代理
# ============================================================
info "步骤 8/8: 配置 Nginx 反向代理..."

NGINX_CONF="/etc/nginx/sites-available/${APP_NAME}"
if [ -n "${DOMAIN}" ]; then
    SERVER_NAME="${DOMAIN}"
    LISTEN_DIRECTIVE="listen 80;"
else
    # 获取服务器公网 IP
    PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")
    SERVER_NAME="${PUBLIC_IP}"
    LISTEN_DIRECTIVE="listen 80 default_server;"
fi

cat > "${NGINX_CONF}" << EOF
server {
    ${LISTEN_DIRECTIVE}
    server_name ${SERVER_NAME};

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 静态文件直接由 Nginx 处理（更快）
    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
    }

    # API 和页面走 Gunicorn
    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # 长超时（采集任务可能耗时）
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
    }
}
EOF

# 启用站点
ln -sf "${NGINX_CONF}" /etc/nginx/sites-enabled/

# 移除默认站点（避免冲突）
if [ -n "${DOMAIN}" ]; then
    rm -f /etc/nginx/sites-enabled/default
fi

# 测试 Nginx 配置
nginx -t 2>/dev/null
if [ $? -eq 0 ]; then
    systemctl restart nginx
    ok "Nginx 已配置并重启"
else
    warn "Nginx 配置测试失败，请检查: nginx -t"
fi

# ============================================================
# 防火墙配置
# ============================================================
info "配置防火墙..."
ufw --force enable
ufw allow ssh
ufw allow 'Nginx Full'
ufw reload
ok "防火墙已配置 (SSH + HTTP/HTTPS)"

# ============================================================
# 等待服务启动 & 健康检查
# ============================================================
info "等待服务启动..."
sleep 3

if systemctl is-active --quiet ${APP_NAME}; then
    ok "应用服务运行正常"
else
    warn "应用服务未启动，请检查: journalctl -u ${APP_NAME} -n 50"
fi

if curl -sf http://127.0.0.1:${APP_PORT}/api/dashboard > /dev/null 2>&1; then
    ok "应用健康检查通过"
else
    warn "健康检查未通过，服务可能还在初始化中"
    info "请稍后手动检查: curl http://127.0.0.1:${APP_PORT}/api/dashboard"
fi

# ============================================================
# 完成
# ============================================================
echo ""
info "============================================"
ok "🎉 部署完成！"
info "============================================"
echo ""
if [ -n "${DOMAIN}" ]; then
    info "访问地址: http://${DOMAIN}"
    info ""
    info "如需 HTTPS，运行:"
    info "  sudo certbot --nginx -d ${DOMAIN}"
else
    info "访问地址: http://${SERVER_NAME}"
fi
echo ""
info "常用命令:"
info "  查看状态:   systemctl status ${APP_NAME}"
info "  查看日志:   journalctl -u ${APP_NAME} -f"
info "  重启服务:   systemctl restart ${APP_NAME}"
info "  更新代码:   cd ${APP_DIR} && git pull && systemctl restart ${APP_NAME}"
echo ""
info "数据目录: ${APP_DIR}/data/"
info "配置文件: ${APP_DIR}/.env"
info "============================================"
