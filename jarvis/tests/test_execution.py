import pytest
import os
from jarvis.router import route, RouteType
from jarvis.command_normalizer import CommandNormalizer
from jarvis.filesystem_executor import execute_filesystem_route

def test_missing_parent_folder_creation():
    cmd = CommandNormalizer.normalize("create folder tester in folder_that_does_not_exist")
    res = route(cmd)
    
    assert res.route_type == RouteType.FILESYSTEM
    
    # Execute the route and ensure it returns success=False
    context = {"current_directory": None}
    outcome = execute_filesystem_route(res.tool_args, context, None)
    
    assert outcome["success"] is False
    assert "couldn't find" in outcome["observation"].lower()

def test_browser_search_does_not_route_to_filesystem():
    cmd = CommandNormalizer.normalize("open brave in default and search hotstar")
    res = route(cmd)
    assert res.route_type == RouteType.WINDOWS
    assert res.tool_name == "win_browser_search"
    assert "hotstar" in res.tool_args.get("query", "")

def test_memory_set_and_get():
    # Set
    cmd_set = CommandNormalizer.normalize("remember that my favorite test directory is tester")
    res_set = route(cmd_set)
    assert res_set.route_type == RouteType.MEMORY
    assert res_set.tool_name == "set"
    assert res_set.tool_args["key"] == "favorite_test_directory"
    assert res_set.tool_args["value"] == "tester"
    
    # Get
    cmd_get = CommandNormalizer.normalize("what is my favorite test directory")
    res_get = route(cmd_get)
    assert res_get.route_type == RouteType.MEMORY
    assert res_get.tool_name == "get"
    assert res_get.tool_args["key"] == "favorite_test_directory"

def test_rag_knowledge_path():
    cmd = CommandNormalizer.normalize("what is RAG")
    res = route(cmd)
    assert res.route_type == RouteType.CONVERSATION

def test_local_media_routing_intact():
    cmd = CommandNormalizer.normalize("play Dexter S07E02 from Movies")
    res = route(cmd)
    assert res.route_type == RouteType.WINDOWS
    assert res.tool_name == "win_play_local_media"

def test_existing_d_path_intact():
    cmd = CommandNormalizer.normalize("open local disk D")
    res = route(cmd)
    assert res.route_type == RouteType.FILESYSTEM
    assert res.tool_args["intent"] == "DRIVE_OPEN"
    assert "D:\\" in res.tool_args["location"]

def test_system_workflow_reaches_agent():
    cmd = CommandNormalizer.normalize("switch to performance mode")
    res = route(cmd)
    assert res.route_type == RouteType.AGENT
