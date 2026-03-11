from __future__ import annotations


def grade_from_score(score: float, grade_a: float = 80, grade_b: float = 70) -> str:
    if score >= grade_a:
        return "A"
    if score >= grade_b:
        return "B"
    return "C"
