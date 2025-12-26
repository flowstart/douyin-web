# 抖音电商物流查询系统 - 线上部署指南

本文档介绍如何将系统部署到生产环境。

## 目录

- [环境要求](#环境要求)
- [部署架构](#部署架构)
- [方式一：Docker 部署（推荐）](#方式一docker-部署推荐)
- [方式二：传统部署](#方式二传统部署)
- [方式三：云平台部署](#方式三云平台部署)
- [Nginx 反向代理配置](#nginx-反向代理配置)
- [SSL 证书配置](#ssl-证书配置)
- [监控与日志](#监控与日志)
- [常见问题](#常见问题)

---

## 环境要求

### 服务器配置

| 配置项 | 最低要求 | 推荐配置 |
|--------|----------|----------|
| CPU | 1 核 | 2 核+ |
| 内存 | 2 GB | 4 GB+ |
| 硬盘 | 20 GB | 50 GB+ SSD |
| 系统 | Ubuntu 20.04+ / CentOS 7+ | Ubuntu 22.04 LTS |

### 软件依赖

- Python 3.11+
- Node.js 18+
- Nginx（反向代理）
- Docker & Docker Compose（可选）

---

## 部署架构

```
                    ┌─────────────┐
                    │   Nginx     │
                    │  (端口 80/443) │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Frontend │    │ Backend  │    │ 静态文件  │
    │ (3000)   │    │ (8000)   │    │ /uploads │
    └──────────┘    └──────────┘    └──────────┘
                           │
                           ▼
                    ┌──────────┐
                    │ SQLite / │
                    │  MySQL   │
                    └──────────┘
```

---

## 方式一：Docker 部署（推荐）

### 1. 创建 Docker 配置文件

在项目根目录创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: douyin-backend
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./data/douyin_orders.db
      - KD100_KEY=${KD100_KEY}
      - KD100_CUSTOMER=${KD100_CUSTOMER}
      - DEBUG=false
    volumes:
      - ./data:/app/data
      - ./backend/uploads:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: douyin-frontend
    restart: always
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend

  nginx:
    image: nginx:alpine
    container_name: douyin-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - frontend
      - backend
```

### 2. 创建 Backend Dockerfile

创建 `backend/Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data /app/uploads

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. 创建 Frontend Dockerfile

创建 `frontend/Dockerfile`：

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖
RUN npm ci

# 复制源代码
COPY . .

# 设置环境变量
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}

# 构建应用
RUN npm run build

# 生产镜像
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# 复制构建产物
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
```

### 4. 启动服务

```bash
# 创建环境变量文件
cp backend/env.example .env

# 编辑环境变量
vim .env

# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

---

## 方式二：传统部署

### 1. 后端部署

```bash
# 1. 安装 Python 3.11
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# 2. 创建项目目录
sudo mkdir -p /var/www/douyin-web
sudo chown $USER:$USER /var/www/douyin-web

# 3. 上传代码
cd /var/www/douyin-web
git clone https://github.com/flowstart/douyin-web.git .

# 4. 创建虚拟环境
cd backend
python3.11 -m venv venv
source venv/bin/activate

# 5. 安装依赖
pip install -r requirements.txt

# 6. 配置环境变量
cp env.example .env
vim .env  # 填入生产环境配置

# 7. 创建 Systemd 服务
sudo tee /etc/systemd/system/douyin-backend.service << EOF
[Unit]
Description=Douyin Backend API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/var/www/douyin-web/backend
Environment="PATH=/var/www/douyin-web/backend/venv/bin"
EnvironmentFile=/var/www/douyin-web/backend/.env
ExecStart=/var/www/douyin-web/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 8. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable douyin-backend
sudo systemctl start douyin-backend

# 9. 检查状态
sudo systemctl status douyin-backend
```

### 2. 前端部署

```bash
# 1. 安装 Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 2. 构建前端
cd /var/www/douyin-web/frontend

# 3. 安装依赖
npm ci

# 4. 设置 API 地址（修改 src/lib/api.ts 或使用环境变量）
export NEXT_PUBLIC_API_URL=https://your-domain.com/api

# 5. 构建生产版本
npm run build

# 6. 使用 PM2 管理进程
sudo npm install -g pm2

# 7. 启动应用
pm2 start npm --name "douyin-frontend" -- start

# 8. 设置开机自启
pm2 startup
pm2 save
```

---

## 方式三：云平台部署

### 阿里云 ECS 部署

1. **购买 ECS 实例**
   - 选择 Ubuntu 22.04 LTS
   - 配置安全组，开放 80、443、22 端口

2. **连接服务器**
   ```bash
   ssh root@your-server-ip
   ```

3. **按照「传统部署」步骤操作**

### Vercel + Railway 部署

**前端部署到 Vercel：**

```bash
# 1. 安装 Vercel CLI
npm i -g vercel

# 2. 部署
cd frontend
vercel

# 3. 设置环境变量
vercel env add NEXT_PUBLIC_API_URL
```

**后端部署到 Railway：**

1. 访问 [Railway](https://railway.app)
2. 新建项目，导入 GitHub 仓库
3. 选择 `backend` 目录
4. 配置环境变量
5. 部署

---

## Nginx 反向代理配置

创建 `/etc/nginx/sites-available/douyin-web`：

```nginx
upstream backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

upstream frontend {
    server 127.0.0.1:3000;
    keepalive 32;
}

server {
    listen 80;
    server_name your-domain.com;

    # 重定向到 HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL 配置
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 1000;

    # 前端
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://backend/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # API 文档
    location /docs {
        proxy_pass http://backend/docs;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://backend/openapi.json;
        proxy_set_header Host $host;
    }

    # 静态文件上传目录
    location /uploads/ {
        alias /var/www/douyin-web/backend/uploads/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/douyin-web /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## SSL 证书配置

### 使用 Let's Encrypt（免费）

```bash
# 1. 安装 Certbot
sudo apt install certbot python3-certbot-nginx

# 2. 申请证书
sudo certbot --nginx -d your-domain.com

# 3. 自动续期（已自动配置）
sudo certbot renew --dry-run
```

### 使用已有证书

```bash
# 上传证书到服务器
sudo mkdir -p /etc/nginx/ssl
sudo cp fullchain.pem /etc/nginx/ssl/
sudo cp privkey.pem /etc/nginx/ssl/
sudo chmod 600 /etc/nginx/ssl/*.pem
```

---

## 监控与日志

### 日志位置

```bash
# 后端日志
journalctl -u douyin-backend -f

# 前端日志
pm2 logs douyin-frontend

# Nginx 日志
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### 健康检查

```bash
# 检查后端
curl http://localhost:8000/health

# 检查前端
curl http://localhost:3000
```

### 进程监控

```bash
# 查看后端状态
sudo systemctl status douyin-backend

# 查看前端状态
pm2 status

# 查看资源使用
htop
```

---

## 数据库迁移（可选）

如果需要从 SQLite 迁移到 MySQL：

### 1. 安装 MySQL

```bash
sudo apt install mysql-server
sudo mysql_secure_installation
```

### 2. 创建数据库

```sql
CREATE DATABASE douyin_orders CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'douyin'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON douyin_orders.* TO 'douyin'@'localhost';
FLUSH PRIVILEGES;
```

### 3. 修改环境变量

```bash
# .env
DATABASE_URL=mysql+aiomysql://douyin:your_password@localhost/douyin_orders
```

### 4. 安装 MySQL 驱动

```bash
pip install aiomysql
```

---

## 常见问题

### Q: 后端无法启动

**检查步骤：**
```bash
# 查看日志
journalctl -u douyin-backend -n 50

# 检查端口占用
lsof -i :8000

# 检查环境变量
cat /var/www/douyin-web/backend/.env
```

### Q: 前端无法访问 API

**检查步骤：**
1. 确认 `NEXT_PUBLIC_API_URL` 配置正确
2. 检查 Nginx 反向代理配置
3. 确认后端服务正在运行

### Q: 上传文件失败

**解决方案：**
```bash
# 检查目录权限
ls -la /var/www/douyin-web/backend/uploads/

# 修复权限
sudo chown -R www-data:www-data /var/www/douyin-web/backend/uploads/
sudo chmod 755 /var/www/douyin-web/backend/uploads/
```

### Q: 内存不足

**优化方案：**
```bash
# 添加 Swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 备份策略

### 数据库备份

```bash
# 创建备份脚本
cat > /var/www/douyin-web/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/douyin"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# 备份 SQLite 数据库
cp /var/www/douyin-web/backend/douyin_orders.db $BACKUP_DIR/db_$DATE.db

# 备份上传文件
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /var/www/douyin-web/backend/uploads/

# 保留最近 7 天备份
find $BACKUP_DIR -type f -mtime +7 -delete
EOF

chmod +x /var/www/douyin-web/backup.sh

# 添加定时任务（每天凌晨 2 点执行）
echo "0 2 * * * /var/www/douyin-web/backup.sh" | crontab -
```

---

## 联系方式

如有问题，请提交 Issue：https://github.com/flowstart/douyin-web/issues
