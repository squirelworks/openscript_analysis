"""Quiz rules taken from the OpenScript shared scripts.

A quiz page carries a user property named Answer.
buttonClick sends the button that was hit.
The click is right when that button's name, or its caption, is the answer.
Letter keys are the same test. Author-only setup is not run at reader level.
"""

from __future__ import annotations


def answer_of(props: dict | None) -> str:
    if not props:
        return ""
    for key, value in props.items():
        if str(key).lower() == "answer":
            return str(value or "").strip()
    return ""


def is_quiz(props: dict | None) -> bool:
    return bool(answer_of(props))


def grade(answer: str, target: str) -> bool:
    """True when the clicked button is the one the book named."""
    left = (answer or "").strip().lower()
    right = (target or "").strip().lower()
    if not left or not right:
        return False
    return left == right
