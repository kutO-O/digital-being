"""Workflow orchestrator for Heavy Tick with parallel execution and recovery."""

import asyncio
import uuid
from typing import Dict, Any, List, Optional
from celery import group, chain
from tasks.heavy_tick_tasks import (
    execute_monologue,
    execute_goal_selection,
    execute_action,
    execute_curiosity,
    execute_beliefs,
    execute_contradictions,
    execute_social_interaction,
    execute_meta_cognition,
    load_last_checkpoint,
    STEP_TIMEOUTS
)
import logging

logger = logging.getLogger('digital_being.orchestrator')


class HeavyTickOrchestrator:
    """Orchestrates Heavy Tick execution with checkpoints and parallel tasks."""
    
    def __init__(self):
        self.logger = logger
    
    async def execute_heavy_tick(self, tick_number: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Heavy Tick workflow with fault tolerance.
        
        Steps:
        1. Check for existing checkpoint (recovery)
        2. Execute critical steps sequentially: monologue → goal → action
        3. Execute optional steps in parallel: curiosity, beliefs, social, etc.
        4. Aggregate results
        
        Args:
            tick_number: Current tick number
            context: Current system state and context
            
        Returns:
            Aggregated results from all steps
        """
        workflow_id = f"heavy_tick_{tick_number}_{uuid.uuid4().hex[:8]}"
        self.logger.info(f"[HeavyTick #{tick_number}] Workflow {workflow_id} starting.")
        
        try:
            # Check if we can recover from previous crash
            checkpoint = load_last_checkpoint(workflow_id)
            if checkpoint:
                self.logger.info(f"[HeavyTick #{tick_number}] Recovered from checkpoint: {checkpoint['stage']}")
                context = checkpoint['context']
            
            # === PHASE 1: Critical Sequential Steps ===
            monologue_result = await self._execute_with_timeout(
                execute_monologue,
                workflow_id,
                tick_number,
                context,
                stage='monologue',
                timeout=STEP_TIMEOUTS['monologue']
            )
            
            if not monologue_result:
                self.logger.error(f"[HeavyTick #{tick_number}] Monologue failed, aborting.")
                return {'status': 'failed', 'stage': 'monologue'}
            
            goal_result = await self._execute_with_timeout(
                execute_goal_selection,
                workflow_id,
                tick_number,
                monologue_result,
                stage='goal_selection',
                timeout=STEP_TIMEOUTS['goal_selection']
            )
            
            if not goal_result:
                self.logger.error(f"[HeavyTick #{tick_number}] Goal selection failed, aborting.")
                return {'status': 'failed', 'stage': 'goal_selection'}
            
            action_result = await self._execute_with_timeout(
                execute_action,
                workflow_id,
                tick_number,
                goal_result,
                stage='action',
                timeout=STEP_TIMEOUTS['action']
            )
            
            # === PHASE 2: Optional Parallel Steps ===
            self.logger.info(f"[HeavyTick #{tick_number}] Starting parallel optional steps.")
            
            optional_tasks = [
                self._execute_with_timeout(
                    execute_curiosity,
                    workflow_id,
                    tick_number,
                    goal_result,
                    stage='curiosity',
                    timeout=STEP_TIMEOUTS['curiosity']
                ),
                self._execute_with_timeout(
                    execute_beliefs,
                    workflow_id,
                    tick_number,
                    goal_result,
                    stage='beliefs',
                    timeout=STEP_TIMEOUTS['belief_system']
                ),
                self._execute_with_timeout(
                    execute_contradictions,
                    workflow_id,
                    tick_number,
                    goal_result,
                    stage='contradictions',
                    timeout=STEP_TIMEOUTS['contradiction_resolver']
                ),
                self._execute_with_timeout(
                    execute_social_interaction,
                    workflow_id,
                    tick_number,
                    goal_result,
                    stage='social',
                    timeout=STEP_TIMEOUTS['social_interaction']
                ),
                self._execute_with_timeout(
                    execute_meta_cognition,
                    workflow_id,
                    tick_number,
                    goal_result,
                    stage='meta_cognition',
                    timeout=STEP_TIMEOUTS['meta_cognition']
                ),
            ]
            
            # Execute all optional tasks in parallel
            optional_results = await asyncio.gather(
                *optional_tasks,
                return_exceptions=True  # Continue even if some fail
            )
            
            # Process results
            curiosity_result, beliefs_result, contradictions_result, social_result, meta_result = optional_results
            
            # Log failures in optional steps (non-critical)
            for name, result in zip(
                ['curiosity', 'beliefs', 'contradictions', 'social', 'meta_cognition'],
                optional_results
            ):
                if isinstance(result, Exception):
                    self.logger.warning(f"[HeavyTick #{tick_number}] Optional step '{name}' failed: {result}")
            
            # === PHASE 3: Aggregate Results ===
            final_result = {
                'workflow_id': workflow_id,
                'tick_number': tick_number,
                'status': 'success',
                'critical_steps': {
                    'monologue': monologue_result,
                    'goal': goal_result,
                    'action': action_result,
                },
                'optional_steps': {
                    'curiosity': curiosity_result if not isinstance(curiosity_result, Exception) else None,
                    'beliefs': beliefs_result if not isinstance(beliefs_result, Exception) else None,
                    'contradictions': contradictions_result if not isinstance(contradictions_result, Exception) else None,
                    'social': social_result if not isinstance(social_result, Exception) else None,
                    'meta_cognition': meta_result if not isinstance(meta_result, Exception) else None,
                }
            }
            
            self.logger.info(f"[HeavyTick #{tick_number}] Workflow {workflow_id} completed successfully.")
            return final_result
            
        except Exception as e:
            self.logger.error(f"[HeavyTick #{tick_number}] Workflow {workflow_id} failed: {e}")
            return {'status': 'error', 'error': str(e), 'workflow_id': workflow_id}
    
    async def _execute_with_timeout(
        self,
        task_func,
        workflow_id: str,
        tick_number: int,
        context: Dict[str, Any],
        stage: str,
        timeout: int
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a Celery task with timeout and error handling.
        
        Args:
            task_func: Celery task function
            workflow_id: Unique workflow identifier
            tick_number: Current tick number
            context: Task context/input
            stage: Stage name for logging
            timeout: Timeout in seconds
            
        Returns:
            Task result or None if failed
        """
        try:
            self.logger.info(f"[HeavyTick #{tick_number}] STEP: {stage} (timeout: {timeout}s)")
            
            # Apply task asynchronously
            async_result = task_func.apply_async(
                kwargs={
                    'workflow_id': workflow_id,
                    'tick_number': tick_number,
                    'context': context,
                    'stage': stage
                },
                soft_time_limit=timeout,
                time_limit=timeout + 10
            )
            
            # Wait for result with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(async_result.get),
                timeout=timeout + 15  # Extra buffer for network overhead
            )
            
            self.logger.info(f"[HeavyTick #{tick_number}] Step '{stage}' completed.")
            return result
            
        except asyncio.TimeoutError:
            self.logger.warning(f"[HeavyTick #{tick_number}] Step '{stage}' timed out after {timeout}s.")
            return None
        except Exception as e:
            self.logger.error(f"[HeavyTick #{tick_number}] Step '{stage}' failed: {e}")
            return None


# Global orchestrator instance
orchestrator = HeavyTickOrchestrator()