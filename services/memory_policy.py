"""
Memory policies: importance scoring, simple event extraction, and summarization.
Lightweight and rule-based for MVP.
"""
from __future__ import annotations
import re
from typing import Dict, Optional

IMPORTANT_PATTERNS = [
    r"我喜欢[，。,.]?|我不喜欢|以后请|记住|我的名字|我住在|我的生日|我偏好|请永远|不要|务必",
]

class MemoryPolicy:
    def __init__(self, config: Dict):
        self.cfg = config
        self.threshold = float(self.cfg.get("importance_threshold", 0.5))

    def importance(self, text: str) -> float:
        score = 0.0
        for p in IMPORTANT_PATTERNS:
            if re.search(p, text, flags=re.IGNORECASE):
                score += 0.6
        score += min(len(text) / 2000.0, 0.4)
        return min(score, 1.0)

    def should_persist(self, text: str) -> bool:
        return self.importance(text) >= self.threshold

    def summarize(self, user: str, assistant: str) -> str:
        # ultra-light summary: keep salient sentences up to ~2
        def pick_sentences(s: str, n: int = 2):
            parts = re.split(r"[。.!?！？]\s*", s)
            parts = [p.strip() for p in parts if p.strip()]
            return "。".join(parts[:n])
        u = pick_sentences(user, 1)
        a = pick_sentences(assistant, 1)
        pieces = []
        if u:
            pieces.append(f"用户：{u}")
        if a:
            pieces.append(f"助手：{a}")
        return "；".join(pieces)
