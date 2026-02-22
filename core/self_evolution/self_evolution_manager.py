"""
Digital Being — Self-Evolution Manager
Stage 30: Orchestrates the self-improvement process.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from enum import Enum
from pathlib import Path
from typing import Any

from core.self_evolution.code_generator import CodeGenerator
from core.self_evolution.evolution_sandbox import EvolutionSandbox

log = logging.getLogger("digital_being.self_evolution")

class EvolutionMode(Enum):
    """Evolution operation modes"""
    SUPERVISED = "supervised"  # Requires human approval
    SEMI_AUTONOMOUS = "semi_autonomous"  # Auto for safe changes
    AUTONOMOUS = "autonomous"  # Fully autonomous

class ChangeType(Enum):
    """Types of changes"""
    MODULE_CREATION = "module_creation"
    MODULE_UPDATE = "module_update"
    BUG_FIX = "bug_fix"
    OPTIMIZATION = "optimization"
    NEW_FEATURE = "new_feature"

class SelfEvolutionManager:
    """
    Manages the self-evolution process.
    
    Features:
    - Code generation
    - Safe testing
    - Approval workflow
    - Change tracking
    - Rollback support
    - Performance monitoring
    """
    
    def __init__(
        self,
        storage_dir: Path,
        mode: EvolutionMode = EvolutionMode.SUPERVISED
    ) -> None:
        self._storage_dir = storage_dir / "self_evolution"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        
        self._state_path = self._storage_dir / "manager.json"
        self._mode = mode
        
        # Initialize components
        templates_path = self._storage_dir / "templates"
        sandbox_path = self._storage_dir / "sandbox"
        backups_path = self._storage_dir / "backups"
        
        self._code_generator = CodeGenerator(self._storage_dir, templates_path)
        self._sandbox = EvolutionSandbox(self._storage_dir, sandbox_path)
        self._backups_path = backups_path
        self._backups_path.mkdir(parents=True, exist_ok=True)
        
        self._state = {
            "mode": mode.value,
            "changes": [],
            "pending_approvals": [],
            "approved_changes": 0,
            "rejected_changes": 0,
            "rollbacks": 0,
            "evolution_cycles": 0,
        }
        
        self._load_state()
        
        log.info(f"SelfEvolutionManager initialized in {mode.value} mode")
    
    def _load_state(self) -> None:
        """Load manager state"""
        if self._state_path.exists():
            try:
                with self._state_path.open("r", encoding="utf-8") as f:
                    self._state = json.load(f)
                # Restore mode from state
                self._mode = EvolutionMode(self._state.get("mode", "supervised"))
                log.info("SelfEvolutionManager: loaded state")
            except Exception as e:
                log.error(f"SelfEvolutionManager: failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save manager state"""
        try:
            self._state["mode"] = self._mode.value
            with self._state_path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"SelfEvolutionManager: failed to save state: {e}")
    
    def set_mode(self, mode: EvolutionMode) -> None:
        """Change evolution mode."""
        log.info(f"SelfEvolutionManager: changing mode from {self._mode.value} to {mode.value}")
        self._mode = mode
        self._save_state()
    
    def propose_change(
        self,
        change_type: ChangeType,
        description: str,
        module_name: str,
        reasoning: str,
        template: str = "basic_module.py"
    ) -> dict:
        """
        Propose a change to the system.
        
        Args:
            change_type: Type of change
            description: Change description
            module_name: Module to create/modify
            reasoning: Why this change is needed
            template: Code template to use
        
        Returns:
            Proposal result
        """
        log.info(
            f"SelfEvolutionManager: proposing {change_type.value} - {description}"
        )
        
        # Generate code
        gen_result = self._code_generator.generate_module(
            module_name=module_name,
            description=description,
            template=template
        )
        
        if not gen_result["success"]:
            log.error(f"Code generation failed: {gen_result['error']}")
            return {
                "success": False,
                "error": gen_result["error"],
                "proposal_id": None
            }
        
        # Test in sandbox
        test_result = self._sandbox.test_module(
            module_code=gen_result["result"]["code"],
            module_name=module_name
        )
        
        if not test_result["passed"]:
            log.warning(f"Sandbox test failed: {test_result.get('error')}")
            # Still allow proposal but mark as risky
        
        # Create proposal
        proposal = {
            "id": f"proposal_{int(time.time() * 1000)}",
            "type": change_type.value,
            "module_name": module_name,
            "description": description,
            "reasoning": reasoning,
            "code": gen_result["result"]["code"],
            "test_result": test_result,
            "status": "pending",
            "created_at": time.time(),
            "risk_level": "low" if test_result["passed"] else "medium"
        }
        
        # Auto-approve in autonomous mode if tests pass
        if self._mode == EvolutionMode.AUTONOMOUS and test_result["passed"]:
            return self._approve_change(proposal["id"], proposal)
        
        # Auto-approve low-risk changes in semi-autonomous mode
        if (self._mode == EvolutionMode.SEMI_AUTONOMOUS and 
            test_result["passed"] and 
            change_type in [ChangeType.BUG_FIX, ChangeType.OPTIMIZATION]):
            return self._approve_change(proposal["id"], proposal)
        
        # Otherwise add to pending approvals
        self._state["pending_approvals"].append(proposal)
        self._save_state()
        
        log.info(
            f"SelfEvolutionManager: proposal {proposal['id']} created, awaiting approval"
        )
        
        return {
            "success": True,
            "proposal_id": proposal["id"],
            "status": "pending_approval",
            "proposal": proposal
        }
    
    def approve_change(self, proposal_id: str) -> dict:
        """Approve a pending change."""
        # Find proposal
        proposal = None
        for p in self._state["pending_approvals"]:
            if p["id"] == proposal_id:
                proposal = p
                break
        
        if not proposal:
            return {
                "success": False,
                "error": "Proposal not found"
            }
        
        return self._approve_change(proposal_id, proposal)
    
    def _approve_change(self, proposal_id: str, proposal: dict) -> dict:
        """
        Internal method to approve and apply a change.
        
        Args:
            proposal_id: Proposal ID
            proposal: Proposal dict
        
        Returns:
            Application result
        """
        log.info(f"SelfEvolutionManager: approving change {proposal_id}")
        
        # Create backup if file exists
        target_path = Path("core") / f"{proposal['module_name']}.py"
        if target_path.exists():
            self._create_backup(target_path, proposal_id)
        
        try:
            # Write new code
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(proposal["code"], encoding="utf-8")
            
            # Update proposal status
            proposal["status"] = "approved"
            proposal["approved_at"] = time.time()
            
            # Move from pending to changes
            if proposal in self._state["pending_approvals"]:
                self._state["pending_approvals"].remove(proposal)
            
            self._state["changes"].append(proposal)
            self._state["approved_changes"] += 1
            self._state["evolution_cycles"] += 1
            
            self._save_state()
            
            log.info(
                f"SelfEvolutionManager: successfully applied change {proposal_id}"
            )
            
            return {
                "success": True,
                "proposal_id": proposal_id,
                "message": f"Change applied: {proposal['description']}"
            }
        
        except Exception as e:
            log.error(f"Failed to apply change: {e}")
            
            # Restore backup if exists
            if target_path.exists():
                self._restore_backup(proposal_id)
            
            return {
                "success": False,
                "error": str(e)
            }
    
    def reject_change(self, proposal_id: str, reason: str = "") -> dict:
        """Reject a pending change."""
        # Find and remove proposal
        proposal = None
        for p in self._state["pending_approvals"]:
            if p["id"] == proposal_id:
                proposal = p
                break
        
        if not proposal:
            return {
                "success": False,
                "error": "Proposal not found"
            }
        
        proposal["status"] = "rejected"
        proposal["rejection_reason"] = reason
        proposal["rejected_at"] = time.time()
        
        self._state["pending_approvals"].remove(proposal)
        self._state["changes"].append(proposal)
        self._state["rejected_changes"] += 1
        
        self._save_state()
        
        log.info(f"SelfEvolutionManager: rejected change {proposal_id}: {reason}")
        
        return {
            "success": True,
            "proposal_id": proposal_id,
            "message": "Change rejected"
        }
    
    def _create_backup(self, file_path: Path, change_id: str) -> None:
        """Create backup of existing file."""
        backup_path = self._backups_path / f"{change_id}_{file_path.name}"
        try:
            shutil.copy2(file_path, backup_path)
            log.debug(f"Created backup: {backup_path}")
        except Exception as e:
            log.error(f"Failed to create backup: {e}")
    
    def _restore_backup(self, change_id: str) -> bool:
        """Restore backup for a change."""
        # Find backup file
        for backup_file in self._backups_path.glob(f"{change_id}_*"):
            try:
                # Extract original filename
                original_name = backup_file.name.split("_", 1)[1]
                target_path = Path("core") / original_name
                
                shutil.copy2(backup_file, target_path)
                log.info(f"Restored backup: {backup_file}")
                return True
            except Exception as e:
                log.error(f"Failed to restore backup: {e}")
                return False
        
        return False
    
    def rollback_change(self, change_id: str) -> dict:
        """Rollback a previously applied change."""
        # Find change
        change = None
        for c in self._state["changes"]:
            if c["id"] == change_id and c["status"] == "approved":
                change = c
                break
        
        if not change:
            return {
                "success": False,
                "error": "Change not found or not applied"
            }
        
        # Restore backup
        if self._restore_backup(change_id):
            change["status"] = "rolled_back"
            change["rolled_back_at"] = time.time()
            self._state["rollbacks"] += 1
            self._save_state()
            
            log.info(f"SelfEvolutionManager: rolled back change {change_id}")
            
            return {
                "success": True,
                "message": "Change rolled back successfully"
            }
        else:
            return {
                "success": False,
                "error": "No backup found or restore failed"
            }
    
    def get_pending_approvals(self) -> list[dict]:
        """Get list of pending approvals."""
        return self._state["pending_approvals"]
    
    def get_change_history(self, limit: int = 20) -> list[dict]:
        """Get recent change history."""
        return sorted(
            self._state["changes"],
            key=lambda c: c.get("created_at", 0),
            reverse=True
        )[:limit]
    
    def get_stats(self) -> dict:
        """Get evolution statistics."""
        total_changes = self._state["approved_changes"] + self._state["rejected_changes"]
        approval_rate = 0.0
        if total_changes > 0:
            approval_rate = self._state["approved_changes"] / total_changes
        
        return {
            "mode": self._mode.value,
            "evolution_cycles": self._state["evolution_cycles"],
            "pending_approvals": len(self._state["pending_approvals"]),
            "approved_changes": self._state["approved_changes"],
            "rejected_changes": self._state["rejected_changes"],
            "rollbacks": self._state["rollbacks"],
            "approval_rate": approval_rate,
            "code_generator": self._code_generator.get_stats(),
            "sandbox": self._sandbox.get_stats()
        }
