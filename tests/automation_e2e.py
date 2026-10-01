import time
from jarvis_integration import build_agent, handle_command
from jarvis.agent.task_state import TaskStatus

def test_workflow(agent, command, expected_intent, expected_tools):
    print(f"\n[{command}]")
    start_t = time.time()
    
    # 1. Routing Pass check
    # We intercept the router to check intent
    from jarvis.router import route
    from jarvis.semantic.classifier import classify_intent, Intent
    
    r_start = time.time()
    route_res = route(command)
    actual_intent = None
    if route_res.route_type.name == "AGENT":
        intent_data = classify_intent(command, agent.llm_fn)
        actual_intent = intent_data.intent.value
    else:
        actual_intent = "FAST_PATH"
        
    r_ms = int((time.time() - r_start)*1000)
    
    routing_pass = expected_intent == actual_intent or (expected_intent == "FAST_PATH" and actual_intent == "FAST_PATH")
    
    # 2. Execution Pass check
    e_start = time.time()
    res = handle_command(agent, command)
    e_ms = int((time.time() - e_start)*1000)
    
    execution_pass = False
    verification_pass = False
    
    if getattr(res, "outcome", None):
        steps = res.outcome.task_state.completed_steps
        tools_used = [step.tool for step in steps]
        
        # Check if all expected tools were used
        if all(t in tools_used for t in expected_tools):
            execution_pass = True
            
        # Check if the final status was SUCCESS (meaning verification passed in the tools)
        if res.outcome.status == TaskStatus.COMPLETED:
            verification_pass = True
    else:
        # Fast path
        if expected_tools is None or len(expected_tools) == 0:
            execution_pass = True
            verification_pass = True
            
    print(f"Routing: {r_ms}ms | Execution: {e_ms}ms")
    print(f"ROUTING PASS: {'YES' if routing_pass else 'NO'} (Expected {expected_intent}, got {actual_intent})")
    print(f"EXECUTION PASS: {'YES' if execution_pass else 'NO'} (Tools used matched expected)")
    print(f"VERIFICATION PASS: {'YES' if verification_pass else 'NO'} (Task completed successfully)")
    
    if routing_pass and execution_pass and verification_pass:
        print("FULL PASS: YES")
    else:
        print("FULL PASS: NO")

def main():
    agent = build_agent()
    agent.registry._confirm_fn = lambda x: True
    
    tests = [
        ("can you bring chrome up?", "FAST_PATH", []),
        ("Open calculator and calculate 2+2", "APPLICATION_OPEN", ["windows_launch", "windows_type", "windows_press"]),
        ("Search for Java 21 features in Chrome", "BROWSER_RESEARCH", ["browser_navigate", "browser_type", "browser_press", "browser_observe"]),
        ("I feel like hearing Loser", "MUSIC_PLAY", []),
        ("I need to do some research in Chrome", "BROWSER_RESEARCH", [])
    ]
    
    for cmd, intent, tools in tests:
        test_workflow(agent, cmd, intent, tools)

if __name__ == "__main__":
    main()
