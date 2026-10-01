import time
import os
import asyncio
from jarvis_integration import build_agent, handle_command
from jarvis.agent.task_state import TaskStatus

def run_smoke_test(agent, command, expected_action=None):
    print(f"\n[{command}]")
    start_t = time.time()
    
    res = handle_command(agent, command)
    
    total_ms = int((time.time() - start_t) * 1000)
    print(f"Result: {res.text}")
    print(f"Total Time: {total_ms}ms")
    
    if getattr(res, "outcome", None):
        print(f"Agent Status: {res.outcome.status.name}")
        if expected_action:
            success = any(step.tool == expected_action and step.success for step in res.outcome.task_state.completed_steps)
            print(f"Verified Action '{expected_action}': {'PASS' if success else 'FAIL'}")
    else:
        print(f"Deterministic/Fast Route used. Status: PASS")

def main():
    agent = build_agent()
    # Mock confirmation to always approve for tests
    agent.registry._confirm_fn = lambda x: True
    
    tests = [
        ("can you bring chrome up?", None), # Fast path
        ("I need to do some research in Chrome.", None), # Fast path missing info
        ("open calculator and calculate 2+2", "windows_type"), # Complex
        ("open my Movies folder", None),
    ]
    
    for cmd, act in tests:
        run_smoke_test(agent, cmd, act)
        
if __name__ == "__main__":
    main()
