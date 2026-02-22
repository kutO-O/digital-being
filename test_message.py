#!/usr/bin/env python3
"""Test agent-to-agent communication"""
import json
import time
from pathlib import Path

# Read registry
registry_path = Path("memory/multi_agent/registry.json")
with open(registry_path) as f:
    registry = json.load(f)

print("🤝 Multi-Agent System Status\n")
print(f"Total agents in registry: {len(registry)}\n")

# List all agents
for agent_id, info in registry.items():
    status_emoji = "✅" if info['status'] == 'online' else "❌"
    age_sec = int(time.time() - info['last_heartbeat'])
    print(f"{status_emoji} {info['name']} ({info['specialization']})")
    print(f"   ID: {agent_id}")
    print(f"   Port: {info['port']}")
    print(f"   Last heartbeat: {age_sec}s ago")
    
    # Check if really online (heartbeat < 60s)
    if age_sec < 60:
        print(f"   🟢 ACTIVE")
    else:
        print(f"   🔴 STALE (>60s)")
    print()

# Summary
active_agents = [a for a in registry.values() if (time.time() - a['last_heartbeat']) < 60]
print(f"\n📊 Summary:")
print(f"   Total: {len(registry)} agents")
print(f"   Active: {len(active_agents)} agents (heartbeat <60s)")
print(f"   Specializations: {set(a['specialization'] for a in registry.values())}")

# Check messages
messages_dir = Path("memory/multi_agent/messages")
if messages_dir.exists():
    message_files = list(messages_dir.glob("*.json"))
    print(f"\n📬 Messages: {len(message_files)} files")
    if message_files:
        for msg_file in message_files[:5]:  # Show first 5
            print(f"   - {msg_file.name}")
else:
    print(f"\n📬 Messages directory not found")
