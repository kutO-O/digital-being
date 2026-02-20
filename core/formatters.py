"""
Digital Being — Shared Formatters
Common formatting utilities to avoid duplication across modules.

Used by: NarrativeEngine, AttentionSystem, and other components.
"""

from __future__ import annotations


def format_emotions(state: dict) -> str:
    """
    Format emotion state dict into human-readable string.
    Returns: "emotion1=0.75, emotion2=0.62" for emotions > 0.3
    """
    if not state:
        return "(нет данных)"
    
    # Extract emotions dict if state has nested structure
    emotions = state.get("emotions", state) if "emotions" in state else state
    
    significant = {
        k: v for k, v in emotions.items()
        if isinstance(v, (int, float)) and v > 0.3
    }
    if not significant:
        return "(нейтральное)"
    
    sorted_items = sorted(significant.items(), key=lambda x: x[1], reverse=True)
    return ", ".join(f"{k}={v:.2f}" for k, v in sorted_items)


def format_reflections(reflections: list[dict], limit: int = 5) -> str:
    """
    Format reflection log entries into human-readable string.
    Returns: "1) [timestamp] insight text\n2) ..."
    """
    if not reflections:
        return "(нет данных)"
    
    recent = reflections[-limit:] if len(reflections) > limit else reflections
    lines = []
    for i, r in enumerate(recent, 1):
        ts = r.get("timestamp_str", "?")
        insight = r.get("insight", "")[:120]
        lines.append(f"{i}) [{ts}] {insight}")
    
    return "\n".join(lines)


def format_actions(episodes: list) -> str:
    """
    Format episode list into human-readable action summary.
    Returns: "event_type: description\nevent_type: description\n..."
    """
    if not episodes:
        return "(нет данных)"
    
    lines = [
        f"{ep.get('event_type', '?')}: {ep.get('description', '')[:120]}"
        for ep in episodes
    ]
    return "\n".join(lines)
