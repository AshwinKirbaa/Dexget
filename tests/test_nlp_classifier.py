from jarvis_integration import _build_standalone_llm_fn
from jarvis.semantic.classifier import classify_intent, Intent
import pytest

llm = _build_standalone_llm_fn()

def test_classifier():
    # test "Would you mind getting the browser ready?"
    res = classify_intent("Would you mind getting the browser ready?", llm)
    assert res.intent == Intent.BROWSER_OPEN

    # test "I feel like listening to the Loser track."
    res = classify_intent("I feel like listening to the Loser track.", llm)
    assert res.intent == Intent.MUSIC_PLAY
    assert "loser" in res.query.lower()

    # test "There's something I want to investigate on the web using Chrome."
    res = classify_intent("There's something I want to investigate on the web using Chrome.", llm)
    assert res.intent == Intent.BROWSER_RESEARCH
    assert "chrome" in res.browser.lower()
    
    # test "I need to research Java 21 features in Chrome."
    res = classify_intent("I need to research Java 21 features in Chrome.", llm)
    assert res.intent == Intent.BROWSER_RESEARCH
    assert "java" in res.topic.lower()
    
    print("All classifier tests passed!")

if __name__ == "__main__":
    test_classifier()
