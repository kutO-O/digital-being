"""
Digital Being - Telegram Bot Integration
Интеграция с Telegram для удалённого взаимодействия
"""

import asyncio
import logging
from pathlib import Path

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    print("⚠️  python-telegram-bot не установлен")
    print("Установи: pip install python-telegram-bot")
    Application = None

log = logging.getLogger("digital_being.telegram_bot")

class TelegramBot:
    """
    Telegram бот для Digital Being
    
    Возможности:
    - Отправка сообщений в inbox
    - Получение ответов из outbox
    - Проверка статуса системы
    - Управление агентами
    """
    
    def __init__(self, token: str, project_root: Path):
        self.token = token
        self.project_root = project_root
        self.inbox_path = project_root / "memory" / "inbox.txt"
        self.outbox_path = project_root / "outbox.txt"
        self.app = None
        self.authorized_users = set()  # Добавь свой Telegram ID
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/start - начало работы"""
        user_id = update.effective_user.id
        await update.message.reply_text(
            f"🤖 **Digital Being Bot**\n\n"
            f"Ваш ID: `{user_id}`\n\n"
            f"📝 **Команды:**\n"
            f"/status - Статус системы\n"
            f"/agents - Список агентов\n"
            f"/memory - Статистика памяти\n"
            f"/read - Прочитать outbox\n\n"
            f"Просто напишите сообщение - оно попадёт в inbox!",
            parse_mode="Markdown"
        )
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/status - статус системы"""
        try:
            import requests
            response = requests.get("http://127.0.0.1:8766/status", timeout=5)
            data = response.json()
            
            ollama_status = "✅" if data.get('ollama_available') else "❌"
            
            status_text = (
                f"🟢 **Система работает**\n\n"
                f"⏱ Uptime: {data.get('uptime_sec', 0)} сек\n"
                f"🔄 Ticks: {data.get('tick_count', 0)}\n"
                f"🧠 Episodes: {data.get('episode_count', 0)}\n"
                f"🎯 Mode: {data.get('mode', 'unknown')}\n"
                f"🤖 Ollama: {ollama_status}\n\n"
                f"🎯 Current goal:\n{data.get('current_goal', 'none')}"
            )
            
            if "emotions" in data:
                emotions = data["emotions"]
                dominant = emotions.get("dominant", {})
                status_text += f"\n\n🙂 Emotion: {dominant.get('name', 'none')} ({dominant.get('value', 0):.2f})"
            
            await update.message.reply_text(status_text, parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def agents(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/agents - список агентов"""
        try:
            import requests
            response = requests.get("http://127.0.0.1:8766/multi-agent", timeout=5)
            data = response.json()
            
            online = data.get("online_agents", [])
            stats = data.get("stats", {})
            
            agents_text = f"🤖 **Агенты ({len(online)} online)**\n\n"
            
            for agent in online:
                agents_text += f"• {agent.get('name', 'unknown')} ({agent.get('role', 'none')})\n"
            
            agents_text += f"\n📊 **Статистика:**\n"
            agents_text += f"Total: {stats.get('registry', {}).get('total_agents', 0)}\n"
            
            await update.message.reply_text(agents_text, parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def memory_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/memory - статистика памяти"""
        try:
            import requests
            response = requests.get("http://127.0.0.1:8766/memory", timeout=5)
            data = response.json()
            
            memory_text = (
                f"🧠 **Память**\n\n"
                f"📚 Episodes: {data.get('episode_count', 0)}\n"
                f"📦 Vectors: {data.get('vector_count', 0)}\n"
            )
            
            await update.message.reply_text(memory_text, parse_mode="Markdown")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def read_outbox(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/read - прочитать outbox"""
        try:
            if not self.outbox_path.exists():
                await update.message.reply_text("📥 Outbox пуст")
                return
            
            content = self.outbox_path.read_text(encoding="utf-8")
            
            # Последнее сообщение
            messages = content.split("\n\n--- [")
            if len(messages) > 1:
                last_msg = messages[-1]
                if "] Digital Being ---" in last_msg:
                    parts = last_msg.split("] Digital Being ---\n", 1)
                    if len(parts) == 2:
                        timestamp = parts[0].strip()
                        message = parts[1].strip()
                        await update.message.reply_text(
                            f"📤 **Последнее сообщение:**\n\n{message}\n\n⏰ {timestamp}",
                            parse_mode="Markdown"
                        )
                        return
            
            await update.message.reply_text("📥 Нет сообщений")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        text = update.message.text
        
        # Запись в inbox
        try:
            self.inbox_path.parent.mkdir(parents=True, exist_ok=True)
            with self.inbox_path.open("a", encoding="utf-8") as f:
                f.write(f"\n[Telegram] {text}\n")
            
            await update.message.reply_text(
                "✅ Сообщение добавлено в inbox!\n"
                "Ответ появится в outbox через 30-60 сек."
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    async def run(self):
        """Запустить бота"""
        if not Application:
            log.error("python-telegram-bot not installed")
            return
        
        self.app = Application.builder().token(self.token).build()
        
        # Команды
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("status", self.status))
        self.app.add_handler(CommandHandler("agents", self.agents))
        self.app.add_handler(CommandHandler("memory", self.memory_stats))
        self.app.add_handler(CommandHandler("read", self.read_outbox))
        
        # Текстовые сообщения
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        log.info("🤖 Telegram bot started")
        await self.app.run_polling()

if __name__ == "__main__":
    # Пример запуска
    TOKEN = "YOUR_BOT_TOKEN_HERE"  # Получи у @BotFather
    PROJECT_ROOT = Path(__file__).parent.parent
    
    bot = TelegramBot(TOKEN, PROJECT_ROOT)
    asyncio.run(bot.run())
