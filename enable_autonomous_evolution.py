"""
Enable Autonomous Self-Evolution
Включение автономной самоэволюции

⚠️  ОСТОРОЖНО: Система сможет изменять себя без вашего одобрения!
"""

import yaml
from pathlib import Path

def enable_autonomous_mode():
    """Включить автономный режим эволюции"""
    
    config_path = Path("config.yaml")
    
    if not config_path.exists():
        print("❌ config.yaml не найден")
        return
    
    # Загрузить config
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # Создать бэкап
    backup_path = Path("config.yaml.backup.autonomous")
    with open(backup_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    
    print(f"💾 Бэкап создан: {backup_path}")
    
    # Изменить режим
    if "self_evolution" not in config:
        config["self_evolution"] = {}
    
    old_mode = config["self_evolution"].get("mode", "supervised")
    config["self_evolution"]["mode"] = "autonomous"
    
    # Добавить ограничения для безопасности
    config["self_evolution"].update({
        "max_changes_per_day": 10,
        "require_tests": True,
        "backup_before_apply": True,
        "rollback_on_error": True,
        "forbidden_modules": [
            "os",
            "sys", 
            "subprocess",
            "shutil"
        ]
    })
    
    # Сохранить
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    
    print(f"\n✅ Режим изменён: {old_mode} → autonomous")
    print("\n🛡️ Ограничения безопасности:")
    print("  • Максимум 10 изменений в день")
    print("  • Требуются тесты")
    print("  • Бэкап перед применением")
    print("  • Откат при ошибке")
    print("  • Запрещены опасные модули")
    
    print("\n🔄 Перезапусти Digital Being чтобы применить изменения")
    print("\n⚠️  Для отключения: python disable_autonomous_evolution.py")

def disable_autonomous_mode():
    """Отключить автономный режим"""
    config_path = Path("config.yaml")
    
    if not config_path.exists():
        print("❌ config.yaml не найден")
        return
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    if "self_evolution" in config:
        old_mode = config["self_evolution"].get("mode", "supervised")
        config["self_evolution"]["mode"] = "supervised"
        
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)
        
        print(f"✅ Режим изменён: {old_mode} → supervised")
        print("🔄 Перезапусти Digital Being")
    else:
        print("⚠️  self_evolution не настроен в config.yaml")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--disable":
        disable_autonomous_mode()
    else:
        print("🧠 Digital Being - Autonomous Evolution")
        print("=" * 50)
        print("\n⚠️  ВНИМАНИЕ: Система сможет изменять свой код!")
        print("⚠️  Это может быть опасно!\n")
        
        confirm = input("Продолжить? (yes/no): ")
        
        if confirm.lower() in ["yes", "y", "да"]:
            enable_autonomous_mode()
        else:
            print("❌ Отменено")
