"""
Bootstrap Knowledge Base
Быстрый старт: загрузка начальных знаний
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime

def bootstrap_concepts():
    """Загрузить начальные концепты"""
    
    concepts = [
        {
            "id": "concept_programming",
            "name": "Programming",
            "type": "skill",
            "description": "The art of writing computer code",
            "confidence": 0.8,
            "related": ["Python", "JavaScript", "algorithms"],
            "created_at": datetime.now().isoformat()
        },
        {
            "id": "concept_ai",
            "name": "Artificial Intelligence",
            "type": "domain",
            "description": "Computer systems that can perform tasks requiring human intelligence",
            "confidence": 0.9,
            "related": ["machine learning", "neural networks", "LLM"],
            "created_at": datetime.now().isoformat()
        },
        {
            "id": "concept_automation",
            "name": "Automation",
            "type": "concept",
            "description": "Using technology to perform tasks without human intervention",
            "confidence": 0.85,
            "related": ["scripting", "bots", "workflows"],
            "created_at": datetime.now().isoformat()
        },
        {
            "id": "concept_github",
            "name": "GitHub",
            "type": "tool",
            "description": "Platform for version control and collaboration",
            "confidence": 0.9,
            "related": ["git", "repositories", "commits"],
            "created_at": datetime.now().isoformat()
        },
        {
            "id": "concept_llm",
            "name": "Large Language Model",
            "type": "technology",
            "description": "AI model trained on vast amounts of text data",
            "confidence": 0.95,
            "related": ["Ollama", "GPT", "transformers"],
            "created_at": datetime.now().isoformat()
        }
    ]
    
    # Сохранить концепты
    concepts_path = Path("memory/initial_concepts.json")
    concepts_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(concepts_path, "w", encoding="utf-8") as f:
        json.dump(concepts, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Загружено {len(concepts)} концептов")
    return concepts

def bootstrap_skills():
    """Загрузить начальные навыки"""
    
    skills = [
        {
            "id": "skill_file_management",
            "name": "File Management",
            "description": "Read, write, and organize files",
            "success_rate": 0.95,
            "usage_count": 0,
            "confidence": 0.9,
            "examples": [
                "Read text file",
                "Write JSON",
                "List directory"
            ]
        },
        {
            "id": "skill_web_search",
            "name": "Web Search",
            "description": "Search the internet for information",
            "success_rate": 0.85,
            "usage_count": 0,
            "confidence": 0.8,
            "examples": [
                "DuckDuckGo search",
                "Google search",
                "Parse results"
            ]
        },
        {
            "id": "skill_code_execution",
            "name": "Code Execution",
            "description": "Execute Python code safely",
            "success_rate": 0.9,
            "usage_count": 0,
            "confidence": 0.85,
            "examples": [
                "Run calculations",
                "Data processing",
                "API calls"
            ]
        },
        {
            "id": "skill_data_analysis",
            "name": "Data Analysis",
            "description": "Analyze patterns in data",
            "success_rate": 0.8,
            "usage_count": 0,
            "confidence": 0.75,
            "examples": [
                "Find patterns",
                "Calculate statistics",
                "Visualize trends"
            ]
        }
    ]
    
    skills_path = Path("memory/initial_skills.json")
    with open(skills_path, "w", encoding="utf-8") as f:
        json.dump(skills, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Загружено {len(skills)} навыков")
    return skills

def bootstrap_episodes():
    """Добавить начальные эпизоды в память"""
    
    episodes = [
        {
            "event_type": "system.bootstrap",
            "description": "Initial knowledge base loaded",
            "timestamp": datetime.now().isoformat()
        },
        {
            "event_type": "learning.concept_formed",
            "description": "Learned about programming concepts",
            "timestamp": datetime.now().isoformat()
        },
        {
            "event_type": "learning.skill_acquired",
            "description": "Acquired file management skills",
            "timestamp": datetime.now().isoformat()
        },
        {
            "event_type": "system.goal_set",
            "description": "Ready to learn and grow",
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    # Добавить в episodic memory DB
    db_path = Path("memory/episodes.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for episode in episodes:
            cursor.execute(
                "INSERT INTO episodes (timestamp, event_type, description) VALUES (?, ?, ?)",
                (episode["timestamp"], episode["event_type"], episode["description"])
            )
        
        conn.commit()
        conn.close()
        
        print(f"✅ Добавлено {len(episodes)} эпизодов в память")
    except Exception as e:
        print(f"⚠️  Не удалось добавить эпизоды: {e}")

def bootstrap_all():
    """Загрузить все начальные знания"""
    
    print("🚀 Digital Being - Knowledge Bootstrap")
    print("=" * 50)
    print()
    
    concepts = bootstrap_concepts()
    skills = bootstrap_skills()
    bootstrap_episodes()
    
    print()
    print("🎉 Начальная база знаний загружена!")
    print()
    print("📊 Статистика:")
    print(f"  • Концепты: {len(concepts)}")
    print(f"  • Навыки: {len(skills)}")
    print(f"  • Эпизоды: 4")
    print()
    print("🔄 Система автоматически интегрирует эти знания при следующем запуске.")

if __name__ == "__main__":
    bootstrap_all()
