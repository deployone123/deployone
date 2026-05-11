#!/bin/bash

# Exit on error
set -e

echo "--- DeployOne MariaDB Setup Script ---"

# 1. Ask for Nginx machine IP to allow remote connections
read -p "Enter the Nginx machine IP (to allow remote connection): " NGINX_IP
if [ -z "$NGINX_IP" ]; then
    echo "Error: Nginx machine IP is required."
    exit 1
fi

# 2. Ask for credentials
read -p "Enter database name [website]: " DB_NAME
DB_NAME=${DB_NAME:-website}
read -p "Enter database user [admin]: " DB_USER
DB_USER=${DB_USER:-admin}
read -s -p "Enter database password: " DB_PASS
echo ""

# 3. Install MariaDB
echo "Installing MariaDB..."
sudo apt update
sudo apt install -y mariadb-server

# 4. Configure MariaDB to listen on all interfaces
echo "Configuring MariaDB to allow remote connections..."
sudo sed -i 's/bind-address\s*=\s*127.0.0.1/bind-address = 0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf
sudo systemctl restart mariadb

# 5. Setup database and user
echo "Setting up database and privileges..."
sudo mariadb -e "CREATE DATABASE IF NOT EXISTS $DB_NAME;"
sudo mariadb -e "CREATE USER IF NOT EXISTS '$DB_USER'@'$NGINX_IP' IDENTIFIED BY '$DB_PASS';"
sudo mariadb -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'$NGINX_IP';"
sudo mariadb -e "FLUSH PRIVILEGES;"

echo "------------------------------------------------"
echo "MariaDB setup complete!"
echo "Database '$DB_NAME' created and user '$DB_USER' granted access from $NGINX_IP."
echo "------------------------------------------------"
