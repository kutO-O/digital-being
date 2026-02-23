# 🧪 Digital Being - Testing

Полное руководство по тестированию Digital Being.

---

## 📚 Содержание

- [Установка](#установка)
- [Запуск тестов](#запуск-тестов)
- [Покрытие кода](#покрытие-кода)
- [Написание тестов](#написание-тестов)
- [Структура](#структура)

---

## 📦 Установка

### **1. Установите зависимости для тестов:**

```bash
pip install pytest pytest-asyncio pytest-cov pytest-mock pyyaml
```

Или из requirements:

```bash
pip install -r requirements-dev.txt  # (если есть)
```

### **2. Проверьте установку:**

```bash
pytest --version
# pytest 8.0.0
```

---

## 🚀 Запуск тестов

### **Запустить все тесты:**

```bash
pytest
```

### **Запустить конкретный файл:**

```bash
pytest tests/test_hot_reloader.py
```

### **Запустить конкретный тест:**

```bash
pytest tests/test_hot_reloader.py::TestHotReloader::test_syntax_validation_valid
```

### **Verbose output:**

```bash
pytest -v
```

### **Показать print вывод:**

```bash
pytest -s
```

### **Остановиться на первой ошибке:**

```bash
pytest -x
```

### **Запустить только быстрые тесты:**

```bash
pytest -m "not slow"
```

### **Запустить только unit тесты:**

```bash
pytest -m unit
```

---

## 📊 Покрытие кода

### **Запустить с coverage:**

```bash
pytest --cov=core
```

### **Генерация HTML отчёта:**

```bash
pytest --cov=core --cov-report=html
```

Откройте `htmlcov/index.html` в браузере.

### **Показать непокрытые строки:**

```bash
pytest --cov=core --cov-report=term-missing
```

### **Минимальное покрытие (fail if below):**

```bash
pytest --cov=core --cov-fail-under=50
```

---

## ✍️ Написание тестов

### **Шаблон теста:**

```python
import pytest
from core.your_module import YourClass

class TestYourClass:
    """Test suite for YourClass."""
    
    @pytest.fixture
    def instance(self):
        """Create instance for testing."""
        return YourClass(param1="value1")
    
    def test_initialization(self, instance):
        """Test object initialization."""
        assert instance.param1 == "value1"
    
    def test_method_success(self, instance):
        """Test successful method execution."""
        result = instance.some_method()
        assert result == expected_value
    
    def test_method_failure(self, instance):
        """Test method handles errors."""
        with pytest.raises(ValueError):
            instance.some_method(invalid_input)
    
    @pytest.mark.asyncio
    async def test_async_method(self, instance):
        """Test async method."""
        result = await instance.async_method()
        assert result is not None
```

### **Fixtures:**

Fixtures используются для setup/teardown:

```python
@pytest.fixture
def temp_dir():
    """Create temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
    # Auto cleanup after test

@pytest.fixture
def mock_ollama():
    """Mock Ollama client."""
    mock = Mock()
    mock.is_available.return_value = True
    return mock
```

### **Mocking:**

```python
from unittest.mock import Mock, patch

def test_with_mock():
    mock_obj = Mock()
    mock_obj.method.return_value = "mocked"
    
    result = mock_obj.method()
    assert result == "mocked"
    mock_obj.method.assert_called_once()

@patch('module.function')
def test_with_patch(mock_func):
    mock_func.return_value = 42
    # Test code
```

### **Parametrize:**

```python
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    assert input * 2 == expected
```

---

## 📝 Структура

```
tests/
├── README.md                    # Этот файл
├── conftest.py                  # Общие fixtures
├── test_hot_reloader.py         # Тесты HotReloader
├── test_self_modification.py    # Тесты SelfModificationEngine
├── test_vector_memory.py        # Тесты VectorMemory
├── test_emotions.py             # Тесты Emotions
├── test_goal_generator.py       # Тесты GoalGenerator
└── ...
```

---

## 🛠️ Best Practices

### **1. Названия тестов:**

- ✅ `test_method_success` - что тестируем + ожидаемый результат
- ✅ `test_method_handles_invalid_input` - чёткое описание
- ❌ `test1`, `test_stuff` - неясно

### **2. Изоляция:**

- Каждый тест независим
- Используйте fixtures для setup
- Мокируйте внешние зависимости

### **3. Coverage:**

- Цель: **50%+** для критичных модулей
- Приоритет: core modules > utils
- Тестируйте edge cases

### **4. Документация:**

- Docstrings в каждом тесте
- Описывайте что тестируется

---

## 🔧 CI/CD Integration

### **GitHub Actions Example:**

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pip install pytest pytest-cov
      - run: pytest --cov=core --cov-fail-under=50
```

---

## 📊 Текущее покрытие

| Модуль | Coverage | Status |
|--------|----------|--------|
| `hot_reloader.py` | ~70% | ✅ Good |
| `self_modification.py` | ~65% | ✅ Good |
| `vector_memory.py` | ~40% | ⚠️ TODO |
| `emotions.py` | ~30% | ⚠️ TODO |
| `goal_generator.py` | ~20% | ❌ TODO |

**Цель:** 50%+ coverage для всех critical модулей

---

## 📞 Контакты

- **Issues:** https://github.com/kutO-O/digital-being/issues
- **Discussions:** https://github.com/kutO-O/digital-being/discussions

---

**Удачи в тестировании!** 🧪
