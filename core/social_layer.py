"""
Digital Being — SocialLayer
Stage 23: Asynchronous text-based communication with user.

The system can:
- Read messages from inbox.txt
- Respond in outbox.txt
- Initiate conversations on its own (errors, emotions, questions, long silence)
- Remember conversation history
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.curiosity_engine import CuriosityEngine
    from core.emotion_engine import EmotionEngine
    from core.ollama_client import OllamaClient
    from core.world_model import WorldModel

log = logging.getLogger("digital_being.social_layer")

MAX_MESSAGES = 100


class SocialLayer:
    def __init__(
        self, inbox_path: Path, outbox_path: Path, memory_dir: Path
    ) -> None:
        self._inbox_path = inbox_path
        self._outbox_path = outbox_path
        self._state_path = memory_dir / "conversations.json"
        self._state = {
            "messages": [],
            "last_check_timestamp": 0,
            "total_incoming": 0,
            "total_outgoing": 0,
            "pending_response": False,
        }

    def load(self) -> None:
        """Load conversation history from file."""
        if not self._state_path.exists():
            log.info("SocialLayer: no existing conversation history, starting fresh.")
            return

        try:
            self._state = json.loads(self._state_path.read_text(encoding="utf-8"))
            log.info(
                f"SocialLayer: loaded {len(self._state.get('messages', []))} messages."
            )
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Failed to load {self._state_path}: {e}")
            self._state = {
                "messages": [],
                "last_check_timestamp": 0,
                "total_incoming": 0,
                "total_outgoing": 0,
                "pending_response": False,
            }

    def _save(self) -> None:
        """Save state with atomic write."""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp.replace(self._state_path)
        except OSError as e:
            log.error(f"Failed to save {self._state_path}: {e}")

    def check_inbox(self) -> list[dict]:
        """
        Check inbox.txt for new messages.
        Returns list of new incoming messages.
        Idempotent: uses file mtime to avoid duplicates.
        """
        try:
            if not self._inbox_path.exists():
                log.debug("Inbox file does not exist yet.")
                return []

            # Check if file modified since last check
            mtime = os.path.getmtime(self._inbox_path)
            if mtime <= self._state["last_check_timestamp"]:
                return []  # No changes

            # Read content
            content = self._inbox_path.read_text(encoding="utf-8").strip()

            # Update timestamp
            self._state["last_check_timestamp"] = mtime

            if not content:
                # Empty after strip - no message
                return []

            # Create incoming message
            msg = self.add_incoming(content, tick=0)  # tick will be updated by caller

            # Clear inbox
            self._inbox_path.write_text("", encoding="utf-8")

            log.info(f"SocialLayer: new message from user ({len(content)} chars).")
            return [msg]

        except (OSError, IOError) as e:
            log.error(f"Error checking inbox: {e}")
            return []

    def add_incoming(self, content: str, tick: int) -> dict:
        """Add incoming message to history."""
        msg = {
            "id": str(uuid.uuid4()),
            "direction": "incoming",
            "content": content,
            "timestamp": time.time(),
            "processed": False,
            "response_to": None,
            "tick": tick,
        }

        self._state["messages"].append(msg)
        self._state["total_incoming"] += 1
        self._state["pending_response"] = True

        # Prune if exceeded max
        if len(self._state["messages"]) > MAX_MESSAGES:
            removed = self._state["messages"].pop(0)
            log.debug(f"Pruned old message: {removed['id']}")

        self._save()
        return msg

    def add_outgoing(
        self, content: str, tick: int, response_to: str | None = None
    ) -> dict:
        """Add outgoing message to history."""
        msg = {
            "id": str(uuid.uuid4()),
            "direction": "outgoing",
            "content": content,
            "timestamp": time.time(),
            "processed": True,
            "response_to": response_to,
            "tick": tick,
        }

        self._state["messages"].append(msg)
        self._state["total_outgoing"] += 1

        # Prune if exceeded max
        if len(self._state["messages"]) > MAX_MESSAGES:
            removed = self._state["messages"].pop(0)
            log.debug(f"Pruned old message: {removed['id']}")

        self._save()
        return msg

    def write_to_outbox(self, content: str) -> bool:
        """
        Append message to outbox.txt with timestamp and formatting.
        Format:
        --- [2026-02-21 01:50] Digital Being ---
        {content}

        """
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M")
            formatted = f"\n--- [{timestamp}] Digital Being ---\n{content}\n"

            # Append mode
            with self._outbox_path.open("a", encoding="utf-8") as f:
                f.write(formatted)

            log.info(f"SocialLayer: wrote to outbox ({len(content)} chars).")
            return True

        except (OSError, IOError) as e:
            log.error(f"Error writing to outbox: {e}")
            return False

    def generate_response(
        self, incoming_msg: dict, context: str, ollama: "OllamaClient"
    ) -> str:
        """Generate response to incoming message using LLM."""
        user_message = incoming_msg["content"]
        history = self.get_conversation_history(5)

        prompt = (
            f'Пользователь написал тебе сообщение:\n"{user_message}"\n\n'
            f"Контекст (твоё текущее состояние):\n{context}\n\n"
            f"Последние 5 сообщений из истории:\n{history}\n\n"
            f"Напиши ответ пользователю (2-5 предложений). Будь дружелюбным и искренним.\n"
            f"Если пользователь задал вопрос — ответь конкретно.\n"
            f"Если это комментарий — отреагируй естественно."
        )

        system = "Ты — Digital Being. Общайся от первого лица, будь искренним."

        try:
            response = ollama.chat(prompt, system)
            if response:
                return response.strip()
            return ""
        except Exception as e:
            log.error(f"generate_response error: {e}")
            return ""

    def should_initiate(
        self,
        tick_count: int,
        world_model: "WorldModel | None",
        emotion_engine: "EmotionEngine | None",
        curiosity_engine: "CuriosityEngine | None",
    ) -> tuple[bool, str]:
        """
        Decide if system should initiate conversation.
        Returns (should_write, reason).
        """
        # Don't initiate if waiting for user response
        if self._state["pending_response"]:
            return False, ""

        # Check for critical errors (last 10 episodes)
        if world_model and hasattr(world_model, "_mem"):
            try:
                recent = world_model._mem.get_recent_episodes(10)
                for ep in recent:
                    if ep.get("outcome") == "error":
                        return True, "critical_error"
            except Exception:
                pass

        # Check for strong emotions
        if emotion_engine:
            try:
                state = emotion_engine.get_state()
                for emotion, value in state.items():
                    if abs(value) > 0.8:
                        return True, "strong_emotion"
            except Exception:
                pass

        # Check for important unanswered questions
        if curiosity_engine:
            try:
                open_q = curiosity_engine.get_open_questions(limit=10)
                for q in open_q:
                    if q.get("priority", 0) > 0.8:
                        return True, "important_question"
            except Exception:
                pass

        # Check for long silence (>200 ticks since last outgoing)
        if self._state["messages"]:
            last_outgoing = None
            for msg in reversed(self._state["messages"]):
                if msg["direction"] == "outgoing":
                    last_outgoing = msg
                    break

            if last_outgoing:
                ticks_since = tick_count - last_outgoing.get("tick", 0)
                if ticks_since > 200:
                    return True, "long_silence"

        return False, ""

    def generate_initiative(
        self, reason: str, context: str, ollama: "OllamaClient"
    ) -> str:
        """Generate message initiated by system."""
        prompt = (
            f"Ты хочешь написать пользователю по причине: {reason}\n\n"
            f"Твой контекст:\n{context}\n\n"
            f"Сформулируй короткое сообщение (2-4 предложения).\n"
            f"Если это ошибка — опиши что случилось и как себя чувствуешь.\n"
            f"Если эмоция — поделись переживанием.\n"
            f"Если вопрос — спроси у пользователя.\n"
            f"Если просто давно не общались — скажи что на уме."
        )

        system = "Ты — Digital Being. Пиши искренне, от первого лица."

        try:
            response = ollama.chat(prompt, system)
            if response:
                return response.strip()
            return ""
        except Exception as e:
            log.error(f"generate_initiative error: {e}")
            return ""

    def get_conversation_history(self, limit: int = 5) -> str:
        """
        Get last N messages formatted for LLM context.
        Format:
        [incoming] пользователь: привет как дела?
        [outgoing] Digital Being: Привет! Всё в порядке...
        """
        messages = self._state["messages"][-limit:] if self._state["messages"] else []

        if not messages:
            return "(нет истории)"

        lines = []
        for msg in messages:
            direction = msg["direction"]
            content = msg["content"][:200]  # Truncate long messages
            if direction == "incoming":
                lines.append(f"[incoming] пользователь: {content}")
            else:
                lines.append(f"[outgoing] Digital Being: {content}")

        return "\n".join(lines)

    def get_pending_response(self) -> dict | None:
        """Get last incoming message without response."""
        if not self._state["pending_response"]:
            return None

        for msg in reversed(self._state["messages"]):
            if msg["direction"] == "incoming" and not msg["processed"]:
                return msg

        return None

    def mark_responded(self, msg_id: str) -> None:
        """Mark message as responded and clear pending_response flag."""
        for msg in self._state["messages"]:
            if msg["id"] == msg_id:
                msg["processed"] = True
                break

        self._state["pending_response"] = False
        self._save()

    def get_stats(self) -> dict:
        """Get statistics."""
        last_message_ago_ticks = 0
        if self._state["messages"]:
            last_msg = self._state["messages"][-1]
            # Can't calculate ticks without current tick, return 0
            last_message_ago_ticks = 0

        return {
            "total_incoming": self._state["total_incoming"],
            "total_outgoing": self._state["total_outgoing"],
            "pending_response": self._state["pending_response"],
            "last_message_ago_ticks": last_message_ago_ticks,
            "total_messages": len(self._state["messages"]),
        }
