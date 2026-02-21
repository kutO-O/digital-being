"""Celery tasks package."""

from tasks.heavy_tick_tasks import (
    execute_monologue,
    execute_goal_selection,
    execute_action,
    execute_curiosity,
    execute_beliefs,
    execute_contradictions,
    execute_social_interaction,
    execute_meta_cognition,
)