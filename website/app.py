from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import functools
import socket
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key-goes-here' # Use a real secret key in production

# Base URL for the Ansible FastAPI application
ANSIBLE_API_BASE_URL = "http://answeb.deployone.test"

# Authorized Proxy IP
ALLOWED_PROXY_IP = "100.121.99.42"

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        else:
            error = 'Invalid username or password'
            
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            error = 'Username and password are required'
        else:
            conn = get_db_connection()
            try:
                hashed_password = generate_password_hash(password)
                conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                            (username, hashed_password))
                conn.commit()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                error = f'User {username} is already registered.'
            finally:
                conn.close()
            
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', user_role=session.get('role'))

@app.route('/api/machines', methods=['GET'])
@login_required
def get_machines():
    conn = get_db_connection()
    if session.get('role') == 'admin':
        machines = conn.execute('SELECT m.*, u.username as owner_name FROM machines m LEFT JOIN users u ON m.owner_id = u.id').fetchall()
    else:
        machines = conn.execute('SELECT * FROM machines WHERE owner_id = ?', (session['user_id'],)).fetchall()
    conn.close()
    
    return jsonify([dict(m) for m in machines])

@app.route('/api/admin/users', methods=['GET'])
@login_required
def admin_get_users():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, role FROM users').fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/admin/unassigned_machines', methods=['GET'])
@login_required
def admin_get_unassigned():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    conn = get_db_connection()
    machines = conn.execute('SELECT * FROM machines WHERE owner_id IS NULL').fetchall()
    conn.close()
    return jsonify([dict(m) for m in machines])

@app.route('/api/admin/assign', methods=['POST'])
@login_required
def admin_assign_machine():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    machine_id = data.get('machine_id')
    user_id = data.get('user_id')
    
    if not machine_id or not user_id:
        return jsonify({"error": "Missing data"}), 400
        
    conn = get_db_connection()
    conn.execute('UPDATE machines SET owner_id = ? WHERE id = ?', (user_id, machine_id))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": "Machine assigned successfully"})

@app.route('/api/admin/user_machines/<int:user_id>', methods=['GET'])
@login_required
def admin_get_user_machines(user_id):
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    conn = get_db_connection()
    machines = conn.execute('SELECT * FROM machines WHERE owner_id = ?', (user_id,)).fetchall()
    conn.close()
    return jsonify([dict(m) for m in machines])

@app.route('/api/admin/unlink', methods=['POST'])
@login_required
def admin_unlink_machine():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    machine_id = data.get('machine_id')
    
    if not machine_id:
        return jsonify({"error": "Missing machine_id"}), 400
        
    conn = get_db_connection()
    conn.execute('UPDATE machines SET owner_id = NULL WHERE id = ?', (machine_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success", "message": "Machine unlinked successfully"})

@app.route('/list_playbooks', methods=['GET'])
@login_required
def list_playbooks_proxy():
    try:
        response = requests.get(f"{ANSIBLE_API_BASE_URL}/list-playbooks/")
        response.raise_for_status()
        return jsonify(response.json())
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

    # If user is admin, deploy directly
    if session.get('role') == 'admin':
        task_ids = []
        for playbook in playbook_names:
            try:
                response = requests.post(
                    f"{ANSIBLE_API_BASE_URL}/run-playbook/",
                    json={"playbook_name": playbook, "extra_vars": {"custom_message": f"Direct Admin Deployment of {playbook}"}},
                    timeout=10
                )
                response.raise_for_status()
                task_ids.append({"playbook": playbook, "task_id": response.json().get('task_id')})
            except Exception as e:
                app.logger.error(f"Error deploying {playbook}: {e}")
                task_ids.append({"playbook": playbook, "error": str(e)})
        
        return jsonify({"status": "Started", "deployments": task_ids})
    
    # If user is not admin, create a request
    else:
        conn = get_db_connection()
        playbooks_str = ",".join(playbook_names)
        conn.execute('INSERT INTO deployment_requests (user_id, playbook_names) VALUES (?, ?)',
                    (session['user_id'], playbooks_str))
        conn.commit()
        conn.close()
        return jsonify({"status": "Requested", "message": "Your deployment request has been sent to the admin for review."})

@app.route('/api/admin/deployment_requests', methods=['GET'])
@login_required
def admin_get_requests():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    conn = get_db_connection()
    requests_list = conn.execute('''
        SELECT dr.*, u.username 
        FROM deployment_requests dr 
        JOIN users u ON dr.user_id = u.id 
        WHERE dr.status = 'pending'
        ORDER BY dr.created_at DESC
    ''').fetchall()
    conn.close()
    return jsonify([dict(r) for r in requests_list])

@app.route('/api/admin/process_request', methods=['POST'])
@login_required
def admin_process_request():
    if session.get('role') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.get_json()
    request_id = data.get('request_id')
    action = data.get('action') # 'approve' or 'deny'

    if not request_id or not action:
        return jsonify({"error": "Missing data"}), 400
        
    conn = get_db_connection()
    req = conn.execute('SELECT * FROM deployment_requests WHERE id = ?', (request_id,)).fetchone()
    
    if not req:
        conn.close()
        return jsonify({"error": "Request not found"}), 404

    if action == 'deny':
        conn.execute("UPDATE deployment_requests SET status = 'denied' WHERE id = ?", (request_id,))
        conn.commit()
        conn.close()
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

        conn.execute("UPDATE deployment_requests SET status = 'approved' WHERE id = ?", (request_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Request approved and playbooks triggered.", "deployments": task_ids})

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
