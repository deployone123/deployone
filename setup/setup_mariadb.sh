#!/bin/bash

# --- DeployOne MariaDB Automated Setup ---
# This script installs MariaDB and configures it for remote access from the Web Server.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}   DeployOne: Database Server Setup          ${NC}"
echo -e "${BLUE}==============================================${NC}"

# Check for root
if [ "$EUID" -ne 0 ]; then 
  echo -e "${RED}Please run as root (sudo)${NC}"
  exit 1
fi

# 1. Configuration Prompts
echo -e "${GREEN}[1/5] Configuration${NC}"
read -p "Enter the Web Server (Nginx) IP Address: " NGINX_IP
read -p "Enter Database Name [deployone]: " DB_NAME
DB_NAME=${DB_NAME:-deployone}
read -p "Enter Database User [nginx]: " DB_USER
DB_USER=${DB_USER:-nginx}
read -s -p "Enter Database Password: " DB_PASS
echo ""

# 2. Install MariaDB
echo -e "${GREEN}[2/5] Installing MariaDB Server...${NC}"
apt update && apt install -y mariadb-server

# 3. Network Configuration
echo -e "${GREEN}[3/5] Configuring Network Access...${NC}"
# Allow MariaDB to listen on all interfaces
sed -i 's/bind-address\s*=\s*127.0.0.1/bind-address = 0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf
systemctl restart mariadb

# 4. Database & User Creation
echo -e "${GREEN}[4/5] Setting up Database and Privileges...${NC}"
mariadb -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`;"
mariadb -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'${NGINX_IP}' IDENTIFIED BY '${DB_PASS}';"
mariadb -e "GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'${NGINX_IP}';"
mariadb -e "FLUSH PRIVILEGES;"

# 5. Firewall (Optional but recommended)
echo -e "${GREEN}[5/5] Finalizing...${NC}"
if command -v ufw > /dev/null; then
    echo "Allowing MySQL port (3306) through UFW..."
    ufw allow from "$NGINX_IP" to any port 3306
fi

echo -e "${BLUE}==============================================${NC}"
echo -e "${GREEN}SUCCESS: Database server is ready!${NC}"
echo -e "Database: ${DB_NAME}"
echo -e "User: ${DB_USER}"
echo -e "Access allowed from: ${NGINX_IP}"
echo -e "${BLUE}==============================================${NC}"
