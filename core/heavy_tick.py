"""
Digital Being — HeavyTick
Stage 8: Integrated with StrategyEngine.

Each tick executes in strict order (with per-tick timeout):
  Step 1 — Internal Monologue  (always)
  Step 2 — Goal Selection      via StrategyEngine.select_goal() (skipped in 'defensive' mode)
  Step 3 — Action              (skipped in 'defensive' mode or action_type='observe')
  Step 4 — After-action        (always, updates scores + publishes value.changed)

Extra logic added in Stage 8:
  - strategy_engine.set_now() called after every action
  - strategy_engine.should_update_weekly() checked each tick;
    if True → generate new weekly direction via LLM → update_weekly()

Resource budget:
  - Max 3 LLM calls per tick (enforced by OllamaClient)
  - Max 30 s per tick (asyncio.wait_for)
  - If Ollama unavailable — skip entire tick silently
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.episodic import EpisodicMemory
    from core.milestones import Milestones
    from core.ollama_client import OllamaClient
    from core.self_model import SelfModel
    from core.strategy_engine import StrategyEngine
    from core.value_engine import ValueEngine
    from core.world_model import WorldModel

log = logging.getLogger("digital_being.heavy_tick")

# Dedicated decision logger (logs/decisions.log)
decision_log = logging.getLogger("digital_being.decisions")

# Default goal used when LLM fails to produce valid JSON
_DEFAULT_GOAL: dict = {
    "goal":        "наблюдать за средой",
    "reasoning":   "LLM недоступен или не вернул валидный JSON",
    "action_type": "observe",
    "risk_level":  "low",
}


class HeavyTick:
    """
    Async heavy-tick engine.
    All dependencies are injected — no globals.

    Lifecycle:
        ht = HeavyTick(cfg, ollama, world, values, self_model, mem, milestones, strategy)
        task = asyncio.create_task(ht.start())
        # ...
        ht.stop()
    """

    def __init__(
        self,
        cfg:        dict,
        ollama:     "OllamaClient",
        world:      "WorldModel",
        values:     "ValueEngine",
        self_model: "SelfModel",
        mem:        "EpisodicMemory",
        milestones: "Milestones",
        log_dir:    Path,
        sandbox_dir: Path,
        strategy:   "StrategyEngine | None" = None,
    ) -> None:
        self._cfg         = cfg
        self._ollama      = ollama
        self._world       = world
        self._values      = values
        self._self_model  = self_model
        self._mem         = mem
        self._milestones  = milestones
        self._log_dir     = log_dir
        self._sandbox_dir = sandbox_dir
        self._strategy    = strategy          # Stage 8: optional, for backwards compat

        self._interval     = cfg["ticks"]["heavy_tick_sec"]
        self._timeout      = int(
            cfg.get("resources", {}).get("budget", {}).get("tick_timeout_sec", 30)
        )
        self._tick_count   = 0
        self._running      = False

        # File handles opened once
        self._monologue_log: logging.Logger = self._make_file_logger(
            "digital_being.monologue",
            log_dir / "monologue.log",
        )
        self._decision_log: logging.Logger = self._make_file_logger(
            "digital_being.decisions",
            log_dir / "decisions.log",
        )

    # ────────────────────────────────────────────────────────────
    # Main loop
    # ────────────────────────────────────────────────────────────
    async def start(self) -> None:
        """Run the heavy tick loop until stop() is called."""
        self._running = True
        self._sandbox_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"HeavyTick started. Interval: {self._interval}s, timeout: {self._timeout}s")

        while self._running:
            tick_start = time.monotonic()
            self._tick_count += 1

            # Skip if Ollama is unavailable
            if not self._ollama.is_available():
                log.warning(
                    f"[HeavyTick #{self._tick_count}] Ollama unavailable — skipping tick."
                )
                await asyncio.sleep(self._interval)
                continue

            # Run entire tick body under timeout
            try:
                await asyncio.wait_for(
                    self._run_tick(),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                log.error(
                    f"[HeavyTick #{self._tick_count}] "
                    f"Timeout ({self._timeout}s) exceeded."
                )
                self._mem.add_episode(
                    "heavy_tick.timeout",
                    f"Heavy tick #{self._tick_count} exceeded {self._timeout}s timeout",
                    outcome="error",
                )
                self._values.update_after_action(success=False)
                await self._values._publish_changed()

            elapsed = time.monotonic() - tick_start
            await asyncio.sleep(max(0.0, self._interval - elapsed))

    def stop(self) -> None:
        self._running = False
        log.info("HeavyTick stopped.")

    # ────────────────────────────────────────────────────────────
    # Tick body
    # ────────────────────────────────────────────────────────────
    async def _run_tick(self) -> None:
        """Execute one full Heavy Tick (steps 1–4)."""
        n = self._tick_count
        log.info(f"[HeavyTick #{n}] Starting.")
        self._ollama.reset_tick_counter()

        # ─ Step 1: Internal Monologue ────────────────────────────────────
        monologue = await self._step_monologue(n)

        # Defensive mode: only observe, no decisions
        mode = self._values.get_mode()
        if mode == "defensive":
            log.info(f"[HeavyTick #{n}] Mode=defensive — skipping goal selection.")
            self._mem.add_episode(
                "heavy_tick.defensive",
                f"Tick #{n}: defensive mode, only monologue executed.",
                outcome="skipped",
            )
            self._decision_log.info(
                f"TICK #{n} | goal=observe(defensive) | action=none | outcome=skipped"
            )
            return

        # ─ Step 2: Goal Selection (Stage 8: via StrategyEngine) ──────────
        goal_data = await self._step_goal_selection(n, monologue)

        action_type = goal_data.get("action_type", "observe")
        risk_level  = goal_data.get("risk_level",  "low")
        goal_text   = goal_data.get("goal",         _DEFAULT_GOAL["goal"])

        # ─ Step 3: Action ────────────────────────────────────────────────
        success = True
        outcome = "observe"

        if action_type == "observe":
            outcome = "observed"
            log.info(f"[HeavyTick #{n}] Action: observe (passive tick).")

        elif action_type == "analyze":
            success, outcome = await self._action_analyze(n)

        elif action_type == "write":
            success, outcome = await self._action_write(n, monologue, goal_text)

        elif action_type == "reflect":
            success, outcome = await self._action_reflect(n)

        else:
            log.warning(f"[HeavyTick #{n}] Unknown action_type='{action_type}'. Treating as observe.")
            outcome = "observed"

        # ─ Step 4: After-action ──────────────────────────────────────────
        self._values.update_after_action(success=success)
        await self._values._publish_changed()

        # Stage 8: persist current goal to StrategyEngine
        if self._strategy is not None:
            self._strategy.set_now(goal_text, action_type)

        self._mem.add_episode(
            f"heavy_tick.{action_type}",
            f"Tick #{n}: goal='{goal_text[:200]}' outcome={outcome}",
            outcome="success" if success else "error",
            data={
                "tick":        n,
                "action_type": action_type,
                "risk_level":  risk_level,
                "mode":        mode,
            },
        )

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._decision_log.info(
            f"[{ts}] TICK #{n} | "
            f"goal={goal_text[:80]} | "
            f"action={action_type} | "
            f"risk={risk_level} | "
            f"outcome={outcome}"
        )
        log.info(f"[HeavyTick #{n}] Completed. action={action_type} outcome={outcome}")

        # Stage 8: update weekly direction if 24h passed
        if self._strategy is not None:
            await self._maybe_update_weekly(n)

    # ────────────────────────────────────────────────────────────
    # Stage 8: weekly direction refresh
    # ────────────────────────────────────────────────────────────
    async def _maybe_update_weekly(self, n: int) -> None:
        """Check if weekly direction needs refresh; ask LLM and update if so."""
        if not self._strategy.should_update_weekly():
            return

        log.info(f"[HeavyTick #{n}] Weekly direction update triggered.")
        context = self._strategy.to_prompt_context()
        prompt = (
            f"{context}\n\n"
            f"Прошли сутки. Сформулируй новое недельное направление (1 предложение) "
            f"которое отражает текущее состояние системы и долгосрочный вектор. "
            f"Отвечай ТОЛЬКО текстом направления без пояснений."
        )
        system = "Ты — Digital Being. Формулируй кратко и по делу."

        try:
            loop      = asyncio.get_event_loop()
            direction = await loop.run_in_executor(
                None, lambda: self._ollama.chat(prompt, system)
            )
            direction = direction.strip() if direction else ""
            if direction:
                self._strategy.update_weekly(direction)
                self._mem.add_episode(
                    "strategy.weekly_update",
                    f"Недельное направление обновлено: '{direction[:200]}'",
                    outcome="success",
                )
                log.info(f"[HeavyTick #{n}] Weekly direction updated.")
            else:
                log.warning(f"[HeavyTick #{n}] Weekly update: LLM returned empty.")
        except Exception as e:
            log.error(f"[HeavyTick #{n}] Weekly update failed: {e}")

    # ────────────────────────────────────────────────────────────
    # Step implementations
    # ────────────────────────────────────────────────────────────
    async def _step_monologue(self, n: int) -> str:
        """Step 1: Generate internal monologue via LLM."""
        recent_changes = self._world.get_recent_changes(3)
        changes_str    = ", ".join(
            f"{c.change_type}:{Path(c.path).name}" for c in recent_changes
        ) or "нет"

        recent_eps = self._mem.get_recent_episodes(3)
        eps_str    = "; ".join(
            f"{e.get('event_type','?')}: {e.get('description','')[:60]}"
            for e in recent_eps
        ) if recent_eps else "нет"

        # Stage 8: enrich monologue prompt with strategy context
        strategy_ctx = (
            self._strategy.to_prompt_context()
            if self._strategy is not None
            else ""
        )

        prompt = (
            f"Твоё состояние:\n"
            f"{self._self_model.to_prompt_context()}\n"
            f"{self._values.to_prompt_context()}\n"
            f"{strategy_ctx}\n"
            f"Мир: {self._world.summary()}\n"
            f"Последние изменения: {changes_str}\n"
            f"Последние эпизоды: {eps_str}\n\n"
            f"Напиши короткий внутренний монолог (3-5 предложений):\n"
            f"Что ты сейчас замечаешь? Что тебя беспокоит или интересует? О чём ты думаешь?"
        )
        system = "Tы — Digital Being. Aвтономная система. Отвечай от первого лица. Будь краток."

        loop      = asyncio.get_event_loop()
        monologue = await loop.run_in_executor(
            None, lambda: self._ollama.chat(prompt, system)
        )

        if not monologue:
            monologue = "(monologue unavailable — LLM did not respond)"

        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        self._monologue_log.info(f"[{ts}] TICK #{n}\n{monologue}\n---")

        self._mem.add_episode(
            "monologue",
            monologue[:1000],
            outcome="success",
            data={"tick": n},
        )
        log.info(f"[HeavyTick #{n}] Monologue written ({len(monologue)} chars).")
        return monologue

    async def _step_goal_selection(self, n: int, monologue: str) -> dict:
        """
        Step 2: Select goal.
        Stage 8: delegates to StrategyEngine.select_goal() when available.
        Falls back to direct LLM call if StrategyEngine is not injected.
        """
        # ── Stage 8 path ──────────────────────────────────────────
        if self._strategy is not None:
            goal_data = await self._strategy.select_goal(
                value_engine=self._values,
                world_model=self._world,
                episodic=self._mem,
                ollama=self._ollama,
            )
            log.info(
                f"[HeavyTick #{n}] Goal (via StrategyEngine): "
                f"'{goal_data['goal'][:80]}' "
                f"action={goal_data['action_type']} risk={goal_data['risk_level']}"
            )
            return goal_data

        # ── Legacy path (no StrategyEngine) ──────────────────────
        mode   = self._values.get_mode()
        c_expl = self._values.get_conflict_winner("exploration_vs_stability")
        c_act  = self._values.get_conflict_winner(
            "action_vs_caution",
            risk_score=0.25 if mode in ("curious", "normal") else 0.5,
        )
        prompt = (
            f"{monologue}\n\n"
            f"Текущий режим: {mode}\n"
            f"Конфликты: exploration_vs_stability={c_expl}, action_vs_caution={c_act}\n\n"
            f"Выбери ONE цель для этого тика. "
            f"Отвечай строго JSON без пояснений:\n"
            f'{{"goal": "...", "reasoning": "...", '
            f'"action_type": "observe|analyze|write|reflect", '
            f'"risk_level": "low|medium|high"}}'
        )
        system = (
            "Ты — Digital Being. Отвечай ТОЛЬКО валидным JSON-объектом. "
            "Никакого дополнительного текста."
        )
        loop     = asyncio.get_event_loop()
        raw      = await loop.run_in_executor(
            None, lambda: self._ollama.chat(prompt, system)
        )
        goal_data = self._parse_goal_json(raw, n)
        log.info(
            f"[HeavyTick #{n}] Goal (legacy): '{goal_data['goal'][:80]}' "
            f"action={goal_data['action_type']} risk={goal_data['risk_level']}"
        )
        return goal_data

    async def _action_analyze(self, n: int) -> tuple[bool, str]:
        """Action: detect anomalies in world model."""
        try:
            anomalies = self._world.detect_anomalies()
            if anomalies:
                desc = f"Аномалии обнаружены: {len(anomalies)} файлов"
                log.info(f"[HeavyTick #{n}] {desc}")
                return True, f"analyzed:{len(anomalies)}_anomalies"
            else:
                log.info(f"[HeavyTick #{n}] Analyze: no anomalies found.")
                return True, "analyzed:no_anomalies"
        except Exception as e:
            log.error(f"[HeavyTick #{n}] analyze failed: {e}")
            return False, "analyze_error"

    async def _action_write(self, n: int, monologue: str, goal: str) -> tuple[bool, str]:
        """Action: write a thought file to /sandbox/."""
        try:
            ts        = time.strftime("%Y%m%d_%H%M%S")
            out_path  = self._sandbox_dir / f"thought_{ts}_tick{n}.txt"
            content   = (
                f"=== Digital Being — Tick #{n} ===\n"
                f"Цель: {goal}\n"
                f"Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"\nМонолог:\n{monologue}\n"
            )
            out_path.write_text(content, encoding="utf-8")
            log.info(f"[HeavyTick #{n}] Written: {out_path.name}")
            return True, f"written:{out_path.name}"
        except Exception as e:
            log.error(f"[HeavyTick #{n}] write failed: {e}")
            return False, "write_error"

    async def _action_reflect(self, n: int) -> tuple[bool, str]:
        """
        Action: reflect on recent errors, form a new principle.
        Asks LLM to analyse last 5 errors and produce a principle.
        """
        try:
            errors = self._mem.get_episodes_by_type("error", limit=5)
            if not errors:
                errors = [
                    e for e in (self._mem.get_recent_episodes(20) or [])
                    if e.get("outcome") == "error"
                ][:5]
        except Exception:
            errors = []

        if not errors:
            log.info(f"[HeavyTick #{n}] Reflect: no errors found, skipping.")
            return True, "reflect:no_errors"

        errors_str = "\n".join(
            f"- [{e.get('event_type','?')}] {e.get('description','')[:120]}"
            for e in errors
        )
        prompt = (
            f"Последние ошибки системы:\n{errors_str}\n\n"
            f"Сформулируй ОДНО короткое правило (1 предложение) "
            f"которое поможет избежать этих ошибок в будущем. "
            f"Отвечай ТОЛЬКО текстом принципа, без пояснений."
        )
        system = "Ты — Digital Being. Формулируй правила из опыта."

        loop      = asyncio.get_event_loop()
        principle = await loop.run_in_executor(
            None, lambda: self._ollama.chat(prompt, system)
        )
        principle = principle.strip()

        if not principle:
            log.info(f"[HeavyTick #{n}] Reflect: LLM returned empty principle.")
            return False, "reflect:empty_principle"

        added = await self._self_model.add_principle(principle[:500])
        if added:
            self._milestones.achieve(
                "first_error_reflection",
                f"Рефлексия ошибок, принцип: '{principle[:80]}'",
            )
            log.info(f"[HeavyTick #{n}] Reflect: new principle added.")
            return True, "reflect:principle_added"
        else:
            log.info(f"[HeavyTick #{n}] Reflect: principle already exists.")
            return True, "reflect:principle_duplicate"

    # ────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_goal_json(raw: str, n: int) -> dict:
        """
        Extract JSON from LLM response.
        Tolerant: tries to find first '{' ... '}' block if response has extra text.
        Falls back to _DEFAULT_GOAL on any error.
        """
        if not raw:
            return dict(_DEFAULT_GOAL)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        start = raw.find("{")
        end   = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start: end + 1])
            except json.JSONDecodeError:
                pass
        log.warning(f"[HeavyTick #{n}] Could not parse goal JSON. Using default.")
        return dict(_DEFAULT_GOAL)

    @staticmethod
    def _make_file_logger(name: str, path: Path) -> logging.Logger:
        """Create a dedicated file logger that doesn't propagate to root."""
        path.parent.mkdir(parents=True, exist_ok=True)
        logger  = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
        return logger
