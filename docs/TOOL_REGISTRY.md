# Tool Registry System

## Обзор

**Tool Registry** — это система инструментов для расширения возможностей Digital Being.

### Проблема

До этого система могла только:
```
❌ Shell команды
❌ LLM запросы
❌ Простые file operations
```

### Решение

Теперь система имеет **расширяемый реестр инструментов**:
```
✅ web_search — поиск в интернете
✅ read_url — чтение веб-страниц
✅ file_read/write — безопасная работа с файлами
✅ python_execute — выполнение Python кода
✅ json_parse — парсинг JSON
✅ + любые новые инструменты!
```

---

## Архитектура

### **BaseTool**

Базовый класс для всех инструментов:

```python
class BaseTool(ABC):
    @property
    def name(self) -> str:  # Уникальный идентификатор
    @property
    def description(self) -> str  # Описание
    @property
    def parameters(self) -> List[ToolParameter]  # Параметры
    
    async def execute(self, **kwargs) -> ToolResult:
        # Выполнение
```

**Возможности:**
- Автоматическая валидация параметров
- Type checking
- Error handling
- Статистика использования
- Cost tracking

---

### **ToolRegistry**

Реестр инструментов:

```python
registry = ToolRegistry()

# Регистрация
registry.register(WebSearchTool())

# Поиск
tools = registry.search("web")

# Выполнение
result = await registry.execute(
    "web_search",
    query="pandas documentation",
    max_results=5
)
```

**Функции:**
- `register()` / `unregister()`
- `get()` / `list_tools()`
- `search()` — поиск по категории/названию
- `execute()` — выполнение
- `get_statistics()` — статистика

---

## Встроенные инструменты

### 1. **WebSearchTool**

Поиск в интернете:

```python
result = await registry.execute(
    "web_search",
    query="pandas dataframe tutorial",
    max_results=5
)

# result.data = {
#   "query": "...",
#   "results": [
#     {"title": "...", "url": "..."},
#     ...
#   ],
#   "count": 5
# }
```

**Использует:** DuckDuckGo (no API key needed)

---

### 2. **ReadUrlTool**

Чтение содержимого страницы:

```python
result = await registry.execute(
    "read_url",
    url="https://example.com/doc",
    max_length=10000
)

# result.data = {
#   "url": "...",
#   "content": "...",  # Текст страницы
#   "length": 5234
# }
```

**Возможности:**
- HTML → text extraction
- Timeout protection
- Max length limit

---

### 3. **FileReadTool / FileWriteTool**

Безопасная работа с файлами:

```python
# Чтение
result = await registry.execute(
    "file_read",
    path="data/notes.txt",
    encoding="utf-8"
)

# Запись
result = await registry.execute(
    "file_write",
    path="data/output.txt",
    content="Hello, world!"
)
```

**Безопасность:**
- Sandboxing: только allowed_dirs
- Path validation
- Permission checks

---

### 4. **PythonExecuteTool**

Выполнение Python кода:

```python
code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
print(df.mean())
'''

result = await registry.execute(
    "python_execute",
    code=code,
    timeout=30
)

# result.data = {
#   "stdout": "a    2.0\n...",
#   "stderr": "",
#   "exit_code": 0
# }
```

**Безопасность:**
- Subprocess isolation
- Timeout protection
- Resource limits

---

### 5. **JSONParseTool**

Парсинг JSON:

```python
result = await registry.execute(
    "json_parse",
    json_string='{"key": "value"}'
)

# result.data = {
#   "parsed": {"key": "value"},
#   "type": "dict"
# }
```

---

## Интеграция

### С GoalExecutor

```python
from core.tools import ToolRegistry, initialize_default_tools
from core.tools.tool_executor import ToolAwareExecutor

# Инициализация
registry = ToolRegistry()
initialize_default_tools(registry)

# В GoalExecutor
tool_executor = ToolAwareExecutor(registry)

# В action execution:
if action.action_type in ["web_search", "read_url", ...]:
    success, result = await tool_executor.execute_tool_action(action)
```

### С GoalPlanner

GoalPlanner теперь знает о доступных инструментах:

```python
prompt = f"""
Цель: Изучить pandas

{tool_executor.get_tool_capabilities_prompt()}

Разбей на шаги с использованием доступных инструментов.
"""
```

**Результат:**
```json
{
  "subgoals": [
    {
      "description": "Найти документацию",
      "is_action": true,
      "action_type": "web_search",
      "action_params": {
        "query": "pandas official documentation",
        "max_results": 3
      }
    },
    {
      "description": "Прочитать getting started",
      "is_action": true,
      "action_type": "read_url",
      "action_params": {
        "url": "<результат web_search>"
      }
    }
  ]
}
```

---

## Создание новых инструментов

```python
from core.tools.base_tool import BaseTool, ToolCategory, ToolParameter, ToolResult

class MyCustomTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Мой кастомный инструмент"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM
    
    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="input",
                type="string",
                description="Входные данные",
                required=True
            )
        ]
    
    async def execute(self, **kwargs) -> ToolResult:
        input_data = kwargs["input"]
        # Ваша логика
        result = input_data.upper()
        
        return ToolResult(
            success=True,
            data={"result": result},
            cost=1
        )

# Регистрация
registry.register(MyCustomTool())
```

---

## Преимущества

✅ **Расширяемость** — легко добавлять новые инструменты  
✅ **Безопасность** — sandboxing, validation, permissions  
✅ **Discovery** — LLM автоматически находит нужные инструменты  
✅ **Статистика** — отслеживание использования  
✅ **Cost tracking** — учёт стоимости операций  

---

## Будущие улучшения

- [ ] **GitHubAPITool** — работа с GitHub
- [ ] **EmailTool** — отправка писем
- [ ] **DatabaseTool** — запросы к БД
- [ ] **Tool composition** — комбинация инструментов
- [ ] **Async caching** — кэширование результатов