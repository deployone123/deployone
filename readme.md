# DeployOne
**Gestión de Infraestructura Cloud sobre Proxmox**

DeployOne es una plataforma ligera diseñada para gestionar el despliegue de máquinas virtuales y contenedores (LXC) en un entorno de Proxmox. El sistema permite a los usuarios autenticarse, visualizar sus activos y gestionar sus terminales de forma segura a través de una interfaz web.

## 🏗️ Arquitectura del Sistema

El proyecto se basa en una arquitectura de red segmentada para maximizar la seguridad:

* **Proxy Inverso:** Nginx actuando como puerta de enlace con terminación SSL.
* **Servidor de Aplicaciones:** Python Flask servido mediante Gunicorn a través de sockets Unix.
* **Base de Datos:** MariaDB (almacenando usuarios, roles y mapeo de VMIDs de Proxmox).
* **Terminal:** Integración de `ttyd` para acceso por consola desde el navegador.

## 🛠️ Stack Tecnológico

* **Lenguaje:** Python 3.13+
* **Framework Web:** Flask
* **Servidor WSGI:** Gunicorn
* **Base de Datos:** MariaDB
* **Servidor Web:** Nginx
* **Automatización:** Ansible (Playbooks de despliegue)

## 📋 Requisitos Previos

* Servidor con **Debian 13 (Trixie)** o superior.
* Instancia de **Proxmox VE** operativa.
* Acceso SSH con privilegios de root.
* Python `venv` configurado en el directorio de la aplicación.

## 🚀 Instalación y Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone [https://github.com/tu-usuario/deployone.git](https://github.com/tu-usuario/deployone.git)
    cd deployone/website
    ```

2.  **Configurar el entorno virtual:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Configurar la Base de Datos:**
    Accede a MariaDB y crea la estructura:
    ```sql
    CREATE DATABASE cloud_provider;
    -- Importar el esquema desde la carpeta /sql si existe
    ```

4.  **Despliegue con Systemd:**
    Copia el archivo de servicio incluido para habilitar el arranque automático:
    ```bash
    sudo cp deployone.service /etc/systemd/system/
    sudo systemctl enable --now deployone
    ```

## 🔒 Seguridad

* **Hashing de contraseñas:** Implementado mediante `werkzeug.security` usando el método `scrypt`.
* **Aislamiento de Red:** La base de datos solo acepta conexiones desde el segmento de red interno o el router configurado.
* **Permisos de Socket:** El socket de Gunicorn está restringido al grupo `www-data` con un umask `007`.

## 🤝 Contribuciones

Si quieres contribuir, por favor abre un *Issue* primero para discutir los cambios que te gustaría realizar.

---
Creado con 💻 por el equipo de DeployOne.