from jarvis.tools.base import RiskLevel, Tool, ToolResult

def schedule_delay(command: str, delay_seconds: int) -> ToolResult:
    from jarvis.scheduler import scheduler
    job_id = scheduler.schedule_delay(command, delay_seconds)
    return ToolResult(True, observation=f"Scheduled '{command}' to run in {delay_seconds} seconds. Job ID: {job_id}")

def schedule_cron(command: str, cron_expr: str) -> ToolResult:
    from jarvis.scheduler import scheduler
    job_id = scheduler.schedule_cron(command, cron_expr)
    return ToolResult(True, observation=f"Scheduled '{command}' to run on cron '{cron_expr}'. Job ID: {job_id}")

def register(registry) -> None:
    registry.register(Tool(
        name="sys_schedule_delay",
        description="Schedule a command to be executed after a delay.",
        parameters={
            "command": {"type": "str", "required": True},
            "delay_seconds": {"type": "int", "required": True}
        },
        risk_level=RiskLevel.LOW,
        func=schedule_delay,
        category="system"
    ))
    
    registry.register(Tool(
        name="sys_schedule_cron",
        description="Schedule a command to be executed on a cron schedule.",
        parameters={
            "command": {"type": "str", "required": True},
            "cron_expr": {"type": "str", "required": True}
        },
        risk_level=RiskLevel.LOW,
        func=schedule_cron,
        category="system"
    ))
    registry.register(Tool(
        name="sys_schedule_cancel",
        description="Cancel all scheduled jobs.",
        parameters={},
        risk_level=RiskLevel.LOW,
        func=lambda: _cancel_all(),
        category="system"
    ))

def _cancel_all():
    from jarvis.scheduler import scheduler
    scheduler.jobs.clear()
    scheduler.save_jobs()
    return ToolResult(True, observation="All scheduled tasks cancelled.")
