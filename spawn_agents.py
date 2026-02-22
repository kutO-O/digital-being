"""
Spawn Multiple Agents
Создаёт дополнительных агентов для системы
"""

import json
import time
from pathlib import Path

def spawn_agents():
    """Создать дополнительных агентов"""
    
    agents_to_create = [
        {
            "agent_id": "researcher_001",
            "name": "researcher",
            "specialization": "research",
            "host": "localhost",
            "port": 9001,
            "status": "online",
            "last_heartbeat": time.time(),
            "capabilities": ["web_search", "data_analysis", "information_gathering"],
            "load": 0.0
        },
        {
            "agent_id": "executor_001",
            "name": "executor",
            "specialization": "execution",
            "host": "localhost",
            "port": 9002,
            "status": "online",
            "last_heartbeat": time.time(),
            "capabilities": ["python_execute", "file_write", "shell_execute"],
            "load": 0.0
        },
        {
            "agent_id": "analyst_001",
            "name": "analyst",
            "specialization": "analysis",
            "host": "localhost",
            "port": 9003,
            "status": "online",
            "last_heartbeat": time.time(),
            "capabilities": ["data_analysis", "pattern_recognition", "reporting"],
            "load": 0.0
        },
        {
            "agent_id": "planner_001",
            "name": "planner",
            "specialization": "planning",
            "host": "localhost",
            "port": 9004,
            "status": "online",
            "last_heartbeat": time.time(),
            "capabilities": ["strategic_planning", "goal_setting", "task_breakdown"],
            "load": 0.0
        },
        {
            "agent_id": "tester_001",
            "name": "tester",
            "specialization": "testing",
            "host": "localhost",
            "port": 9005,
            "status": "online",
            "last_heartbeat": time.time(),
            "capabilities": ["testing", "validation", "quality_assurance"],
            "load": 0.0
        }
    ]
    
    # Загрузить реестр
    registry_path = Path("memory/multi_agent/registry.json")
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    
    if registry_path.exists():
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    else:
        registry = {}
    
    # Формат системы: {"agent_id": {...data...}}
    # НЕ массив!
    
    # Добавить новых агентов
    for agent in agents_to_create:
        agent_id = agent["agent_id"]
        
        # Проверить, не существует ли уже
        if agent_id in registry:
            print(f"⚠️  Агент {agent['name']} уже существует")
        else:
            registry[agent_id] = agent
            print(f"✅ Создан агент: {agent['name']} ({agent['specialization']})")
    
    # Сохранить
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 Всего агентов в системе: {len(registry)}")
    print("\n📊 Агенты:")
    
    specializations = {}
    for agent_id, agent_data in registry.items():
        spec = agent_data.get("specialization", "unknown")
        name = agent_data.get("name", "unknown")
        specializations[spec] = specializations.get(spec, 0) + 1
        print(f"  • {name} - {spec}")
    
    print("\n📊 Специализации:")
    for spec, count in specializations.items():
        print(f"  {spec}: {count}")

if __name__ == "__main__":
    spawn_agents()
