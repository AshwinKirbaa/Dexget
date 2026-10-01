import pytest
from jarvis.command_parser import parse_compound_command
from jarvis.tools.browser_engine import AuthState, ContextMode

def test_command_parser_application():
    cmd = "open calculator and do 2+2"
    parsed = parse_compound_command(cmd)
    assert parsed.primary_intent == "application_workflow"
    assert parsed.target_application == "Calculator"
    assert len(parsed.workflow_steps) == 2
    assert parsed.workflow_steps[1].parameters["expression"] == "2+2"

def test_command_parser_browser():
    cmd = "open chrome, go to gmail, send mail to test@example.com subject hi"
    parsed = parse_compound_command(cmd)
    assert parsed.primary_intent == "application_workflow"
    assert parsed.target_application == "chrome"
    assert parsed.target_website is None
    
    assert len(parsed.workflow_steps) == 2
    assert parsed.workflow_steps[1].action == "secondary_action"
    assert "gmail" in parsed.workflow_steps[1].parameters["expression"]

def test_command_parser_discord():
    cmd = "open discord, join hangout voice call and turn camera on"
    parsed = parse_compound_command(cmd)
    assert parsed.primary_intent == "application_workflow"
    assert parsed.target_application == "Discord"
    assert len(parsed.workflow_steps) == 2
    assert parsed.workflow_steps[0].action == "join_voice_call"
    assert parsed.workflow_steps[1].action == "enable_camera"

def test_command_parser_simple():
    cmd = "play radhimma"
    parsed = parse_compound_command(cmd)
    assert parsed.primary_intent == "unknown"
