"""
Multi-Agent Communication Demo
Demonstrates 3 specialized agents working together.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.multi_agent_coordinator import MultiAgentCoordinator
from core.skill_library import SkillLibrary
from core.ollama_client import OllamaClient
from core.message_protocol import Priority


async def run_alice(storage_dir: Path, ollama: OllamaClient):
    """Alice - Research agent."""
    print("\n[Alice] Starting research agent...")
    
    # Initialize components
    skill_lib = SkillLibrary(
        memory_dir=storage_dir / "alice" / "skills",
        ollama=ollama
    )
    skill_lib.load()
    
    config = {
        "auto_register": True,
        "network": {"host": "localhost", "port": 9000}
    }
    
    coordinator = MultiAgentCoordinator(
        agent_id="alice_001",
        agent_name="Alice",
        specialization="research",
        skill_library=skill_lib,
        config=config,
        storage_dir=storage_dir / "alice"
    )
    
    # Wait for other agents to register
    await asyncio.sleep(2)
    
    # Check online agents
    agents = coordinator.get_online_agents()
    print(f"[Alice] Found {len(agents)} agents online:")
    for agent in agents:
        print(f"  - {agent.name} ({agent.specialization})")
    
    # Send query to Bob
    print("\n[Alice] Asking Bob about web frameworks...")
    answer = await coordinator.send_query_and_wait(
        to_agent="bob_001",
        question="What's the best Python web framework for REST APIs?",
        context={"requirements": ["fast", "async", "modern"]},
        timeout=10.0
    )
    print(f"[Alice] Bob's answer: {answer}")
    
    # Delegate task to Bob
    print("\n[Alice] Delegating coding task to Bob...")
    task_id = coordinator.delegate_task(
        task="Create a /health endpoint using FastAPI",
        context={
            "type": "coding",
            "framework": "FastAPI",
            "requirements": ["return status", "include timestamp"]
        },
        priority=Priority.HIGH
    )
    print(f"[Alice] Task delegated: {task_id[:8]}")
    
    # Process messages for a bit
    for _ in range(5):
        await coordinator.process_messages()
        await asyncio.sleep(1)
    
    # Request consensus
    print("\n[Alice] Requesting consensus on database choice...")
    result = await coordinator.request_consensus(
        question="Which database should we use?",
        options=["PostgreSQL", "MongoDB", "SQLite"],
        timeout=10
    )
    print(f"[Alice] Consensus reached: {result}")
    
    # Broadcast announcement
    print("\n[Alice] Broadcasting project update...")
    coordinator.broadcast(
        announcement="Project phase 1 completed!",
        data={"completed_tasks": 5, "next_phase": "testing"}
    )
    
    print("\n[Alice] Demo complete!")
    print(f"[Alice] Stats: {coordinator.get_stats()}")


async def run_bob(storage_dir: Path, ollama: OllamaClient):
    """Bob - Coding agent."""
    print("\n[Bob] Starting coding agent...")
    
    skill_lib = SkillLibrary(
        memory_dir=storage_dir / "bob" / "skills",
        ollama=ollama
    )
    skill_lib.load()
    
    # Add a coding skill
    skill_lib._skills.append({
        "id": "fastapi_endpoint",
        "name": "FastAPI endpoint creation",
        "action_type": "code",
        "description": "Create REST API endpoints using FastAPI",
        "confidence": 0.9,
        "use_count": 10,
        "success_count": 9
    })
    skill_lib._save()
    
    config = {
        "auto_register": True,
        "network": {"host": "localhost", "port": 9001}
    }
    
    coordinator = MultiAgentCoordinator(
        agent_id="bob_001",
        agent_name="Bob",
        specialization="coding",
        skill_library=skill_lib,
        config=config,
        storage_dir=storage_dir / "bob"
    )
    
    # Share skill with all agents
    print("[Bob] Sharing FastAPI skill with network...")
    coordinator.share_skill(skill_id="fastapi_endpoint", to_agent="*")
    
    # Process messages
    print("[Bob] Processing incoming messages...")
    for _ in range(20):
        count = await coordinator.process_messages()
        if count > 0:
            print(f"[Bob] Processed {count} messages")
        coordinator.send_heartbeat(current_load=0.4)
        await asyncio.sleep(1)
    
    print("\n[Bob] Demo complete!")
    print(f"[Bob] Stats: {coordinator.get_stats()}")


async def run_charlie(storage_dir: Path, ollama: OllamaClient):
    """Charlie - Testing agent."""
    print("\n[Charlie] Starting testing agent...")
    
    skill_lib = SkillLibrary(
        memory_dir=storage_dir / "charlie" / "skills",
        ollama=ollama
    )
    skill_lib.load()
    
    config = {
        "auto_register": True,
        "network": {"host": "localhost", "port": 9002}
    }
    
    coordinator = MultiAgentCoordinator(
        agent_id="charlie_001",
        agent_name="Charlie",
        specialization="testing",
        skill_library=skill_lib,
        config=config,
        storage_dir=storage_dir / "charlie"
    )
    
    # Process messages and participate in consensus
    print("[Charlie] Processing messages and voting...")
    for _ in range(20):
        await coordinator.process_messages()
        coordinator.send_heartbeat(current_load=0.2)
        await asyncio.sleep(1)
    
    print("\n[Charlie] Demo complete!")
    print(f"[Charlie] Stats: {coordinator.get_stats()}")


async def main():
    """Run multi-agent demo."""
    storage_dir = Path("memory/multi_agent_demo")
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*60)
    print("  Multi-Agent Communication Demo")
    print("  3 Specialized Agents: Alice, Bob, Charlie")
    print("="*60)
    
    # Initialize shared Ollama client
    ollama = OllamaClient(
        strategy_model="llama3.2:3b",
        embed_model="nomic-embed-text",
        host="http://127.0.0.1:11434"
    )
    
    # Check if Ollama is available
    if not ollama.is_available():
        print("\n❌ Ollama is not available. Please start Ollama service.")
        print("   Run: ollama serve")
        return
    
    print("✅ Ollama connected\n")
    
    # Run all agents concurrently
    await asyncio.gather(
        run_alice(storage_dir, ollama),
        run_bob(storage_dir, ollama),
        run_charlie(storage_dir, ollama)
    )
    
    print("\n" + "="*60)
    print("  Demo Complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
