"""
JARVIS Scheduler (Phase 8 Implementation)
Replaces jarvis/scheduler.py with an APScheduler-based implementation.
Supports: run once, interval, daily, weekly, and conditional execution.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import os
import datetime
from typing import Callable, Optional

DB_PATH = os.path.expanduser("~/.jarvis/jobs.sqlite")

class JarvisTaskScheduler:
    def __init__(self, execute_callback: Optional[Callable[[str], None]] = None):
        self.execute_callback = execute_callback
        
        jobstores = {
            'default': SQLAlchemyJobStore(url=f'sqlite:///{DB_PATH}')
        }
        
        self.scheduler = BackgroundScheduler(jobstores=jobstores)
        
    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            
    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
            
    def _execute(self, command: str):
        if self.execute_callback:
            self.execute_callback(command)
            
    def run_once(self, command: str, run_at: datetime.datetime) -> str:
        job = self.scheduler.add_job(
            self._execute,
            DateTrigger(run_date=run_at),
            args=[command]
        )
        return job.id
        
    def run_interval(self, command: str, minutes: int) -> str:
        job = self.scheduler.add_job(
            self._execute,
            IntervalTrigger(minutes=minutes),
            args=[command]
        )
        return job.id
        
    def run_cron(self, command: str, cron_expr: str) -> str:
        job = self.scheduler.add_job(
            self._execute,
            CronTrigger.from_crontab(cron_expr),
            args=[command]
        )
        return job.id
        
    def cancel_job(self, job_id: str) -> bool:
        try:
            self.scheduler.remove_job(job_id)
            return True
        except:
            return False

    def list_jobs(self) -> list:
        return self.scheduler.get_jobs()

# Global singleton
scheduler = JarvisTaskScheduler()
