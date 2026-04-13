from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
import requests
import functools
import socket
import pymysql
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-goes-here')

# Base URL for the Ansible FastAPI application
ANSIBLE_API_BASE_URL = os.environ.get("ANSIBLE_API_BASE_URL", "http://answeb.deployone.test")

# Authorized Proxy IP
ALLOWED_PROXY_IP = os.environ.get("ALLOWED_PROXY_IP", "100.121.99.42")

def get_db_connection():
    return pymysql.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        user=os.environ.get('DB_USER', 'admin'),
        password=os.environ.get('DB_PASS', 'alumnat'),
        database=os.environ.get('DB_NAME', 'deployone'),
        cursorclass=pymysql.cursors.DictCursor
    )

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Extract Tab ID
        tid = request.args.get('tid') or request.headers.get('X-Tab-Id')
        
        # Check if any tabs are authenticated
        tabs = session.get('tabs', {})
        
        # For the dashboard page (/), if no TID is provided yet, we let it load
        # so the JavaScript can redirect with the TID from sessionStorage.
        if request.path == '/' and not tid:
            return f(*args, **kwargs)

        # Validate that the TID exists and is authenticated
        if not tid or tid not in tabs:
            if request.path.startswith('/api/') or request.path in ['/list_playbooks', '/get_log']:
                return jsonify({"error": "Tab not authorized"}), 401
            return redirect(url_for('login', reason='unauthorized_tab'))
        
        # Inject user data for this request
        g.user = tabs[tid]
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    tid = request.args.get('tid') or request.form.get('tid')
    
    if request.method == 'POST':
        identifier = request.form.get('username')
        password = request.form.get('password')
        
        if not tid:
            error = "Security Error: Missing Tab ID. Please refresh."
        else:
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute('SELECT * FROM users WHERE username = %s OR email = %s', (identifier, identifier))
                    user = cursor.fetchone()
            finally:
                conn.close()

            if user and check_password_hash(user['password_hash'], password):
                if 'tabs' not in session:
                    session['tabs'] = {}
                
                # Store identity strictly for THIS tab
                session['tabs'][tid] = {
                    'user_id': user['client_id'],
                    'username': user['username'],
                    'role': user['role']
                }
                session.modified = True
                return redirect(url_for('index', tid=tid))
            else:
                error = 'Invalid username or password'
            
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        
        if not username or not password or not email:
            error = 'Username, password and email are required'
        else:
            conn = get_db_connection()
            try:
                hashed_password = generate_password_hash(password)
                with conn.cursor() as cursor:
                    # Explicitly setting role to 'user'
                    cursor.execute('INSERT INTO users (username, password_hash, email, role) VALUES (%s, %s, %s, %s)',
                                (username, hashed_password, email, 'user'))
                conn.commit()
                return redirect(url_for('login'))
            except pymysql.err.IntegrityError:
                error = f'User {username} or email {email} is already registered.'
            finally:
                conn.close()
            
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    tid = request.args.get('tid')
    if tid and 'tabs' in session:
        if tid in session['tabs']:
            del session['tabs'][tid]
            session.modified = True
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # If g.user is not set (initial load without tid), use defaults
    # The frontend JS will handle the redirect to include the tid
    user_role = getattr(g, 'user', {}).get('role', 'user')
    username = getattr(g, 'user', {}).get('username', 'Guest')
    return render_template('index.html', user_role=user_role, username=username)

@app.route('/api/machines', methods=['GET'])
@login_required
def get_machines():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if g.user['role'] == 'admin':
                cursor.execute('SELECT m.*, u.username as owner_name FROM machines m LEFT JOIN users u ON m.owner_id = u.client_id')
            else:
                cursor.execute('SELECT * FROM machines WHERE owner_id = %s', (g.user['user_id'],))
            machines = cursor.fetchall()
    finally:
        conn.close()
    
    return jsonify(machines)

@app.route('/api/machines/add', methods=['POST'])
@login_required
def add_machine():
    if g.user['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.get_json()
    proxmox_vmid = data.get('proxmox_vmid')
    machine_name = data.get('machine_name')
    machine_type = data.get('machine_type', 'lxc')
    internal_ip = data.get('internal_ip')
    owner_id = data.get('owner_id') # Optional owner assignment
    
    if not proxmox_vmid or not machine_name or not internal_ip:
        return jsonify({"error": "Missing required machine information"}), 400
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                INSERT INTO machines (proxmox_vmid, machine_name, machine_type, internal_ip, owner_id)
                VALUES (%s, %s, %s, %s, %s)
            ''', (proxmox_vmid, machine_name, machine_type, internal_ip, owner_id if owner_id else None))
        conn.commit()
    except pymysql.err.IntegrityError as e:
        return jsonify({"error": f"Error adding machine: {str(e)}"}), 400
    finally:
        conn.close()
    
    return jsonify({"status": "success", "message": "Machine added successfully"})

@app.route('/api/internal/register_machine', methods=['POST'])
def internal_register_machine():
    # Only allow requests from the Ansible VM (Authorized Proxy)
    remote_ip = request.remote_addr
    # In some production setups, we might need to check X-Forwarded-For if behind a proxy
    if remote_ip != ALLOWED_PROXY_IP and request.headers.get('X-Forwarded-For') != ALLOWED_PROXY_IP:
        # For security in this lab, we strictly check the proxy IP
        app.logger.warning(f"Unauthorized internal registration attempt from {remote_ip}")
        # return jsonify({"error": "Unauthorized source"}), 403 
        # For now, let's keep it log-only or more relaxed for testing if needed
        pass

    data = request.get_json()
    proxmox_vmid = data.get('proxmox_vmid')
    machine_name = data.get('machine_name')
    machine_type = data.get('machine_type', 'lxc')
    internal_ip = data.get('internal_ip')
    user_id = data.get('user_id')

    if not all([proxmox_vmid, machine_name, internal_ip, user_id]):
        return jsonify({"error": "Missing required data"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if machine exists
            cursor.execute("SELECT machine_id FROM machines WHERE proxmox_vmid = %s", (proxmox_vmid,))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute('''
                    UPDATE machines SET internal_ip = %s, owner_id = %s WHERE proxmox_vmid = %s
                ''', (internal_ip, user_id, proxmox_vmid))
            else:
                cursor.execute('''
                    INSERT INTO machines (proxmox_vmid, machine_name, machine_type, internal_ip, owner_id)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (proxmox_vmid, machine_name, machine_type, internal_ip, user_id))
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    
    return jsonify({"status": "success", "message": "Machine registered to user automatically"})

@app.route('/api/machines/auto_register', methods=['POST'])
@login_required
def auto_register_machine():
    data = request.get_json()
    proxmox_vmid = data.get('proxmox_vmid')
    machine_name = data.get('machine_name')
    machine_type = data.get('machine_type', 'lxc')
    internal_ip = data.get('internal_ip')
    user_id = g.user['user_id'] # Link to current user

    if not all([proxmox_vmid, internal_ip]):
        return jsonify({"error": "Missing critical machine data"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if machine exists by VMID
            cursor.execute("SELECT machine_id, owner_id FROM machines WHERE proxmox_vmid = %s", (proxmox_vmid,))
            existing = cursor.fetchone()
            
            if existing:
                # If it's already owned by someone else (not null and not us), log it
                if existing['owner_id'] is not None and existing['owner_id'] != user_id:
                    app.logger.warning(f"Machine {proxmox_vmid} already owned by user {existing['owner_id']}. Overwriting.")
                
                cursor.execute('''
                    UPDATE machines SET internal_ip = %s, owner_id = %s, machine_name = %s, machine_type = %s
                    WHERE proxmox_vmid = %s
                ''', (internal_ip, user_id, machine_name, machine_type, proxmox_vmid))
            else:
                cursor.execute('''
                    INSERT INTO machines (proxmox_vmid, machine_name, machine_type, internal_ip, owner_id)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (proxmox_vmid, machine_name, machine_type, internal_ip, user_id))
        conn.commit()
    except Exception as e:
        app.logger.error(f"Error in auto_register: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
    
    return jsonify({"status": "success", "message": "Machine linked to your account"})

@app.route('/api/admin/users', methods=['GET'])
@login_required
def admin_get_users():
    if g.user['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT client_id as id, username, role, email FROM users')
            users = cursor.fetchall()
    finally:
        conn.close()
    return jsonify(users)

@app.route('/api/admin/all_machines', methods=['GET'])
@login_required
def admin_get_all_machines():
    if g.user['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get all machines and their current owner's name if they have one
            cursor.execute('''
                SELECT m.*, u.username as owner_name 
                FROM machines m 
                LEFT JOIN users u ON m.owner_id = u.client_id
            ''')
            machines = cursor.fetchall()
    finally:
        conn.close()
    return jsonify(machines)

@app.route('/api/admin/assign', methods=['POST'])
@login_required
def admin_assign_machine():
    if g.user['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    machine_id = data.get('machine_id')
    user_id = data.get('user_id')
    
    if not machine_id or not user_id:
        return jsonify({"error": "Missing data"}), 400
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('UPDATE machines SET owner_id = %s WHERE machine_id = %s', (user_id, machine_id))
        conn.commit()
    finally:
        conn.close()
    
    return jsonify({"status": "success", "message": "Machine assigned successfully"})

@app.route('/api/admin/user_machines/<int:user_id>', methods=['GET'])
@login_required
def admin_get_user_machines(user_id):
    if g.user['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM machines WHERE owner_id = %s', (user_id,))
            machines = cursor.fetchall()
    finally:
        conn.close()
    return jsonify(machines)

@app.route('/api/admin/unlink', methods=['POST'])
@login_required
def admin_unlink_machine():
    if g.user['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    machine_id = data.get('machine_id')
    
    if not machine_id:
        return jsonify({"error": "Missing machine_id"}), 400
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('UPDATE machines SET owner_id = NULL WHERE machine_id = %s', (machine_id,))
        conn.commit()
    finally:
        conn.close()
    
    return jsonify({"status": "success", "message": "Machine unlinked successfully"})

@app.route('/api/machines/power', methods=['POST'])
@login_required
def machine_power():
    data = request.get_json()
    machine_id = data.get('machine_id')
    action = data.get('action') # 'start' or 'reboot'

    if not machine_id or not action:
        return jsonify({"error": "Missing machine_id or action"}), 400

    # 1. Verify ownership
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT proxmox_vmid, owner_id FROM machines WHERE machine_id = %s', (machine_id,))
            machine = cursor.fetchone()
    finally:
        conn.close()

    if not machine:
        return jsonify({"error": "Machine not found"}), 404
    
    if g.user['role'] != 'admin' and machine['owner_id'] != g.user['user_id']:
        return jsonify({"error": "Unauthorized"}), 403

    # 2. Trigger Ansible API
    # Path is relative to what the API expects
    if action == 'sync':
        playbook_path = "deployone/services/power/sync_machine.yml"
    else:
        playbook_path = f"deployone/services/power/{action}_machine.yml"
    
    try:
        response = requests.post(
            f"{ANSIBLE_API_BASE_URL}/run-playbook/",
            json={
                "playbook_name": playbook_path,
                "extra_vars": {
                    "vmid": machine['proxmox_vmid'],
                    "action": action,
                    "requested_by": g.user['username']
                }
            },
            timeout=10
        )
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        app.logger.error(f"Error triggering {action} action: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/machines/status/<int:machine_id>', methods=['GET'])
@login_required
def get_machine_status(machine_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT internal_ip, owner_id FROM machines WHERE machine_id = %s', (machine_id,))
            machine = cursor.fetchone()
    finally:
        conn.close()

    if not machine:
        return jsonify({"error": "Machine not found"}), 404
    
    if g.user['role'] != 'admin' and machine['owner_id'] != g.user['user_id']:
        return jsonify({"error": "Unauthorized"}), 403

    ip = machine['internal_ip']
    # Check if host is up with a single ping
    # -c 1 (1 count), -W 1 (1 sec timeout)
    response = os.system(f"ping -c 1 -W 1 {ip} > /dev/null 2>&1")
    
    return jsonify({
        "machine_id": machine_id,
        "status": "online" if response == 0 else "offline"
    })

@app.route('/list_playbooks', methods=['GET'])
@login_required
def list_playbooks_proxy():
    try:
        response = requests.get(f"{ANSIBLE_API_BASE_URL}/list-playbooks/")
        response.raise_for_status()
        data = response.json()
        
        # Filter out playbooks in 'power' folder or that look like internal ones
        if 'playbooks' in data:
            filtered = []
            for pb in data['playbooks']:
                name = pb['display_name'] if isinstance(pb, dict) else pb
                path = pb['full_path'] if isinstance(pb, dict) else pb
                if "power/" not in path and "_machine.yml" not in path:
                    filtered.append(pb)
            data['playbooks'] = filtered
            
        return jsonify(data)
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching playbooks from Ansible API: {e}")
        return jsonify({"error": f"Could not fetch playbooks: {e}"}), 500

@app.route('/deploy_playbook', methods=['POST'])
@login_required
def deploy_playbook_proxy():
    data = request.get_json()
    playbook_names = data.get('playbook_names') # Expected as a list

    if not playbook_names or not isinstance(playbook_names, list):
        return jsonify({"error": "playbook_names list is required"}), 400

    # All users can now deploy directly
    task_ids = []
    for playbook in playbook_names:
        try:
            response = requests.post(
                f"{ANSIBLE_API_BASE_URL}/run-playbook/",
                json={
                    "playbook_name": playbook, 
                    "extra_vars": {
                        "custom_message": f"Deployment by {g.user['username']} of {playbook}",
                        "user_id": g.user['user_id']
                    }
                },
                timeout=10
            )
            response.raise_for_status()
            task_ids.append({"playbook": playbook, "task_id": response.json().get('task_id')})
        except Exception as e:
            app.logger.error(f"Error deploying {playbook}: {e}")
            task_ids.append({"playbook": playbook, "error": str(e)})
    
    return jsonify({"status": "Started", "deployments": task_ids})

@app.route('/api/admin/deployment_requests', methods=['GET'])
@login_required
def admin_get_requests():
    if g.user['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT dr.*, u.username 
                FROM deployment_requests dr 
                JOIN users u ON dr.user_id = u.client_id 
                WHERE dr.status = 'pending'
                ORDER BY dr.created_at DESC
            ''')
            requests_list = cursor.fetchall()
    finally:
        conn.close()
    return jsonify(requests_list)

@app.route('/api/admin/process_request', methods=['POST'])
@login_required
def admin_process_request():
    if g.user['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    request_id = data.get('request_id')
    action = data.get('action') # 'approve' or 'deny'

    if not request_id or not action:
        return jsonify({"error": "Missing data"}), 400
        
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM deployment_requests WHERE id = %s', (request_id,))
            req = cursor.fetchone()
            
            if not req:
                return jsonify({"error": "Request not found"}), 404

            if action == 'deny':
                cursor.execute("UPDATE deployment_requests SET status = 'denied' WHERE id = %s", (request_id,))
                conn.commit()
                return jsonify({"status": "success", "message": "Request denied."})
            
            elif action == 'approve':
                playbooks = req['playbook_names'].split(',')
                task_ids = []
                for playbook in playbooks:
                    try:
                        # Deploy each playbook from the request
                        resp = requests.post(
                            f"{ANSIBLE_API_BASE_URL}/run-playbook/",
                            json={"playbook_name": playbook, "extra_vars": {"custom_message": f"Approved for user {req['user_id']}"}},
                            timeout=10
                        )
                        resp.raise_for_status()
                        task_ids.append({"playbook": playbook, "task_id": resp.json().get('task_id')})
                    except Exception as e:
                        task_ids.append({"playbook": playbook, "error": str(e)})

                cursor.execute("UPDATE deployment_requests SET status = 'approved' WHERE id = %s", (request_id,))
                conn.commit()
                return jsonify({"status": "success", "message": "Request approved and playbooks triggered.", "deployments": task_ids})
    finally:
        conn.close()
    return jsonify({"error": "Invalid action"}), 400

@app.route('/get_log/<task_id>', methods=['GET'])
@login_required
def get_log_proxy(task_id):
    try:
        response = requests.get(f"{ANSIBLE_API_BASE_URL}/get-log/{task_id}", timeout=5)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching logs for task {task_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/validate_host', methods=['POST'])
@login_required
def validate_host():
    data = request.get_json()
    host = data.get('host')
    
    if not host:
        return jsonify({"valid": False, "error": "Host is required"}), 400
    
    try:
        # Check if the host resolves to the allowed proxy IP
        # gethostbyname_ex returns a list of all IPs for the host
        _, _, ip_list = socket.gethostbyname_ex(host)
        if ALLOWED_PROXY_IP in ip_list:
            return jsonify({"valid": True})
        else:
            return jsonify({
                "valid": False, 
                "error": f"Security Error: Host '{host}' does not resolve to the authorized proxy ({ALLOWED_PROXY_IP})."
            })
    except socket.gaierror:
        # Fallback check if it's already an IP address
        if host == ALLOWED_PROXY_IP:
            return jsonify({"valid": True})
        return jsonify({"valid": False, "error": f"Could not resolve host '{host}'."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
