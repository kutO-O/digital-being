"""
Autoload Agents Integration
Автоматическая интеграция агентов при старте
"""

import sys
import json
from pathlib import Path

def load_agents_to_system():
    """Загрузить агентов в систему"""
    
    registry_path = Path("memory/multi_agent/registry.json")
    
    if not registry_path.exists():
        print("⚠️  Реестр агентов не найден")
        return False
    
    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)
    
    if "agents" not in registry or not registry["agents"]:
        print("⚠️  Нет агентов для загрузки")
        return False
    
    print(f"🚀 Загружаю {len(registry['agents'])} агентов...")
    
    # Импортируем систему
    try:
        from core.agent_registry import AgentRegistry, AgentInfo
        from core.multi_agent import MultiAgentCoordinator
        
        # Достаём registry из глобального состояния
        # Это работает только AFTER инициализации main.py
        print("✅ Система готова к интеграции")
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False
    
    for agent_data in registry["agents"]:
        print(f"  • {agent_data.get('name', 'unknown')} ({agent_data.get('role', 'none')})")
    
    return True

if __name__ == "__main__":
    # Этот скрипт должен запускаться ИЗ main.py
    print("⚠️  Этот скрипт должен импортироваться, а не запускаться напрямую!")
    load_agents_to_system()
