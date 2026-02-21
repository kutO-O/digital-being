"""
Simplified Multi-Agent Communication Demo
Demonstrates basic agent messaging without LLM.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_registry import AgentRegistry, AgentInfo
from core.message_broker import MessageBroker
from core.message_protocol import MessageBuilder, MessageType, Priority


async def run_alice(storage_dir: Path, registry: AgentRegistry):
    """Alice - Research agent."""
    print("\n[Alice] Starting research agent...")
    
    # Register self
    registry.register(
        agent_id="alice_001",
        name="Alice",
        specialization="research",
        host="localhost",
        port=9000
    )
    
    # Create message broker
    broker = MessageBroker("alice_001", storage_dir / "alice" / "messages")
    
    # Wait for other agents
    await asyncio.sleep(1)
    
    # Check online agents
    agents = registry.get_all_online()
    print(f"[Alice] Found {len(agents)} agents online:")
    for agent in agents:
        print(f"  - {agent.name} ({agent.specialization})")
    
    # Send query to Bob
    print("\n[Alice] Sending query to Bob...")
    query = MessageBuilder.query(
        from_agent="alice_001",
        to_agent="bob_001",
        question="What's the best Python web framework?",
        context={"requirements": ["fast", "async"]}
    )
    broker.send(query)
    print(f"[Alice] Query sent: {query.msg_id[:8]}")
    
    # Delegate task
    print("\n[Alice] Delegating task to Bob...")
    task = MessageBuilder.delegate_task(
        from_agent="alice_001",
        to_agent="bob_001",
        task_description="Create FastAPI endpoint",
        context={"type": "coding"},
        priority=Priority.HIGH
    )
    broker.send(task)
    print(f"[Alice] Task delegated: {task.msg_id[:8]}")
    
    # Wait for reply
    print("\n[Alice] Waiting for Bob's response...")
    reply = await broker.wait_for_reply(query.msg_id, timeout=5.0)
    if reply:
        print(f"[Alice] Got reply: {reply.payload.get('answer')}")
    else:
        print("[Alice] No reply received (timeout)")
    
    # Request consensus
    print("\n[Alice] Broadcasting consensus request...")
    consensus = MessageBuilder.consensus_request(
        from_agent="alice_001",
        question="Which database to use?",
        options=["PostgreSQL", "MongoDB", "SQLite"],
        timeout=5
    )
    broker.send(consensus)
    
    await asyncio.sleep(6)
    
    # Broadcast
    print("\n[Alice] Broadcasting announcement...")
    broadcast = MessageBuilder.broadcast(
        from_agent="alice_001",
        announcement="Phase 1 complete!"
    )
    broker.send(broadcast)
    
    print("\n[Alice] Demo complete!")
    stats = broker.get_stats()
    print(f"[Alice] Sent {stats['total_sent']} messages")


async def run_bob(storage_dir: Path, registry: AgentRegistry):
    """Bob - Coding agent."""
    print("\n[Bob] Starting coding agent...")
    
    # Register self
    registry.register(
        agent_id="bob_001",
        name="Bob",
        specialization="coding",
        host="localhost",
        port=9001
    )
    
    # Create message broker
    broker = MessageBroker("bob_001", storage_dir / "bob" / "messages")
    
    # Handler for queries
    def handle_query(message):
        print(f"\n[Bob] Received query: {message.payload.get('question')}")
        
        # Send response
        response = MessageBuilder.response(
            from_agent="bob_001",
            to_agent=message.from_agent,
            answer="FastAPI is the best!",
            reply_to=message.msg_id
        )
        broker.send(response)
        print(f"[Bob] Sent response: {response.msg_id[:8]}")
    
    # Handler for tasks
    def handle_task(message):
        print(f"\n[Bob] Received task: {message.payload.get('task')}")
        print("[Bob] Task accepted!")
    
    # Handler for consensus
    def handle_consensus(message):
        question = message.payload.get('question')
        options = message.payload.get('options', [])
        print(f"\n[Bob] Consensus request: {question}")
        
        # Vote for first option
        if options:
            vote = MessageBuilder.vote(
                from_agent="bob_001",
                to_agent=message.from_agent,
                reply_to=message.msg_id,
                choice=options[0],
                reasoning="I prefer the first option"
            )
            broker.send(vote)
            print(f"[Bob] Voted for: {options[0]}")
    
    # Register handlers
    broker.register_handler(MessageType.QUERY, handle_query)
    broker.register_handler(MessageType.TASK, handle_task)
    broker.register_handler(MessageType.CONSENSUS, handle_consensus)
    
    # Process messages
    print("[Bob] Processing messages...")
    for i in range(15):
        count = await broker.process_messages()
        if count > 0:
            print(f"[Bob] Processed {count} messages")
        registry.heartbeat("bob_001", load=0.4)
        await asyncio.sleep(0.5)
    
    print("\n[Bob] Demo complete!")
    stats = broker.get_stats()
    print(f"[Bob] Sent {stats['total_sent']} messages, {stats['total_queued']} queued")


async def run_charlie(storage_dir: Path, registry: AgentRegistry):
    """Charlie - Testing agent."""
    print("\n[Charlie] Starting testing agent...")
    
    # Register self
    registry.register(
        agent_id="charlie_001",
        name="Charlie",
        specialization="testing",
        host="localhost",
        port=9002
    )
    
    # Create message broker
    broker = MessageBroker("charlie_001", storage_dir / "charlie" / "messages")
    
    # Handler for consensus
    def handle_consensus(message):
        question = message.payload.get('question')
        options = message.payload.get('options', [])
        print(f"\n[Charlie] Consensus request: {question}")
        
        # Vote for last option
        if options:
            vote = MessageBuilder.vote(
                from_agent="charlie_001",
                to_agent=message.from_agent,
                reply_to=message.msg_id,
                choice=options[-1],
                reasoning="I prefer the last option"
            )
            broker.send(vote)
            print(f"[Charlie] Voted for: {options[-1]}")
    
    broker.register_handler(MessageType.CONSENSUS, handle_consensus)
    
    # Process messages
    print("[Charlie] Processing messages...")
    for i in range(15):
        await broker.process_messages()
        registry.heartbeat("charlie_001", load=0.2)
        await asyncio.sleep(0.5)
    
    print("\n[Charlie] Demo complete!")


async def simulate_message_delivery(storage_dir: Path):
    """Simulate message delivery between agents."""
    await asyncio.sleep(0.5)
    
    alice_broker = MessageBroker("alice_001", storage_dir / "alice" / "messages")
    bob_broker = MessageBroker("bob_001", storage_dir / "bob" / "messages")
    charlie_broker = MessageBroker("charlie_001", storage_dir / "charlie" / "messages")
    
    # Simulate message routing
    for _ in range(20):
        # Check Alice's sent messages and deliver to recipients
        for msg_id, msg in list(alice_broker._sent.items()):
            if msg.to_agent == "bob_001":
                bob_broker.receive(msg)
            elif msg.to_agent == "*":  # Broadcast
                bob_broker.receive(msg)
                charlie_broker.receive(msg)
        
        # Check Bob's sent messages
        for msg_id, msg in list(bob_broker._sent.items()):
            if msg.to_agent == "alice_001":
                alice_broker.receive(msg)
        
        # Check Charlie's sent messages
        for msg_id, msg in list(charlie_broker._sent.items()):
            if msg.to_agent == "alice_001":
                alice_broker.receive(msg)
        
        await asyncio.sleep(0.2)


async def main():
    """Run simplified multi-agent demo."""
    storage_dir = Path("memory/multi_agent_demo")
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*60)
    print("  Simplified Multi-Agent Demo")
    print("  3 Agents: Alice, Bob, Charlie")
    print("  (No LLM required - basic messaging only)")
    print("="*60)
    
    # Shared registry
    registry = AgentRegistry(storage_dir / "registry.json")
    
    # Run all agents + message delivery concurrently
    await asyncio.gather(
        run_alice(storage_dir, registry),
        run_bob(storage_dir, registry),
        run_charlie(storage_dir, registry),
        simulate_message_delivery(storage_dir)
    )
    
    print("\n" + "="*60)
    print("  Demo Complete!")
    print("\n  Registry Stats:")
    print(f"    {registry.get_stats()}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
