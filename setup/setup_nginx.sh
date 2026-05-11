#!/bin/bash

# --- DeployOne Web Server Automated Setup ---
# This script installs Nginx, Gunicorn, and the DeployOne Flask application.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}   DeployOne: Web Server Setup               ${NC}"
echo -e "${BLUE}==============================================${NC}"

# Check for root
if [ "$EUID" -ne 0 ]; then 
  echo -e "${RED}Please run as root (sudo)${NC}"
  exit 1
fi

# 1. Configuration Prompts
echo -e "${GREEN}[1/8] Configuration${NC}"
read -p "Enter the MariaDB Server IP: " DB_HOST
read -p "Enter Database Name [deployone]: " DB_NAME
DB_NAME=${DB_NAME:-deployone}
read -p "Enter Database User [nginx]: " DB_USER
DB_USER=${DB_USER:-nginx}
read -s -p "Enter Database Password: " DB_PASS
echo ""
read -p "Enter Resend API Key (Optional): " RESEND_KEY
read -p "Enter Allowed Proxy IP [100.121.99.42]: " PROXY_IP
ALLOWED_PROXY_IP=${PROXY_IP:-100.121.99.42}

# 2. Install Dependencies
echo -e "${GREEN}[2/8] Installing System Dependencies...${NC}"
apt update && apt install -y nginx git python3-pip python3-venv libmariadb-dev build-essential curl

# 3. Code Synchronization
echo -e "${GREEN}[3/8] Synchronizing Application Code...${NC}"
# Determine if we are inside the repo or need to clone
if [ -f "website/app.py" ]; then
    echo "Found local repository files. Using current directory."
    INSTALL_DIR=$(pwd)/website
else
    echo "Cloning repository from GitHub..."
    TMP_DIR="/tmp/deployone_clone"
    rm -rf "$TMP_DIR"
    git clone https://github.com/deployone123/deployone.git "$TMP_DIR"
    mkdir -p /var/www/deployone
    cp -r "$TMP_DIR/website" /var/www/deployone/
    INSTALL_DIR="/var/www/deployone/website"
fi

# 4. Environment Configuration
echo -e "${GREEN}[4/8] Creating .env File...${NC}"
cat <<EOF > "$INSTALL_DIR/.env"
DB_HOST=$DB_HOST
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASS=$DB_PASS
SECRET_KEY=$(python3 -c 'import os; print(os.urandom(24).hex())')
ANSIBLE_API_BASE_URL=http://answeb.deployone.test:8000
ALLOWED_PROXY_IP=$ALLOWED_PROXY_IP
RESEND_API_KEY=$RESEND_KEY
EOF

# 5. Python Environment Setup
echo -e "${GREEN}[5/8] Setting up Virtual Environment...${NC}"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# 6. Database Initialization
echo -e "${GREEN}[6/8] Initializing Database Schema...${NC}"
echo "Attempting to connect to $DB_HOST..."
if "$INSTALL_DIR/venv/bin/python3" "$INSTALL_DIR/init_db.py"; then
    echo -e "${GREEN}Database initialized successfully.${NC}"
else
    echo -e "${RED}Warning: Database initialization failed. Check connectivity to $DB_HOST.${NC}"
fi

# 7. Nginx Configuration
echo -e "${GREEN}[7/8] Configuring Nginx Reverse Proxy...${NC}"
cat <<EOF > /etc/nginx/sites-available/deployone
server {
    listen 80;
    server_name _;

    location ~ ^/terminal/(?<target_ip>[\d\.]+)/ {
        proxy_pass http://\$target_ip:7681/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host \$host;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:$INSTALL_DIR/deployone.sock;
    }
}
EOF

ln -sf /etc/nginx/sites-available/deployone /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx

# 8. Gunicorn Service Setup
echo -e "${GREEN}[8/8] Creating Systemd Service...${NC}"
cat <<EOF > /etc/systemd/system/deployone.service
[Unit]
Description=Gunicorn instance to serve DeployOne
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/gunicorn --workers 3 --bind unix:$INSTALL_DIR/deployone.sock --umask 007 app:app

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable deployone
systemctl restart deployone

echo -e "${BLUE}==============================================${NC}"
echo -e "${GREEN}SUCCESS: Web Server setup complete!${NC}"
echo -e "Access the dashboard at: http://$(curl -s ifconfig.me || echo 'YOUR_SERVER_IP')"
echo -e "${BLUE}==============================================${NC}"
