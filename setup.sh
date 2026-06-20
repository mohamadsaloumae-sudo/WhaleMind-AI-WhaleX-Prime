#!/bin/bash
# WhaleX Prime — Setup Script
# Run: bash setup.sh

echo "=== WhaleX Prime Setup ==="

# 1. Copy files
cp -r . /opt/whalex/
mkdir -p /opt/whalex/static /opt/whalex/db

# 2. Create .env if not exists
if [ ! -f /opt/whalex/.env ]; then
cat > /opt/whalex/.env << 'ENVEOF'
SECRET_KEY=whalex-change-this-secret-2026
DATABASE_URL=sqlite:////opt/whalex/db/whalex.db
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHANNEL_FUTURES=
TELEGRAM_CHANNEL_SPOT=
TELEGRAM_CHANNEL_MEME=
TELEGRAM_ADMIN_CHAT_ID=
TELEGRAM_MINI_APP_URL=https://yourdomain.com/
BINANCE_API_KEY=
BINANCE_SECRET_KEY=
BYBIT_API_KEY=
BYBIT_SECRET_KEY=
ANTHROPIC_API_KEY=
WALLET_ADDRESS=
ENVEOF
echo "Created /opt/whalex/.env — please fill in your values"
fi

# 3. Create systemd service
cat > /etc/systemd/system/whalex.service << 'SVCEOF'
[Unit]
Description=WhaleX Prime
After=network.target

[Service]
User=root
WorkingDirectory=/opt/whalex
ExecStart=/usr/local/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SVCEOF

# 4. Create nginx config
cat > /etc/nginx/sites-enabled/whalex << 'NGXEOF'
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGXEOF

nginx -t && systemctl reload nginx

# 5. Start service
systemctl daemon-reload
systemctl enable whalex.service
systemctl start whalex.service

echo "=== Done ==="
echo "Edit /opt/whalex/.env then: systemctl restart whalex.service"
echo "Setup webhook: curl -X POST http://localhost:8000/telegram/setup-webhook"
