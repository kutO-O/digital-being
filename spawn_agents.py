"""
Spawn Multiple Agents
Создаёт дополнительных агентов для системы
"""

import json
from pathlib import Path

def spawn_agents():
    """Создать дополнительных агентов"""
    
    agents_to_create = [
        {
            "id": "researcher_001",
            "name": "researcher",
            "specialization": "research",
            "role": "researcher",
            "capabilities": ["web_search", "data_analysis", "information_gathering"],
            "status": "online"
        },
        {
            "id": "executor_001",
            "name": "executor",
            "specialization": "execution",
            "role": "executor",
            "capabilities": ["python_execute", "file_write", "shell_execute"],
            "status": "online"
        },
        {
            "id": "analyst_001",
            "name": "analyst",
            "specialization": "analysis",
            "role": "analyst",
            "capabilities": ["data_analysis", "pattern_recognition", "reporting"],
            "status": "online"
        },
        {
            "id": "planner_001",
            "name": "planner",
            "specialization": "planning",
            "role": "planner",
            "capabilities": ["strategic_planning", "goal_setting", "task_breakdown"],
            "status": "online"
        },
        {
            "id": "tester_001",
            "name": "tester",
            "specialization": "testing",
            "role": "tester",
            "capabilities": ["testing", "validation", "quality_assurance"],
            "status": "online"
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
    
    # Убедиться, что есть ключ 'agents'
    if "agents" not in registry:
        registry["agents"] = []
    
    # Добавить новых агентов
    for agent in agents_to_create:
        # Проверить, не существует ли уже
        exists = any(a.get("id") == agent["id"] for a in registry["agents"])
        if not exists:
            registry["agents"].append(agent)
            print(f"✅ Создан агент: {agent['name']} ({agent['role']})")
        else:
            print(f"⚠️  Агент {agent['name']} уже существует")
    
    # Сохранить
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 Всего агентов в системе: {len(registry['agents'])}")
    print("\n📊 Роли:")
    roles = {}
    for agent in registry["agents"]:
        role = agent.get("role", "unknown")
        roles[role] = roles.get(role, 0) + 1
    
    for role, count in roles.items():
        print(f"  {role}: {count}")

if __name__ == "__main__":
    spawn_agents()
