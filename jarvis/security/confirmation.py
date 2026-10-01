"""
Confirmation channel abstraction.

The ToolRegistry needs a single `confirm_fn(prompt) -> bool` callable.
This module builds that callable from whatever front-end is active
(terminal input, voice yes/no, or the desktop GUI's dialog) so the
*same* Agent + ToolRegistry work no matter which interface the user is
using - per the spec's "one Agent Core" requirement.
"""
from __future__ import annotations

from typing import Callable, Optional


def terminal_confirm_fn(require_confirmation: bool = True) -> Callable[[str], bool]:
    def _confirm(prompt: str) -> bool:
        if not require_confirmation:
            return True
        try:
            answer = input(f"\n[CONFIRM] {prompt} [y/N]: ").strip().lower()
        except EOFError:
            answer = "n"
        return answer in ("y", "yes", "confirm", "do it")
    return _confirm


def voice_confirm_fn(speak_fn: Callable[[str], None], listen_fn: Callable[[], Optional[str]],
                      require_confirmation: bool = True) -> Callable[[str], bool]:
    def _confirm(prompt: str) -> bool:
        if not require_confirmation:
            return True
        speak_fn(prompt + " Say yes to confirm, or no to cancel.")
        answer = listen_fn()
        return bool(answer) and str(answer).strip().lower() in ("y", "yes", "confirm", "do it")
    return _confirm


def auto_deny_confirm_fn() -> Callable[[str], bool]:
    """Safe default for headless/test contexts: never auto-approves risky actions."""
    return lambda prompt: False


def always_allow_confirm_fn() -> Callable[[str], bool]:
    """Only for automated tests of the happy path - never wire this to a real user."""
    return lambda prompt: True
