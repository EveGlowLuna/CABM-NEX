"""
MemoryRouter: multi-source recall and prompt assembly.
MVP: combine short-term buffer, summaries, profile, and vector search results.
"""
from __future__ import annotations
from typing import Dict, Optional, Tuple, List

from config import get_memory_config
from utils.memory import (
    ShortTermBufferStore,
    SummaryStore,
    ProfileStore,
    VectorStoreAdapter,
)


class MemoryRouter:
    def __init__(self, scope_id: str, is_story: bool = False, root_dir: str = "data/memory"):
        self.scope_id = scope_id
        self.is_story = is_story
        self.root_dir = root_dir
        self.cfg = get_memory_config()
        self.buffer = ShortTermBufferStore(root_dir, scope_id)
        self.summaries = SummaryStore(root_dir, scope_id)
        self.profile = ProfileStore(root_dir, scope_id)
        self.vector = VectorStoreAdapter(scope_id, is_story=is_story)

    def _assemble(self, parts: List[str], token_budget: int) -> str:
        if not parts:
            return ""
        # approx char budget for zh: ~2 chars per token
        char_budget = int(token_budget * 2)
        text = "\n\n".join([p for p in parts if p])
        if len(text) <= char_budget:
            return text
        # truncate safely
        return text[:char_budget]

    def recall(self, query: str, token_budget: Optional[int] = None) -> str:
        cfg = self.cfg
        if token_budget is None:
            token_budget = int(cfg.get("token_budget", 512))
        top_k = int(cfg.get("top_k", 5))
        timeout = int(cfg.get("timeout", 10))

        parts: List[str] = []

        # profile
        prof = self.profile.to_prompt()
        if prof:
            parts.append(prof)

        # summaries (latest few)
        summs = self.summaries.top(k=min(3, top_k))
        if summs:
            parts.append("[对话摘要]\n" + "\n".join(f"- {s}" for s in summs))

        # short-term buffer (recent turns)
        recent = self.buffer.get_recent(n=min(4, top_k))
        if recent:
            buf_lines = []
            for t in recent:
                buf_lines.append(f"用户：{t.user}")
                buf_lines.append(f"助手：{t.assistant}")
            parts.append("[最近对话片段]\n" + "\n".join(buf_lines))

        # vector recall
        vec = self.vector.search(query=query, top_k=top_k, timeout=timeout)
        if vec:
            parts.append("[历史语义记忆]\n" + vec)

        if not parts:
            return ""
        header = "[相关记忆] 以下信息用于帮助你更一致地回复，请结合使用，不要重复："
        return self._assemble([header] + parts, token_budget=token_budget)
