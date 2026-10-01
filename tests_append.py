def test_routing_youtube_music_and_local():
    # 1. play Minecraft trailer on youtube
    res = route(CommandNormalizer.normalize("play Minecraft trailer on youtube"))
    assert res.route_type == RouteType.BROWSER
    assert res.tool_name == "youtube_play"
    assert res.tool_args["query"] == "minecraft trailer"
    
    # 2. play Blinding Lights in youtube music
    res = route(CommandNormalizer.normalize("play Blinding Lights in youtube music"))
    assert res.route_type == RouteType.BROWSER
    assert res.tool_name == "youtube_music_play"
    assert res.tool_args["query"] == "blinding lights"

    # 3. play Shape of You in youtube music
    res = route(CommandNormalizer.normalize("play Shape of You in youtube music"))
    assert res.route_type == RouteType.BROWSER
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
    assert res.route_type == RouteType.BROWSER
    assert res.tool_name == "youtube_play"
    assert res.tool_args["query"] == "github tutorial"

    # 7. play Arijit Singh in youtube music
    res = route(CommandNormalizer.normalize("play Arijit Singh in youtube music"))
    assert res.route_type == RouteType.BROWSER
    assert res.tool_name == "youtube_music_play"
    assert res.tool_args["query"] == "arijit singh"
