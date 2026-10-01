import pytest
from jarvis.router import route, RouteType
from jarvis.command_normalizer import CommandNormalizer

def test_routing_application_commands():
    # 1. open discord
    res = route(CommandNormalizer.normalize("open discord"))
    assert res.route_type == RouteType.APPLICATION
    assert res.tool_name == "win_open_application"
    assert res.tool_args["app_name"] == "discord"

    # 2. open chrome
    res = route(CommandNormalizer.normalize("open chrome"))
    assert res.route_type == RouteType.APPLICATION
    assert res.tool_name == "win_open_application"
    assert res.tool_args["app_name"] == "chrome"

    # 3. open calculator
    res = route(CommandNormalizer.normalize("open calculator"))
    assert res.route_type == RouteType.APPLICATION
    assert res.tool_name == "win_open_application"
    assert res.tool_args["app_name"] == "calculator"
    
def test_routing_filesystem_commands():
    # 4. open file explorer
    res = route(CommandNormalizer.normalize("open file explorer"))
    assert res.route_type == RouteType.APPLICATION
    assert res.tool_name == "win_open_application"
    assert res.tool_args["app_name"] == "explorer"

    # 5. open local disk D
    res = route(CommandNormalizer.normalize("open local disk D"))
    assert res.route_type == RouteType.FILESYSTEM
    assert res.tool_args["intent"] == "DRIVE_OPEN"

    # 6. open movies folder
    res = route(CommandNormalizer.normalize("open movies folder"))
    assert res.route_type == RouteType.FILESYSTEM
    assert res.tool_args["target_name"] == "movies"

    # 7. open anime folder in D drive
    res = route(CommandNormalizer.normalize("open anime folder in D drive"))
    assert res.route_type == RouteType.FILESYSTEM
    assert res.tool_args["target_name"] == "anime"
    assert res.tool_args["location"] == "D:\\"

    # 8. create folder tester in projects folder
    res = route(CommandNormalizer.normalize("create folder tester in projects folder"))
    assert res.route_type == RouteType.FILESYSTEM
    assert res.tool_args["intent"] == "FILESYSTEM_CREATE"
    assert res.tool_args["target_name"] == "tester"

def test_routing_local_media():
    # 9. play Dexter S07E02 from Movies
    res = route(CommandNormalizer.normalize("play Dexter S07E02 from Movies"))
    assert res.route_type == RouteType.WINDOWS
    assert res.tool_name == "win_play_local_media"
    assert res.tool_args["media_title"] == "dexter"

def test_routing_browser():
    # 10. open brave in default and search hotstar
    res = route(CommandNormalizer.normalize("open brave in default and search hotstar"))
    assert res.route_type == RouteType.WINDOWS
    assert res.tool_name == "win_browser_search"
    assert res.tool_args["browser"] == "brave"
    assert res.tool_args["profile"] == "default"
    assert res.tool_args["query"] == "hotstar"
    
    # 10.b open brave and search github
    res = route(CommandNormalizer.normalize("open brave and search github"))
    assert res.route_type == RouteType.WINDOWS
    assert res.tool_name == "win_browser_search"
    assert res.tool_args["browser"] == "brave"
    assert res.tool_args["profile"] == "default"
    assert res.tool_args["query"] == "github"
    
    # 10.c search youtube in brave
    res = route(CommandNormalizer.normalize("search youtube in brave"))
    assert res.route_type == RouteType.WINDOWS
    assert res.tool_name == "win_browser_search"
    assert res.tool_args["browser"] == "brave"
    assert res.tool_args["profile"] == "default"
    assert res.tool_args["query"] == "youtube"
    
def test_routing_invalid_application():
    # open_this_application_does_not_exist
    res = route(CommandNormalizer.normalize("open_this_application_does_not_exist"))
    assert res.route_type == RouteType.APPLICATION
    assert res.tool_name == "win_open_application"
    assert res.tool_args["app_name"] == "this_application_does_not_exist"
    
    # open application_that_does_not_exist
    res = route(CommandNormalizer.normalize("open application_that_does_not_exist"))
    assert res.route_type == RouteType.APPLICATION
    assert res.tool_name == "win_open_application"
    assert res.tool_args["app_name"] == "application_that_does_not_exist"
    
def test_routing_system():
    # 11. switch to performance mode
    res = route(CommandNormalizer.normalize("switch to performance mode"))
    assert res.route_type == RouteType.AGENT

def test_routing_knowledge():
    # 12. what is RAG
    res = route(CommandNormalizer.normalize("what is RAG"))
    assert res.route_type == RouteType.CONVERSATION

def test_routing_memory():
    # 13. remember a preference
    res = route(CommandNormalizer.normalize("remember that my favorite color is blue"))
    assert res.route_type == RouteType.MEMORY
    assert res.tool_name == "set"

    # 14. retrieve a preference
    res = route(CommandNormalizer.normalize("what is my favorite color"))
    assert res.route_type == RouteType.MEMORY
    assert res.tool_name == "get"
    assert res.tool_args["key"] == "favorite_color"

def test_routing_unsupported_discord():
    # 15. unsupported Discord action
    res = route(CommandNormalizer.normalize("open discord, join Hangout voice call and turn camera on"))
    assert res.route_type == RouteType.AGENT
    assert res.label == "Desktop workflow"

def test_routing_compound():
    # 18. compound command
    res = route(CommandNormalizer.normalize("open calculator and do 2+2"))
    assert res.route_type == RouteType.APPLICATION
    assert len(res.tool_calls) == 2
    assert res.tool_calls[0].name == "win_open_application"
    assert res.tool_calls[1].name == "keyboard_type"

def test_routing_youtube_music_and_local():
    # 1. play Minecraft trailer on youtube
    res = route(CommandNormalizer.normalize("play Minecraft trailer on youtube"))
    assert res.route_type == RouteType.TASK
    assert res.tool_name == "youtube_play"
    assert res.tool_args["query"] == "minecraft trailer"
    
    # 2. play Blinding Lights in youtube music
    res = route(CommandNormalizer.normalize("play Blinding Lights in youtube music"))
    assert res.route_type == RouteType.TASK
    assert res.tool_name == "youtube_music_play"
    assert res.tool_args["query"] == "blinding lights"

    # 3. play Shape of You in youtube music
    res = route(CommandNormalizer.normalize("play Shape of You in youtube music"))
    assert res.route_type == RouteType.TASK
    assert res.tool_name == "youtube_music_play"
    assert res.tool_args["query"] == "shape of you"

    # 4. play Dexter S07E02 from Movies
    res = route(CommandNormalizer.normalize("play Dexter S07E02 from Movies"))
    assert res.route_type == RouteType.WINDOWS
    assert res.tool_name == "win_play_local_media"
    assert res.tool_args["media_title"] == "dexter"
    assert res.tool_args["season"] == 7
    assert res.tool_args["episode"] == 2
    assert res.tool_args["source"] == "movies"

    # 5. play Dexter S07E02 from D:\Movies
    res = route(CommandNormalizer.normalize(r"play Dexter S07E02 from D:\Movies"))
    assert res.route_type == RouteType.WINDOWS
    assert res.tool_name == "win_play_local_media"
    assert res.tool_args["media_title"] == "dexter"
    assert res.tool_args["season"] == 7
    assert res.tool_args["episode"] == 2
    assert res.tool_args["source"] == "D:\\movies"

    # 6. play github tutorial on youtube
    res = route(CommandNormalizer.normalize("play github tutorial on youtube"))
    assert res.route_type == RouteType.TASK
    assert res.tool_name == "youtube_play"
    assert res.tool_args["query"] == "github tutorial"

    # 7. play Arijit Singh in youtube music
    res = route(CommandNormalizer.normalize("play Arijit Singh in youtube music"))
    assert res.route_type == RouteType.TASK
    assert res.tool_name == "youtube_music_play"
    assert res.tool_args["query"] == "arijit singh"
