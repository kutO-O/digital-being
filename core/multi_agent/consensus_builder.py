"""
Digital Being — Consensus Building System
Stage 28: Agents vote on decisions to reach consensus.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.multi_agent.message_broker import MessageBroker

log = logging.getLogger("digital_being.consensus_builder")

class ConsensusBuilder:
    """
    Manages consensus building between agents.
    
    Features:
    - Proposal creation
    - Voting system (approve, reject, abstain)
    - Weighted voting by expertise
    - Quorum requirements
    - Decision history
    """
    
    def __init__(self, agent_id: str, message_broker: MessageBroker, state_path: Path) -> None:
        self._agent_id = agent_id
        self._broker = message_broker
        self._state_path = state_path / f"consensus_{agent_id}.json"
        
        self._state = {
            "proposals_created": [],
            "votes_cast": [],
            "decisions_made": [],
            "participation_rate": 0.0,
        }
        
        self._load_state()
    
    def _load_state(self) -> None:
        """Load consensus state"""
        if self._state_path.exists():
            try:
                with self._state_path.open("r", encoding="utf-8") as f:
                    self._state = json.load(f)
                log.info(f"ConsensusBuilder: loaded state for {self._agent_id}")
            except Exception as e:
                log.error(f"ConsensusBuilder: failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save consensus state"""
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with self._state_path.open("w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"ConsensusBuilder: failed to save state: {e}")
    
    def create_proposal(
        self,
        title: str,
        description: str,
        options: list[str],
        voting_period: int = 300,  # 5 minutes
        quorum: float = 0.5,  # 50% participation required
        requires_majority: bool = True
    ) -> dict:
        """
        Create a new proposal for voting.
        
        Args:
            title: Proposal title
            description: Proposal description
            options: List of voting options (default: ['approve', 'reject', 'abstain'])
            voting_period: Voting period in seconds
            quorum: Minimum participation rate (0-1)
            requires_majority: Whether majority is required
        
        Returns:
            Proposal dict
        """
        proposal = {
            "id": f"proposal_{int(time.time() * 1000)}",
            "creator": self._agent_id,
            "title": title,
            "description": description,
            "options": options if options else ["approve", "reject", "abstain"],
            "votes": {},
            "status": "open",
            "created_at": time.time(),
            "voting_deadline": time.time() + voting_period,
            "quorum": quorum,
            "requires_majority": requires_majority,
            "result": None,
        }
        
        self._state["proposals_created"].append(proposal)
        self._save_state()
        
        log.info(f"ConsensusBuilder: created proposal '{title}' with {len(options)} options")
        
        return proposal
    
    def broadcast_proposal(self, proposal: dict, agents: list[str]) -> None:
        """
        Broadcast proposal to all agents.
        
        Args:
            proposal: Proposal dict
            agents: List of agent IDs to notify
        """
        for agent_id in agents:
            if agent_id != self._agent_id:
                self._broker.send_message(
                    agent_id,
                    {
                        "type": "proposal",
                        "proposal": proposal,
                        "from": self._agent_id
                    }
                )
        
        log.info(f"ConsensusBuilder: broadcast proposal to {len(agents)} agents")
    
    def cast_vote(
        self,
        proposal_id: str,
        vote: str,
        weight: float = 1.0,
        reasoning: str = ""
    ) -> bool:
        """
        Cast vote on a proposal.
        
        Args:
            proposal_id: Proposal ID
            vote: Vote option
            weight: Vote weight (based on expertise)
            reasoning: Optional reasoning
        
        Returns:
            True if vote cast successfully
        """
        try:
            vote_data = {
                "proposal_id": proposal_id,
                "agent": self._agent_id,
                "vote": vote,
                "weight": weight,
                "reasoning": reasoning,
                "timestamp": time.time()
            }
            
            self._state["votes_cast"].append(vote_data)
            self._save_state()
            
            # Find proposal creator and notify
            # (In real system, would look up creator from proposal registry)
            log.info(f"ConsensusBuilder: cast vote '{vote}' on proposal {proposal_id}")
            
            return True
        except Exception as e:
            log.error(f"ConsensusBuilder: failed to cast vote: {e}")
            return False
    
    def tally_votes(self, proposal: dict) -> dict:
        """
        Tally votes for a proposal.
        
        Args:
            proposal: Proposal dict
        
        Returns:
            Tally results
        """
        votes = proposal.get("votes", {})
        total_weight = sum(v["weight"] for v in votes.values())
        
        tally = {}
        for option in proposal["options"]:
            tally[option] = {
                "count": 0,
                "weight": 0.0,
                "percentage": 0.0
            }
        
        for vote_data in votes.values():
            vote = vote_data["vote"]
            weight = vote_data["weight"]
            
            if vote in tally:
                tally[vote]["count"] += 1
                tally[vote]["weight"] += weight
        
        # Calculate percentages
        if total_weight > 0:
            for option in tally:
                tally[option]["percentage"] = (tally[option]["weight"] / total_weight) * 100
        
        return {
            "tally": tally,
            "total_votes": len(votes),
            "total_weight": total_weight,
            "participation_rate": len(votes)  # Would divide by total agents in real system
        }
    
    def finalize_proposal(self, proposal: dict, tally: dict) -> str:
        """
        Finalize proposal based on votes.
        
        Args:
            proposal: Proposal dict
            tally: Vote tally
        
        Returns:
            Decision result (approved, rejected, no_quorum)
        """
        # Check quorum
        # (Simplified: in real system would check against total agent count)
        if tally["total_votes"] < 1:
            result = "no_quorum"
        else:
            # Find winning option
            max_weight = 0.0
            winner = None
            
            for option, data in tally["tally"].items():
                if data["weight"] > max_weight:
                    max_weight = data["weight"]
                    winner = option
            
            # Check if majority required
            if proposal["requires_majority"]:
                if max_weight > tally["total_weight"] / 2:
                    result = winner
                else:
                    result = "no_majority"
            else:
                result = winner
        
        proposal["status"] = "closed"
        proposal["result"] = result
        proposal["finalized_at"] = time.time()
        
        self._state["decisions_made"].append({
            "proposal_id": proposal["id"],
            "result": result,
            "timestamp": time.time()
        })
        
        self._save_state()
        
        log.info(f"ConsensusBuilder: finalized proposal '{proposal['title']}' - result: {result}")
        
        return result
    
    def get_stats(self) -> dict:
        """Get consensus building statistics"""
        return {
            "proposals_created": len(self._state["proposals_created"]),
            "votes_cast": len(self._state["votes_cast"]),
            "decisions_made": len(self._state["decisions_made"]),
            "participation_rate": self._state["participation_rate"]
        }
