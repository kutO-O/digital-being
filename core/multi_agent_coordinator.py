"""
Digital Being - Multi-Agent Coordinator
Stage 27-28: Coordinates multi-agent communication and collaboration with advanced features.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Any

from core.agent_registry import AgentRegistry, AgentInfo
from core.message_broker import MessageBroker
from core.message_protocol import Message, MessageBuilder, MessageType, Priority
from core.skill_exchange import SkillExchange

# Stage 28 imports
from core.multi_agent.task_delegation import TaskDelegation
from core.multi_agent.consensus_builder import ConsensusBuilder
from core.multi_agent.agent_roles import AgentRoleManager, AgentRole

if TYPE_CHECKING:
    from core.skill_library import SkillLibrary

log = logging.getLogger("digital_being.multi_agent")


class MultiAgentCoordinator:
    """Coordinates multi-agent communication and collaboration with advanced features."""
    
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        specialization: str,
        skill_library: "SkillLibrary",
        config: dict,
        storage_dir: Path
    ):
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._specialization = specialization
        self._skill_library = skill_library
        self._config = config
        self._storage_dir = storage_dir / "multi_agent"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        # Use shared registry path if provided, otherwise use agent-specific
        registry_path = config.get("shared_registry_path")
        if registry_path:
            registry_path = Path(registry_path)
        else:
            registry_path = self._storage_dir / "registry.json"
        
        self._registry = AgentRegistry(registry_path)
        
        # Use shared message storage if provided
        message_storage = config.get("shared_message_storage")
        if message_storage:
            message_storage = Path(message_storage)
        else:
            message_storage = self._storage_dir / "messages"
        
        self._broker = MessageBroker(agent_id, message_storage)
        self._skill_exchange = SkillExchange(agent_id, skill_library, self._broker)
        
        # Stage 28: Advanced features
        self._task_delegation = TaskDelegation(agent_id, self._broker, self._storage_dir)
        self._consensus_builder = ConsensusBuilder(agent_id, self._broker, self._storage_dir)
        self._role_manager = AgentRoleManager(agent_id, self._storage_dir)
        
        # Assign default role based on specialization
        self._assign_default_role()
        
        # Register self in registry
        if config.get("auto_register", True):
            self._register_self()
        
        # Register message handlers
        self._register_handlers()
        
        # Task tracking
        self._delegated_tasks: dict[str, dict] = {}  # task_id -> task_info
        
        # Consensus tracking
        self._consensus_votes: dict[str, dict] = {}  # msg_id -> {question, options, votes}
        
        log.info(
            f"MultiAgentCoordinator initialized: {agent_name} ({agent_id}) - {specialization} "
            f"[Role: {self._role_manager.get_current_role().get('name', 'None') if self._role_manager.get_current_role() else 'None'}]"
        )
    
    def _assign_default_role(self):
        """Assign default role based on specialization."""
        role_mapping = {
            "research": AgentRole.RESEARCHER,
            "analysis": AgentRole.ANALYST,
            "planning": AgentRole.PLANNER,
            "execution": AgentRole.EXECUTOR,
            "testing": AgentRole.TESTER,
            "documentation": AgentRole.DOCUMENTER,
        }
        
        for key, role in role_mapping.items():
            if key in self._specialization.lower():
                self._role_manager.assign_role(role)
                return
        
        # Default to coordinator
        self._role_manager.assign_role(AgentRole.COORDINATOR)
    
    def _register_self(self):
        """Register this agent in the network."""
        network_cfg = self._config.get("network", {})
        self._registry.register(
            agent_id=self._agent_id,
            name=self._agent_name,
            specialization=self._specialization,
            host=network_cfg.get("host", "localhost"),
            port=network_cfg.get("port", 9000),
            capabilities=self._get_capabilities()
        )
    
    def _get_capabilities(self) -> list[str]:
        """Get list of agent capabilities."""
        capabilities = [self._specialization]
        
        # Add role-based capabilities
        role_caps = self._role_manager.get_capabilities()
        capabilities.extend(role_caps)
        
        # Add skill-based capabilities
        for skill in self._skill_library._skills:
            if skill.get("confidence", 0) > 0.7:
                capabilities.append(skill.get("action_type", "unknown"))
        
        return list(set(capabilities))
    
    def _register_handlers(self):
        """Register message handlers."""
        self._broker.register_handler(MessageType.QUERY, self._handle_query)
        self._broker.register_handler(MessageType.TASK, self._handle_task)
        self._broker.register_handler(MessageType.CONSENSUS, self._handle_consensus)
        self._broker.register_handler(MessageType.VOTE, self._handle_vote)
        self._broker.register_handler(MessageType.STATUS, self._handle_status)
    
    async def process_messages(self) -> int:
        """Process pending messages."""
        # Load messages from shared storage first
        self._broker._load_from_disk()
        return await self._broker.process_messages(batch_size=10)
    
    def send_heartbeat(self, current_load: float = 0.0):
        """Send heartbeat to registry."""
        self._registry.heartbeat(self._agent_id, load=current_load)
    
    def send_query(self, to_agent: str, question: str, context: dict | None = None) -> str:
        """Send a query to another agent."""
        message = MessageBuilder.query(
            from_agent=self._agent_id,
            to_agent=to_agent,
            question=question,
            context=context
        )
        msg_id = self._broker.send(message)
        self._broker._save_to_disk()  # Persist immediately
        return msg_id
    
    async def send_query_and_wait(
        self,
        to_agent: str,
        question: str,
        context: dict | None = None,
        timeout: float = 30.0
    ) -> Optional[Any]:
        """Send query and wait for response."""
        msg_id = self.send_query(to_agent, question, context)
        reply = await self._broker.wait_for_reply(msg_id, timeout=timeout)
        
        if reply:
            return reply.payload.get("answer")
        return None
    
    def delegate_task(
        self,
        task: str,
        context: dict | None = None,
        to_agent: Optional[str] = None,
        priority: Priority = Priority.NORMAL
    ) -> str:
        """Delegate a task to another agent using advanced delegation system."""
        # Extract task type and required capabilities
        task_type = context.get("type", "general") if context else "general"
        required_caps = context.get("required_capabilities", []) if context else []
        
        # Create task using TaskDelegation system
        task_obj = self._task_delegation.create_task(
            title=task,
            description=context.get("description", task) if context else task,
            required_capabilities=required_caps,
            priority=priority.value,
            deadline=context.get("deadline") if context else None
        )
        
        # Find best agent if not specified
        if not to_agent:
            # Try to find agent with matching role
            online_agents = self._registry.get_all_online()
            best_agent = None
            best_score = 0
            
            for agent_info in online_agents:
                if agent_info.agent_id == self._agent_id:
                    continue
                
                # Score based on capabilities match
                matching_caps = set(required_caps) & set(agent_info.capabilities)
                score = len(matching_caps)
                
                if score > best_score:
                    best_score = score
                    best_agent = agent_info.agent_id
            
            if not best_agent:
                # Fallback to general task matching
                agent_info = self._registry.get_best_for_task(task_type)
                if agent_info:
                    best_agent = agent_info.agent_id
            
            if not best_agent:
                log.warning(f"No suitable agent found for task: {task}")
                return ""
            
            to_agent = best_agent
        
        # Delegate task
        success = self._task_delegation.delegate_task(task_obj, to_agent)
        
        if success:
            # Also send via message broker for immediate notification
            message = MessageBuilder.delegate_task(
                from_agent=self._agent_id,
                to_agent=to_agent,
                task_description=task,
                context=context,
                priority=priority
            )
            msg_id = self._broker.send(message)
            self._broker._save_to_disk()
            
            # Track delegated task
            self._delegated_tasks[task_obj["id"]] = {
                "task": task,
                "to_agent": to_agent,
                "status": "delegated",
                "context": context
            }
            
            log.info(f"Delegated task to {to_agent}: {task}")
            return task_obj["id"]
        
        return ""
    
    def share_skill(self, skill_id: str, to_agent: str = "*") -> Optional[str]:
        """Share a skill with other agent(s)."""
        msg_id = self._skill_exchange.share_skill(skill_id, to_agent)
        if msg_id:
            self._broker._save_to_disk()
        return msg_id
    
    def broadcast(self, announcement: str, data: dict | None = None) -> str:
        """Broadcast message to all agents."""
        message = MessageBuilder.broadcast(
            from_agent=self._agent_id,
            announcement=announcement,
            data=data
        )
        msg_id = self._broker.send(message)
        self._broker._save_to_disk()  # Persist immediately
        return msg_id
    
    async def request_consensus(
        self,
        question: str,
        options: list[str],
        timeout: int = 30,
        requires_majority: bool = True
    ) -> Optional[str]:
        """Request consensus vote from all agents using ConsensusBuilder."""
        # Create proposal
        proposal = self._consensus_builder.create_proposal(
            title=question,
            description=question,
            options=options,
            voting_period=timeout,
            requires_majority=requires_majority
        )
        
        # Broadcast to all online agents
        online_agents = [a.agent_id for a in self._registry.get_all_online()]
        self._consensus_builder.broadcast_proposal(proposal, online_agents)
        
        # Also send via message broker
        message = MessageBuilder.consensus_request(
            from_agent=self._agent_id,
            question=question,
            options=options,
            timeout=timeout
        )
        
        msg_id = self._broker.send(message)
        self._broker._save_to_disk()
        
        # Initialize vote tracking
        self._consensus_votes[msg_id] = {
            "proposal": proposal,
            "question": question,
            "options": options,
            "votes": {},
            "result": None
        }
        
        # Wait for timeout
        await asyncio.sleep(timeout)
        
        # Tally votes
        return self._tally_votes_advanced(msg_id)
    
    def _tally_votes_advanced(self, consensus_id: str) -> Optional[str]:
        """Tally votes using ConsensusBuilder."""
        if consensus_id not in self._consensus_votes:
            return None
        
        consensus_data = self._consensus_votes[consensus_id]
        proposal = consensus_data["proposal"]
        votes = consensus_data["votes"]
        
        # Update proposal votes
        proposal["votes"] = votes
        
        # Tally
        tally = self._consensus_builder.tally_votes(proposal)
        
        # Finalize
        result = self._consensus_builder.finalize_proposal(proposal, tally)
        
        log.info(f"Consensus reached: {result} for '{consensus_data['question']}'")
        
        consensus_data["result"] = result
        return result
    
    def _tally_votes(self, consensus_id: str) -> Optional[str]:
        """Legacy tally method for backwards compatibility."""
        return self._tally_votes_advanced(consensus_id)
    
    def get_online_agents(self) -> list[AgentInfo]:
        """Get list of all online agents."""
        return self._registry.get_all_online()
    
    def get_agent_by_name(self, name: str) -> Optional[AgentInfo]:
        """Find agent by name."""
        return self._registry.find_by_name(name)
    
    def _handle_query(self, message: Message):
        """Handle incoming query."""
        question = message.payload.get("question")
        log.info(f"Received query from {message.from_agent}: {question}")
        
        # TODO: Generate answer based on agent's knowledge
        # For now, send acknowledgment
        response = MessageBuilder.response(
            from_agent=self._agent_id,
            to_agent=message.from_agent,
            answer="Query received and processing",
            reply_to=message.msg_id,
            success=True
        )
        self._broker.send(response)
        self._broker._save_to_disk()  # Persist response
    
    def _handle_task(self, message: Message):
        """Handle incoming task delegation."""
        task = message.payload.get("task")
        context = message.payload.get("context", {})
        
        log.info(f"Received task from {message.from_agent}: {task}")
        
        # Check if suitable for my role
        task_type = context.get("type", "general")
        is_suitable = self._role_manager.is_suitable_for_task(task_type)
        
        if is_suitable:
            # Accept task
            # Extract task object from context if available
            # For now, create simple task dict
            task_obj = {
                "id": message.msg_id,
                "title": task,
                "creator": message.from_agent,
                "status": "pending"
            }
            
            self._task_delegation.accept_task(task_obj)
            
            status_msg = Message(
                msg_id=str(uuid.uuid4()),
                msg_type=MessageType.STATUS,
                from_agent=self._agent_id,
                to_agent=message.from_agent,
                payload={
                    "task_id": message.msg_id,
                    "status": "accepted",
                    "message": f"Task accepted by {self._role_manager.get_current_role().get('name', self._agent_name)}"
                },
                reply_to=message.msg_id
            )
            self._broker.send(status_msg)
            self._broker._save_to_disk()
        else:
            # Decline task
            status_msg = Message(
                msg_id=str(uuid.uuid4()),
                msg_type=MessageType.STATUS,
                from_agent=self._agent_id,
                to_agent=message.from_agent,
                payload={
                    "task_id": message.msg_id,
                    "status": "declined",
                    "message": f"Task not suitable for my role ({self._role_manager.get_current_role().get('name', 'unknown')})"
                },
                reply_to=message.msg_id
            )
            self._broker.send(status_msg)
            self._broker._save_to_disk()
    
    def _handle_consensus(self, message: Message):
        """Handle consensus request with role-aware voting."""
        question = message.payload.get("question")
        options = message.payload.get("options", [])
        
        log.info(f"Consensus request from {message.from_agent}: {question}")
        
        # Vote based on role expertise
        # TODO: Intelligent voting based on agent's knowledge and role
        # For now, vote based on role preference
        import random
        choice = random.choice(options) if options else None
        
        # Determine vote weight based on expertise
        weight = 1.0
        role_info = self._role_manager.get_current_role()
        if role_info and "strategy" in question.lower() and "planner" in role_info.get("name", "").lower():
            weight = 1.5  # Higher weight for relevant expertise
        
        if choice:
            # Cast vote using ConsensusBuilder
            proposal_id = message.msg_id
            self._consensus_builder.cast_vote(
                proposal_id=proposal_id,
                vote=choice,
                weight=weight,
                reasoning=f"Vote from {role_info.get('name', 'agent') if role_info else 'agent'}"
            )
            
            # Also send via message broker
            vote = MessageBuilder.vote(
                from_agent=self._agent_id,
                to_agent=message.from_agent,
                reply_to=message.msg_id,
                choice=choice,
                reasoning=f"Based on my role as {role_info.get('name', 'agent') if role_info else 'agent'}"
            )
            self._broker.send(vote)
            self._broker._save_to_disk()
    
    def _handle_vote(self, message: Message):
        """Handle incoming vote for consensus."""
        consensus_id = message.reply_to
        if not consensus_id or consensus_id not in self._consensus_votes:
            return
        
        choice = message.payload.get("choice")
        reasoning = message.payload.get("reasoning", "")
        
        # Record vote with weight
        self._consensus_votes[consensus_id]["votes"][message.from_agent] = {
            "vote": choice,
            "weight": message.payload.get("weight", 1.0),
            "reasoning": reasoning
        }
        
        log.debug(
            f"Vote received from {message.from_agent}: {choice} ({reasoning})"
        )
    
    def _handle_status(self, message: Message):
        """Handle status update."""
        task_id = message.payload.get("task_id")
        status = message.payload.get("status")
        
        if task_id in self._delegated_tasks:
            self._delegated_tasks[task_id]["status"] = status
            log.info(
                f"Task {task_id[:8]} status update: {status}"
            )
    
    def get_stats(self) -> dict:
        """Get coordinator statistics including Stage 28 features."""
        role_info = self._role_manager.get_current_role()
        
        return {
            "agent_id": self._agent_id,
            "agent_name": self._agent_name,
            "specialization": self._specialization,
            "current_role": role_info.get("name") if role_info else None,
            "registry": self._registry.get_stats(),
            "broker": self._broker.get_stats(),
            "skill_exchange": self._skill_exchange.get_stats(),
            "task_delegation": self._task_delegation.get_stats(),
            "consensus_building": self._consensus_builder.get_stats(),
            "role_stats": self._role_manager.get_all_stats(),
            "delegated_tasks": len(self._delegated_tasks),
            "active_consensus": len(self._consensus_votes)
        }
