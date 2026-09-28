import threading
import time
import json
import os
import uuid
import datetime
from typing import Dict, Any

class JarvisScheduler:
    def __init__(self, execute_callback=None):
        self.db_path = os.path.expanduser("~/.jarvis/schedule.json")
        self.jobs = {}
        self.running = False
        self.thread = None
        self.execute_callback = execute_callback
        self.load_jobs()
        
    def load_jobs(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r") as f:
                    self.jobs = json.load(f)
            except Exception:
                self.jobs = {}
                
    def save_jobs(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump(self.jobs, f, indent=2)
            
    def schedule_delay(self, command: str, delay_seconds: int):
        job_id = str(uuid.uuid4())
        run_at = time.time() + delay_seconds
        self.jobs[job_id] = {
            "type": "delay",
            "command": command,
            "run_at": run_at
        }
        self.save_jobs()
        return job_id
        
    def schedule_cron(self, command: str, cron_expr: str):
        job_id = str(uuid.uuid4())
        # To keep it simple, we'll store the expr and process it.
        # But for now, let's just do a recurring interval if it's simpler, or assume external cron parser.
        self.jobs[job_id] = {
            "type": "cron",
            "command": command,
            "cron_expr": cron_expr,
            "last_run": time.time()
        }
        self.save_jobs()
        return job_id
        
    def cancel_job(self, job_id: str):
        if job_id in self.jobs:
            del self.jobs[job_id]
            self.save_jobs()
            return True
        return False
        
    def _run_loop(self):
        while self.running:
            now = time.time()
            to_remove = []
            
            for jid, job in list(self.jobs.items()):
                if job["type"] == "delay":
                    if now >= job["run_at"]:
                        if self.execute_callback:
                            self.execute_callback(job["command"])
                        to_remove.append(jid)
                elif job["type"] == "cron":
                    # naive cron fallback if no library: every X seconds if we can parse it, 
                    # but here we just stub the logic
                    pass
                    
            for jid in to_remove:
                if jid in self.jobs:
                    del self.jobs[jid]
            if to_remove:
                self.save_jobs()
                
            time.sleep(1)
            
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

scheduler = JarvisScheduler()
