from unittest.mock import Mock, patch

from jarvis import model_runtime


def test_release_model_unloads_and_terminates_ollama_processes():
    managed = Mock()
    managed.poll.side_effect = [None, 0]
    external = Mock()
    external.info = {"name": "ollama.exe"}
    external.pid = 99999

    model_runtime._managed_process = managed
    model_runtime._model_used_since_release = True
    with patch.object(model_runtime, "_request") as request, \
         patch.object(model_runtime.os, "name", "nt"), \
         patch("psutil.process_iter", return_value=[external]), \
         patch("psutil.wait_procs", return_value=([external], [])):
        model_runtime.release_model("gemma3:4b", stop_server=True)

    assert request.call_args.args[1]["keep_alive"] == 0
    managed.terminate.assert_called_once()
    external.terminate.assert_called_once()
    assert model_runtime._managed_process is None
    assert model_runtime._model_used_since_release is False


def test_release_model_is_noop_when_no_task_used_ollama():
    model_runtime._managed_process = None
    model_runtime._model_used_since_release = False
    with patch.object(model_runtime, "_request") as request:
        model_runtime.release_model()
    request.assert_not_called()
