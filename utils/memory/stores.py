"""
Memory stores for the refactored memory system.
Provide minimal, file-based implementations to avoid new heavy deps.
"""
from __future__ import annotations
import json
import os
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple, Any

# Reuse existing vector DB implementation
from utils.memory_utils import ChatHistoryVectorDB
from config import get_RAG_config, get_memory_config


@dataclass
class ChatTurn:
    user: str
    assistant: str
    timestamp: Optional[str] = None


class ShortTermBufferStore:
    """Keep the most recent N chat turns per scope (character/story)."""
    def __init__(self, root_dir: str, scope_id: str):
        self.scope_id = scope_id
        self.buffer_size = int(get_memory_config().get("buffer_size", 6))
        self.path = Path(root_dir) / scope_id / "buffer.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer: Deque[ChatTurn] = deque(maxlen=self.buffer_size)
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                turns = [ChatTurn(**x) for x in data]
                self._buffer = deque(turns, maxlen=self.buffer_size)
            except Exception:
                # corrupted file, ignore
                self._buffer = deque(maxlen=self.buffer_size)

    def _save(self):
        try:
            data = [vars(t) for t in self._buffer]
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add_turn(self, user: str, assistant: str, timestamp: Optional[str] = None):
        self._buffer.append(ChatTurn(user=user, assistant=assistant, timestamp=timestamp))
        self._save()

    def get_recent(self, n: Optional[int] = None) -> List[ChatTurn]:
        if n is None:
            return list(self._buffer)
        return list(self._buffer)[-n:]


class SummaryStore:
    """Hold conversation summaries as lightweight long-term memory."""
    def __init__(self, root_dir: str, scope_id: str):
        self.scope_id = scope_id
        self.path = Path(root_dir) / scope_id / "summaries.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._items = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._items = []

    def _save(self):
        try:
            self.path.write_text(json.dumps(self._items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add_summary(self, text: str, meta: Optional[Dict[str, Any]] = None):
        self._items.append({"text": text, "meta": meta or {}})
        self._save()

    def top(self, k: int = 3) -> List[str]:
        return [x.get("text", "") for x in self._items[-k:]]


class ProfileStore:
    """Simple key-value profile store (facts/preferences)."""
    def __init__(self, root_dir: str, scope_id: str):
        self.path = Path(root_dir) / scope_id / "profile.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self):
        try:
            self.path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def set(self, key: str, value: Any):
        self._data[key] = value
        self._save()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def to_prompt(self) -> str:
        if not self._data:
            return ""
        pairs = [f"- {k}: {v}" for k, v in self._data.items()]
        return "[已知的长期档案/偏好]\n" + "\n".join(pairs)


class VectorStoreAdapter:
    """Adapter wrapping the existing ChatHistoryVectorDB as a vector store."""
    def __init__(self, scope_id: str):
        self.scope_id = scope_id
        self.db = ChatHistoryVectorDB(RAG_config=get_RAG_config(), character_name=scope_id)
        # Ensure underlying DB exists
        self.db.initialize_database()

    def add_chat_turn(self, user: str, assistant: str):
        self.db.add_chat_turn(user, assistant)
        try:
            self.db.save_to_file()
        except Exception:
            pass

    def search(self, query: str, top_k: int, timeout: int) -> str:
        return self.db.get_relevant_memory(query, top_k, timeout)
