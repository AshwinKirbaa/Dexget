from jarvis.semantic.local_router import route_natural_language
from jarvis.router import RouteType

def test_research():
    res = route_natural_language("i need to do some research in chrome")
    assert res is not None
    assert res.route_type == RouteType.CHAT
    assert "What would you like me to research in Chrome?" in res.text

def test_music():
    res = route_natural_language("I feel like hearing Loser")
    assert res is not None
    assert res.tool_name == "youtube_play"
    assert res.tool_args["query"] == "loser"
    
def test_search():
    res = route_natural_language("could you search for Java 21 features?")
    assert res is not None
    assert res.tool_name == "browser_open"
    assert "java+21+features" in res.tool_args["url"]
    
def test_open():
    res = route_natural_language("can you bring chrome up?")
    assert res is not None
    assert res.tool_name == "win_open_application"
    assert res.tool_args["app_name"] == "chrome"

if __name__ == "__main__":
    test_research()
    test_music()
    test_search()
    test_open()
    print("All tests passed!")
