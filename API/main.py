import uvicorn
import subprocess
import os
import uuid
import datetime
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pathlib import Path

app = FastAPI()
LOGS_DIR = Path(__file__).resolve().parent / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

def run_ansible_playbook(cmd: list, log_path: Path):
    try:
        env = os.environ.copy()
        env['ANSIBLE_HOST_KEY_CHECKING'] = 'False'
        env['ANSIBLE_STDOUT_CALLBACK'] = 'yaml'
        cwd = Path(__file__).resolve().parent
        with open(log_path, 'w') as f:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, cwd=cwd)
            for line in process.stdout:
                f.write(line)
                f.flush()
            process.wait()
    except Exception as e:
        with open(log_path, 'a') as f:
            f.write(f'\nInternal Error: {e}\n')

@app.get('/list-playbooks/')
async def list_playbooks():
    playbooks = []
    base_dir = Path(__file__).resolve().parent
    services_dir = base_dir / 'deployone' / 'services'
    if services_dir.exists():
        for path in services_dir.rglob('*.yml'):
            if 'vars' in path.parts or path.name == 'secrets.yml': continue
            try:
                rel_path = str(path.relative_to(base_dir))
                display_name = path.stem
                playbooks.append({'display_name': display_name, 'full_path': rel_path})
            except ValueError: continue
    return {'playbooks': playbooks}

@app.post('/run-playbook/')
async def run_playbook(request: Request, background_tasks: BackgroundTasks):
    try:
        payload = await request.json()
        playbook_name = payload.get('playbook_name')
        extra_vars = payload.get('extra_vars', {})
        if not playbook_name: raise HTTPException(status_code=400, detail='playbook_name is required')
        task_id = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        log_path = LOGS_DIR / f"{task_id}.log"
        
        # Robust path resolution
        full_path = playbook_name
        if not os.path.exists(full_path):
            p1 = os.path.join('deployone', 'services', playbook_name)
            p2 = os.path.join('deployone', 'services', playbook_name + '.yml')
            if os.path.exists(p1): full_path = p1
            elif os.path.exists(p2): full_path = p2
        
        cmd = ['ansible-playbook', full_path, '--extra-vars', 'ansible_ssh_extra_args="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"']
        for key, value in extra_vars.items(): cmd.extend(['-e', f"{key}='{value}'"])
        background_tasks.add_task(run_ansible_playbook, cmd, log_path)
        return {'status': 'Started', 'task_id': task_id}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get('/get-log/{task_id}')
async def get_log(task_id: str):
    log_path = LOGS_DIR / f'{task_id}.log'
    if not log_path.exists(): return {'log': 'Loading logs...', 'status': 'pending'}
    with open(log_path, 'r') as f: content = f.read()
    is_finished = 'PLAY RECAP' in content
    status = 'success' if is_finished and 'failed=0' in content and 'unreachable=0' in content else ('failed' if is_finished else 'running')
    return {'log': content, 'finished': is_finished, 'status': status}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
