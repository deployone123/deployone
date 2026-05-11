# Deployment Guide for DeployOne

This project is now configured to work with a **Nginx machine** (Web Server) and a **MariaDB machine** (Database Server).

## Prerequisites

- Two clean Ubuntu/Debian machines.
- The project is hosted at `https://github.com/deployone123/deployone.git`.

## Step 1: MariaDB Machine Setup

1. Copy `setup_mariadb.sh` to your MariaDB machine.
2. Make it executable:
   ```bash
   chmod +x setup_mariadb.sh
   ```
3. Run the script:
   ```bash
   ./setup_mariadb.sh
   ```
   - It will ask for the **IP of the Nginx machine** (to allow remote access).
   - It will ask for database name, user, and password.

## Step 2: Nginx Machine Setup

1. Copy `setup_nginx.sh` to your Nginx machine.
2. Make it executable:
   ```bash
   chmod +x setup_nginx.sh
   ```
3. Run the script:
   ```bash
   ./setup_nginx.sh
   ```
   - It will ask for the **IP of the MariaDB machine**.
   - It will ask for the database credentials you set in Step 1.
   - It will clone the repository, install Python dependencies, and configure Nginx + Gunicorn.
   - It will ask if you want to initialize the database schema (Answer `y` if it's a first-time setup).

## Notes

- **Environment Variables**: All configuration is stored in a `.env` file on the Nginx machine.
- **Ansible API**: The `ANSIBLE_API_BASE_URL` is set to `http://answeb.deployone.test` by default. You can change this in the `.env` file.
- **Security**: Nginx is configured as a reverse proxy to Gunicorn via a unix socket.
