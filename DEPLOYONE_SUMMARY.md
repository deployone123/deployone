# Project "DeployOne" - System Architecture & State Summary

## 1. Core Purpose
A custom Cloud Service Provider (CSP) dashboard built on Proxmox VE. The system automates the creation of LXC/VM instances, handles user authentication, manages networking isolation per client, and provides a web-based terminal for management.

## 2. Infrastructure Stack
- **Virtualization**: Proxmox VE (Debian 13 Trixie) - IP: 10.1.100.100.
- **Proxy/Frontend**: Nginx LXC (102) - Acting as the entry point and Reverse Proxy.
- **Application Server**: Python (Flask) + Gunicorn + MariaDB.
- **Automation Engine**: Ansible running a FastAPI management layer (ansible_api).
- **Service Management**: Systemd handles both the `deployone.service` (Flask) and `ansible-api.service` (Uvicorn).

## 3. Network Topology & Segmentation
The project uses multiple Linux Bridges (vmbrX) for traffic isolation:
- **vmbr0 (WAN/Public)**: External access. Proxy IP: 10.1.100.101.
- **vmbr1 (Proxy Internal)**: Subnet 192.168.10.0/29.
- **vmbr2 (Management)**: Subnet 172.31.10.0/29.
- **vmbr3 (Ansible/Automation)**: Subnet 192.168.20.0/29.
- **vmbr4 (Client VLANs)**: This bridge is VLAN Aware. Every client is assigned a unique VLAN Tag (equal to their client_id) for L2 isolation.
  - **Current Status**: vmbr4 is NOT currently VLAN aware as the logic to pass `client_id` from the website to Ansible is still being implemented.

> [!IMPORTANT]
> **Firewall Note**: The Proxmox Datacenter Firewall is currently DISABLED to resolve routing issues between the host and containers. Any future security implementation must account for the FORWARD chain and ARP resolution across these bridges.

## 4. Database Schema (MariaDB)
The `cloud_provider` database tracks resources:
- **users**: `client_id` (PK), `username`, `password_hash` (Scrypt), `role`, `is_verified`.
- **machines**: `proxmox_vmid`, `machine_name`, `internal_ip`, `owner_id` (FK to users).

## 5. Deployment & Automation Logic
- **Deployment Flow**: Web Dashboard → FastAPI (`/root/ansible_api`) → Ansible Playbook → Proxmox API/CLI.
- **IP Logic**: IPs are calculated programmatically: `10.[client_id].0.10/24`.
- **Connectivity**: Ansible and Nginx access client machines via a ProxyJump (Bastion) through the Nginx container to keep clients off the public internet.
- **Inventory**: Uses a Dynamic Inventory script (`inventory.py`) that queries MariaDB to allow Ansible to scale without static host files.

## 6. Current Operational Status
- **Codebase**: Hosted in Git at `/var/www/deployone`.
- **Security**: 
  - **Password Policy**: Enforced complexity (10+ chars, uppercase, number, special char) via `re` validation in `app.py`.
  - **Account Verification**: Full email verification flow implemented using **Resend**. 
    - **Domain**: `deployone.cat` (Verified via Cloudflare DNS).
    - **Sender**: `verify@deployone.cat`.
    - **Token Logic**: Secure tokens generated via `itsdangerous` (valid for 1 hour).
  - **Security Headers**: Standard headers (CSP, HSTS, X-Frame-Options, etc.) active on both Flask and Nginx levels.

## 7. Connection & Access Info
- **Database IP**: `192.168.20.3` (Access via SSH on Proxmox).
- **Proxy IP**: `10.1.100.101` (LAN) or `100.121.99.42` (Tailscale).
- **Proxmox Host**: `10.1.100.100` (LAN) or `100.107.61.56` (Tailscale).
- **Web Server IP**: `172.31.10.4` (Access from inside Proxmox).
- **Outbound Mail Proxy**: `tinyproxy` running on Proxmox host (`172.31.10.0:8888`). Used by the web server to reach the Resend API.

> [!NOTE]
> - The web server still needs to be configured to access all machines across the VLAN-aware bridges.
> - The `is_verified` column is automatically added to the `users` table via the `ensure_required_tables()` migration in `app.py`.


## 8. Backups & Data Integrity
To ensure business continuity, a fully automated backup system is implemented:
- **Schedule**: Full system backups are performed daily at **3:00 AM**.
- **Backup Infrastructure**:
  - **Zerobyte (LXC)**: A dedicated container manages the backup lifecycle.
  - **Rclone Integration**: Configured within Zerobyte to handle secure cloud synchronization.
  - **Storage Strategy**: The backups directory is mounted to the Zerobyte container via **mount passthrough** in the LXC configuration for high-performance disk access.
- **Security & Destination**:
  - **Encryption**: All backup archives are **encrypted** locally using Zerobyte before transmission.
  - **Off-site Storage**: Encrypted bundles are uploaded to **Mega** using the Rclone provider.