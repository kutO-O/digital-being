"""Celery tasks for Heavy Tick execution with checkpoints."""

from celery import Task
from celery_app import app
from database.models import WorkflowCheckpoint, TaskExecution, get_db
from datetime import datetime
import time
import json


# Adaptive timeouts per step (in seconds)
STEP_TIMEOUTS = {
    "monologue": 30,
    "semantic_context": 10,
    "goal_selection": 90,  # Most complex - multiple LLM calls
    "action": 45,
    "curiosity": 30,
    "self_modification": 25,
    "belief_system": 30,
    "contradiction_resolver": 30,
    "time_perception": 15,
    "social_interaction": 25,
    "meta_cognition": 25,
}


class HeavyTickTask(Task):
    """Base task with checkpoint and tracking support."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Save checkpoint on successful completion."""
        workflow_id = kwargs.get('workflow_id')
        stage = kwargs.get('stage')
        
        if workflow_id and stage:
            save_checkpoint(workflow_id, stage, retval)
        
        # Track execution
        track_task_completion(task_id, 'SUCCESS', result=retval)
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Track task failure."""
        track_task_completion(task_id, 'FAILURE', error=str(exc))
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Track retry attempts."""
        track_task_completion(task_id, 'RETRY', error=str(exc))


def save_checkpoint(workflow_id: str, stage: str, state: dict):
    """Save workflow checkpoint to database."""
    db = next(get_db())
    try:
        checkpoint = WorkflowCheckpoint(
            workflow_id=workflow_id,
            tick_number=state.get('tick_number', 0),
            stage=stage,
            state=state
        )
        db.add(checkpoint)
        db.commit()
    except Exception as e:
        print(f"Failed to save checkpoint: {e}")
        db.rollback()
    finally:
        db.close()


def load_last_checkpoint(workflow_id: str, stage: str = None):
    """Load last checkpoint for workflow recovery."""
    db = next(get_db())
    try:
        query = db.query(WorkflowCheckpoint).filter_by(workflow_id=workflow_id)
        if stage:
            query = query.filter_by(stage=stage)
        checkpoint = query.order_by(WorkflowCheckpoint.created_at.desc()).first()
        return checkpoint.state if checkpoint else None
    finally:
        db.close()


def track_task_completion(task_id: str, status: str, result=None, error=None):
    """Track task execution in database."""
    db = next(get_db())
    try:
        execution = db.query(TaskExecution).filter_by(task_id=task_id).first()
        if execution:
            execution.status = status
            execution.completed_at = datetime.utcnow()
            if execution.started_at:
                duration = (execution.completed_at - execution.started_at).total_seconds() * 1000
                execution.duration_ms = int(duration)
            if result:
                execution.result = result
            if error:
                execution.error_message = error
            if status == 'RETRY':
                execution.retry_count += 1
            db.commit()
    except Exception as e:
        print(f"Failed to track task: {e}")
        db.rollback()
    finally:
        db.close()


@app.task(bind=True, base=HeavyTickTask, max_retries=3, name='heavy_tick.monologue')
def execute_monologue(self, workflow_id: str, tick_number: int, context: dict):
    """Execute monologue generation step."""
    start_time = time.time()
    
    try:
        # Import here to avoid circular dependencies
        from core.heavy_tick import _generate_monologue_internal
        
        result = _generate_monologue_internal(tick_number, context)
        
        return {
            'tick_number': tick_number,
            'monologue': result,
            'duration': time.time() - start_time,
            'context': context
        }
    except Exception as exc:
        # Exponential backoff: 60s, 120s, 240s
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown, max_retries=3)


@app.task(bind=True, base=HeavyTickTask, max_retries=3, name='heavy_tick.goal_selection')
def execute_goal_selection(self, workflow_id: str, tick_number: int, monologue_result: dict):
    """Execute goal selection step (most complex - 90s timeout)."""
    start_time = time.time()
    
    try:
        from core.heavy_tick import _select_goal_internal
        
        result = _select_goal_internal(tick_number, monologue_result)
        
        return {
            'tick_number': tick_number,
            'goal': result,
            'duration': time.time() - start_time,
            'previous_stage': 'monologue'
        }
    except Exception as exc:
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown, max_retries=3)


@app.task(bind=True, base=HeavyTickTask, max_retries=3, name='heavy_tick.action')
def execute_action(self, workflow_id: str, tick_number: int, goal_result: dict):
    """Execute action step."""
    start_time = time.time()
    
    try:
        from core.heavy_tick import _execute_action_internal
        
        result = _execute_action_internal(tick_number, goal_result)
        
        return {
            'tick_number': tick_number,
            'action': result,
            'duration': time.time() - start_time
        }
    except Exception as exc:
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown, max_retries=2)


# Optional steps - can run in parallel
@app.task(bind=True, base=HeavyTickTask, max_retries=2, name='heavy_tick.curiosity')
def execute_curiosity(self, workflow_id: str, tick_number: int, context: dict):
    """Execute curiosity engine step."""
    try:
        from core.heavy_tick import _run_curiosity_internal
        return _run_curiosity_internal(tick_number, context)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30, max_retries=2)


@app.task(bind=True, base=HeavyTickTask, max_retries=2, name='heavy_tick.beliefs')
def execute_beliefs(self, workflow_id: str, tick_number: int, context: dict):
    """Execute belief system step."""
    try:
        from core.heavy_tick import _run_beliefs_internal
        return _run_beliefs_internal(tick_number, context)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30, max_retries=2)


@app.task(bind=True, base=HeavyTickTask, max_retries=2, name='heavy_tick.contradictions')
def execute_contradictions(self, workflow_id: str, tick_number: int, context: dict):
    """Execute contradiction resolver step."""
    try:
        from core.heavy_tick import _run_contradictions_internal
        return _run_contradictions_internal(tick_number, context)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30, max_retries=2)


@app.task(bind=True, base=HeavyTickTask, max_retries=2, name='heavy_tick.social')
def execute_social_interaction(self, workflow_id: str, tick_number: int, context: dict):
    """Execute social interaction step."""
    try:
        from core.heavy_tick import _run_social_internal
        return _run_social_internal(tick_number, context)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=25, max_retries=2)


@app.task(bind=True, base=HeavyTickTask, max_retries=2, name='heavy_tick.meta_cognition')
def execute_meta_cognition(self, workflow_id: str, tick_number: int, context: dict):
    """Execute meta cognition step."""
    try:
        from core.heavy_tick import _run_meta_cognition_internal
        return _run_meta_cognition_internal(tick_number, context)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=25, max_retries=2)