"""Consensus Voting System for Multi-Agent Decisions.

Enables democratic decision-making across multiple agents:
- Weighted voting by expertise
- Multiple voting strategies
- Quorum requirements
- Conflict resolution
- Vote tracking

Phase 3 - Multi-Agent System
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .agent_registry import AgentInfo, AgentRegistry

log = logging.getLogger("digital_being.multi_agent.consensus")


class VoteOption(Enum):
    """Vote choices."""
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class VotingStrategy(Enum):
    """Voting decision strategies."""
    MAJORITY = "majority"          # >50% approval
    SUPERMAJORITY = "supermajority"  # >=66% approval
    UNANIMOUS = "unanimous"        # 100% approval
    WEIGHTED = "weighted"          # Weighted by expertise


class VoteStatus(Enum):
    """Vote lifecycle status."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class Vote:
    """Individual vote from an agent."""
    agent_id: str
    option: VoteOption
    weight: float = 1.0  # Voting weight
    reason: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0  # How confident (0.0-1.0)


@dataclass
class VotingProposal:
    """Represents a proposal requiring votes."""
    proposal_id: str
    title: str
    description: str
    proposed_by: str
    
    # Voting configuration
    strategy: VotingStrategy
    required_votes: Optional[int] = None  # Quorum
    eligible_agents: Optional[Set[str]] = None
    
    # Options
    options: Dict[str, Any] = field(default_factory=dict)
    
    # Lifecycle
    status: VoteStatus = VoteStatus.PENDING
    created_at: float = field(default_factory=time.time)
    timeout_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Votes
    votes: List[Vote] = field(default_factory=list)
    
    # Result
    result: Optional[VoteOption] = None
    result_confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "description": self.description,
            "proposed_by": self.proposed_by,
            "strategy": self.strategy.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "timeout_at": self.timeout_at,
            "completed_at": self.completed_at,
            "total_votes": len(self.votes),
            "result": self.result.value if self.result else None,
            "result_confidence": self.result_confidence,
            "vote_summary": self._get_vote_summary(),
        }
    
    def _get_vote_summary(self) -> Dict[str, int]:
        """Get summary of votes."""
        summary = {opt.value: 0 for opt in VoteOption}
        for vote in self.votes:
            summary[vote.option.value] += 1
        return summary
    
    def is_expired(self) -> bool:
        """Check if voting period has expired."""
        if self.timeout_at is None:
            return False
        return time.time() > self.timeout_at


class ConsensusVoting:
    """
    Manages consensus-based voting for multi-agent decisions.
    
    Features:
    - Multiple voting strategies
    - Weighted voting by expertise
    - Quorum requirements
    - Automatic tallying
    - Conflict resolution
    
    Example:
        voting = ConsensusVoting(agent_registry)
        
        # Create proposal
        proposal = VotingProposal(
            proposal_id=str(uuid.uuid4()),
            title="Deploy new feature",
            description="Should we deploy the hot reload feature?",
            proposed_by="coordinator",
            strategy=VotingStrategy.MAJORITY,
            required_votes=3,
            timeout_at=time.time() + 300  # 5 min
        )
        
        voting.create_proposal(proposal)
        
        # Cast votes
        await voting.cast_vote(
            proposal.proposal_id,
            "agent_1",
            VoteOption.APPROVE,
            reason="Feature looks stable"
        )
        
        # Check result
        result = voting.get_result(proposal.proposal_id)
    """
    
    def __init__(self, agent_registry: AgentRegistry):
        """
        Args:
            agent_registry: Registry of agents for weighting votes
        """
        self._registry = agent_registry
        self._proposals: Dict[str, VotingProposal] = {}
        self._vote_callbacks: List[Callable[[VotingProposal], None]] = []
        
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        log.info("ConsensusVoting initialized")
    
    def create_proposal(
        self,
        proposal: VotingProposal
    ) -> None:
        """Create a new voting proposal."""
        self._proposals[proposal.proposal_id] = proposal
        
        log.info(
            f"Proposal created: {proposal.proposal_id} "
            f"(title='{proposal.title}', strategy={proposal.strategy.value})"
        )
    
    async def cast_vote(
        self,
        proposal_id: str,
        agent_id: str,
        option: VoteOption,
        reason: Optional[str] = None,
        confidence: float = 1.0
    ) -> bool:
        """Cast a vote on a proposal."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            log.warning(f"Cannot vote on unknown proposal: {proposal_id}")
            return False
        
        # Check status
        if proposal.status != VoteStatus.PENDING:
            log.warning(
                f"Cannot vote on proposal {proposal_id} with status {proposal.status.value}"
            )
            return False
        
        # Check timeout
        if proposal.is_expired():
            log.warning(f"Cannot vote on expired proposal {proposal_id}")
            await self._finalize_proposal(proposal, VoteStatus.TIMEOUT)
            return False
        
        # Check eligibility
        if proposal.eligible_agents and agent_id not in proposal.eligible_agents:
            log.warning(f"Agent {agent_id} not eligible to vote on {proposal_id}")
            return False
        
        # Check if already voted
        if any(v.agent_id == agent_id for v in proposal.votes):
            log.warning(f"Agent {agent_id} already voted on {proposal_id}")
            return False
        
        # Calculate vote weight
        weight = self._calculate_vote_weight(proposal, agent_id)
        
        # Add vote
        vote = Vote(
            agent_id=agent_id,
            option=option,
            weight=weight,
            reason=reason,
            confidence=confidence,
        )
        proposal.votes.append(vote)
        
        log.info(
            f"Vote cast by {agent_id} on {proposal_id}: {option.value} "
            f"(weight={weight:.2f}, confidence={confidence:.2f})"
        )
        
        # Check if we have enough votes
        await self._check_completion(proposal)
        
        return True
    
    def _calculate_vote_weight(self, proposal: VotingProposal, agent_id: str) -> float:
        """Calculate voting weight for an agent."""
        if proposal.strategy != VotingStrategy.WEIGHTED:
            return 1.0
        
        agent = self._registry.get_agent(agent_id)
        if not agent:
            return 1.0
        
        # Base weight from health and success rate
        weight = agent.health_score * agent._calculate_success_rate()
        
        # Boost for relevant capabilities
        # (In real implementation, match proposal topic to capabilities)
        
        return max(0.1, min(2.0, weight))  # Clamp between 0.1 and 2.0
    
    async def _check_completion(self, proposal: VotingProposal) -> None:
        """Check if proposal voting is complete."""
        # Check quorum
        if proposal.required_votes:
            if len(proposal.votes) < proposal.required_votes:
                return  # Not enough votes yet
        
        # Calculate result based on strategy
        result, confidence = self._tally_votes(proposal)
        
        if result:
            proposal.result = result
            proposal.result_confidence = confidence
            await self._finalize_proposal(proposal, VoteStatus.PASSED if result == VoteOption.APPROVE else VoteStatus.FAILED)
    
    def _tally_votes(self, proposal: VotingProposal) -> tuple[Optional[VoteOption], float]:
        """Tally votes and determine result."""
        if not proposal.votes:
            return None, 0.0
        
        # Count votes by option
        counts = {opt: 0.0 for opt in VoteOption}
        total_weight = 0.0
        total_confidence = 0.0
        
        for vote in proposal.votes:
            if vote.option != VoteOption.ABSTAIN:
                counts[vote.option] += vote.weight
                total_weight += vote.weight
                total_confidence += vote.confidence * vote.weight
        
        if total_weight == 0:
            return None, 0.0
        
        # Calculate percentages
        approve_pct = counts[VoteOption.APPROVE] / total_weight
        reject_pct = counts[VoteOption.REJECT] / total_weight
        avg_confidence = total_confidence / total_weight
        
        # Determine result based on strategy
        if proposal.strategy == VotingStrategy.UNANIMOUS:
            if approve_pct == 1.0:
                return VoteOption.APPROVE, avg_confidence
            elif reject_pct > 0:
                return VoteOption.REJECT, avg_confidence
            return None, 0.0
        
        elif proposal.strategy == VotingStrategy.SUPERMAJORITY:
            threshold = 2.0 / 3.0  # 66.67%
            if approve_pct >= threshold:
                return VoteOption.APPROVE, avg_confidence
            elif reject_pct >= threshold:
                return VoteOption.REJECT, avg_confidence
            return None, 0.0
        
        else:  # MAJORITY or WEIGHTED
            threshold = 0.5  # 50%
            if approve_pct > threshold:
                return VoteOption.APPROVE, avg_confidence
            elif reject_pct > threshold:
                return VoteOption.REJECT, avg_confidence
            return None, 0.0
    
    async def _finalize_proposal(self, proposal: VotingProposal, status: VoteStatus) -> None:
        """Finalize proposal with final status."""
        proposal.status = status
        proposal.completed_at = time.time()
        
        log.info(
            f"Proposal {proposal.proposal_id} finalized: {status.value} "
            f"(result={proposal.result.value if proposal.result else 'none'}, "
            f"confidence={proposal.result_confidence:.2f})"
        )
        
        # Trigger callbacks
        for callback in self._vote_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(proposal)
                else:
                    callback(proposal)
            except Exception as e:
                log.error(f"Vote callback error: {e}")
    
    def get_proposal(self, proposal_id: str) -> Optional[VotingProposal]:
        """Get proposal by ID."""
        return self._proposals.get(proposal_id)
    
    def get_result(self, proposal_id: str) -> Optional[VoteOption]:
        """Get voting result for proposal."""
        proposal = self._proposals.get(proposal_id)
        return proposal.result if proposal else None
    
    def get_pending_proposals(self) -> List[VotingProposal]:
        """Get all pending proposals."""
        return [
            p for p in self._proposals.values()
            if p.status == VoteStatus.PENDING
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get voting statistics."""
        total = len(self._proposals)
        
        status_counts = {}
        for status in VoteStatus:
            count = sum(1 for p in self._proposals.values() if p.status == status)
            status_counts[status.value] = count
        
        passed = status_counts.get(VoteStatus.PASSED.value, 0)
        failed = status_counts.get(VoteStatus.FAILED.value, 0)
        
        return {
            "total_proposals": total,
            "status_distribution": status_counts,
            "pass_rate": passed / total if total > 0 else 0.0,
            "fail_rate": failed / total if total > 0 else 0.0,
        }
    
    def on_vote_complete(self, callback: Callable[[VotingProposal], None]) -> None:
        """Register callback for vote completion."""
        self._vote_callbacks.append(callback)
    
    async def start(self) -> None:
        """Start monitoring for timeouts."""
        if self._running:
            log.warning("ConsensusVoting already running")
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        log.info("ConsensusVoting started")
    
    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        log.info("ConsensusVoting stopped")
    
    async def _monitor_loop(self) -> None:
        """Monitor for proposal timeouts."""
        while self._running:
            try:
                # Check for expired proposals
                for proposal in self.get_pending_proposals():
                    if proposal.is_expired():
                        log.warning(f"Proposal {proposal.proposal_id} timed out")
                        await self._finalize_proposal(proposal, VoteStatus.TIMEOUT)
                
                await asyncio.sleep(5)  # Check every 5 seconds
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Monitor loop error: {e}")
                await asyncio.sleep(5)
