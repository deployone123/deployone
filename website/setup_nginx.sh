#!/bin/bash

# Exit on error
set -e

echo "--- DeployOne Nginx Setup Script ---"

# 1. Ask for MariaDB IP
read -p "Enter the MariaDB machine IP: " MARIADB_IP
if [ -z "$MARIADB_IP" ]; then
    echo "Error: MariaDB IP is required."
    exit 1
fi

# 2. Ask for MariaDB credentials
read -p "Enter MariaDB database name [website]: " DB_NAME
DB_NAME=${DB_NAME:-website}
read -p "Enter MariaDB user [admin]: " DB_USER
DB_USER=${DB_USER:-admin}
read -s -p "Enter MariaDB password: " DB_PASS
echo ""

# 3. Update and install dependencies
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y nginx git python3-pip python3-venv libmariadb-dev build-essential

# 4. Clone or use local files
if [ -f "requirements.txt" ] && [ -f "app.py" ]; then
    echo "Project files detected in the current directory. Using local files."
    APP_PATH=$(pwd)
else
    echo "Project files not found locally."
    if [ -d "deployone" ]; then
        echo "Directory 'deployone' already exists. Updating..."
        cd deployone
        git pull
    else
        echo "Cloning repository..."
        git clone https://github.com/deployone123/deployone.git
        cd deployone
    fi
    APP_PATH=$(pwd)
fi

# Ensure requirements.txt exists before proceeding
if [ ! -f "$APP_PATH/requirements.txt" ]; then
    echo "Error: $APP_PATH/requirements.txt not found!"
    exit 1
fi

# 5. Create .env file
echo "Configuring environment..."
cd "$APP_PATH"
cat <<EOF > .env
DB_HOST=$MARIADB_IP
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASS=$DB_PASS
SECRET_KEY=$(python3 -c 'import os; print(os.urandom(24).hex())')
ANSIBLE_API_BASE_URL=http://answeb.deployone.test
ALLOWED_PROXY_IP=100.121.99.42
EOF

# 6. Setup Python Virtual Environment
echo "Setting up Python virtual environment in $APP_PATH..."
python3 -m venv "$APP_PATH/venv"

# Use the venv pip directly to avoid "externally-managed-environment" errors
echo "Installing dependencies..."
"$APP_PATH/venv/bin/pip" install --upgrade pip
"$APP_PATH/venv/bin/pip" install -r "$APP_PATH/requirements.txt"

# 7. Initialize Database
echo "Do you want to initialize the database schema? (This will attempt to connect to $MARIADB_IP)"
read -p "(y/n): " INIT_DB
if [ "$INIT_DB" == "y" ]; then
    "$APP_PATH/venv/bin/python3" "$APP_PATH/init_db.py"
fi

# 8. Configure Nginx
echo "Configuring Nginx..."
# APP_PATH is already set
cat <<EOF | sudo tee /etc/nginx/sites-available/deployone
server {
    listen 80;
    server_name _;

    location / {
        include proxy_params;
        proxy_pass http://unix:$APP_PATH/deployone.sock;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/deployone /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# 9. Setup Gunicorn Systemd Service
echo "Setting up Gunicorn service..."
USER=$(whoami)
cat <<EOF | sudo tee /etc/systemd/system/deployone.service
[Unit]
Description=Gunicorn instance to serve DeployOne
After=network.target

[Service]
User=$USER
Group=www-data
WorkingDirectory=$APP_PATH
Environment="PATH=$APP_PATH/venv/bin"
ExecStart=$APP_PATH/venv/bin/gunicorn --workers 3 --bind unix:deployone.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl start deployone
sudo systemctl enable deployone

echo "------------------------------------------------"
echo "Setup complete!"
echo "Your application should now be accessible at http://$(curl -s ifconfig.me) or your machine's IP."
echo "------------------------------------------------"
