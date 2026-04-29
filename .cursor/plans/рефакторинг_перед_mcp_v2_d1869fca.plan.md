---
name: Рефакторинг перед MCP v2
overview: "Сформировать короткий, исполнимый план подготовки проекта к MCP: стабилизировать конфигурацию и диагностику, зафиксировать контракты tool-слоя и закрыть минимальные проверки качества."
todos:
  - id: settings-layer
    content: Внедрить settings-слой с валидацией и совместимостью через config.py
    status: pending
  - id: unified-logging
    content: Унифицировать структурное логирование и убрать print в ключевых шагах
    status: pending
  - id: tool-contracts
    content: Добавить доменные контракты ToolCallIntent/ToolExecutionResult/AgentStepState
    status: pending
  - id: quality-gates
    content: Добавить минимальные проверки качества и тесты на новые контракты/валидации
    status: pending
isProject: false
---

# Рефакторинг перед MCP v2

## Цель
Подготовить кодовую базу к следующему этапу (MCP-интеграции) через минимальный рефакторинг без изменения текущей бизнес-логики памяти.

## Границы
- Включаем: `settings`, унификацию логирования, доменные контракты tool-слоя, базовые quality-check.
- Не включаем: реализацию MCP-адаптеров, переработку архитектуры, изменение доменной логики retrieval/pipeline.

## Этапы

### 1. Единый settings-слой с валидацией
- Опорные файлы: [/home/user/Рабочий стол/Jasseya/config.py](/home/user/Рабочий стол/Jasseya/config.py), [/home/user/Рабочий стол/Jasseya/app/core/settings.py](/home/user/Рабочий стол/Jasseya/app/core/settings.py)
- Действия:
  - Вынести параметры из `config.py` в `BaseSettings`-модель.
  - Добавить валидацию диапазонов (`temperature`, `top_p`, лимиты) и положительных числовых значений (порты/таймауты).
  - Оставить совместимый прокси в `config.py`, чтобы существующие импорты не сломались.
  - Добавить `.env.example` с обязательными переменными.
- Результат: конфигурационные ошибки обнаруживаются при старте приложения.

### 2. Унификация логирования шагов пайплайна
- Опорные файлы: [/home/user/Рабочий стол/Jasseya/app/core/logging.py](/home/user/Рабочий стол/Jasseya/app/core/logging.py), [/home/user/Рабочий стол/Jasseya/app/application/memory/use_cases/run_memory_pipeline.py](/home/user/Рабочий стол/Jasseya/app/application/memory/use_cases/run_memory_pipeline.py), [/home/user/Рабочий стол/Jasseya/app/infrastructure/llm/reranker/agent.py](/home/user/Рабочий стол/Jasseya/app/infrastructure/llm/reranker/agent.py)
- Действия:
  - Зафиксировать обязательные поля лог-события: `trace_id`, `session_id`, `component`, `step`, `status`.
  - Заменить диагностические `print` на единый логгер.
  - Прописать правило маскировки/ограничения пользовательских данных в логах.
- Результат: любой запрос трассируется по `trace_id` от входа до ответа.

### 3. Контракты tool-слоя (без MCP-интеграции)
- Опорные файлы: [/home/user/Рабочий стол/Jasseya/app/domain/tools/contracts.py](/home/user/Рабочий стол/Jasseya/app/domain/tools/contracts.py), [/home/user/Рабочий стол/Jasseya/app/application/tools/types.py](/home/user/Рабочий стол/Jasseya/app/application/tools/types.py)
- Действия:
  - Ввести `ToolCallIntent`, `ToolExecutionResult`, `AgentStepState`.
  - Определить обязательные и опциональные поля, ограничения размеров и типы `args`/`metadata`.
  - Подготовить контракты так, чтобы MCP-адаптеры можно было подключить без изменения домена.
- Результат: формат вызовов инструментов фиксирован и пригоден для следующего этапа.

### 4. Минимальные quality-gates
- Опорные файлы: [/home/user/Рабочий стол/Jasseya/tests/test_memory_pipeline.py](/home/user/Рабочий стол/Jasseya/tests/test_memory_pipeline.py), [/home/user/Рабочий стол/Jasseya/tests/test_memory_retrieval.py](/home/user/Рабочий стол/Jasseya/tests/test_memory_retrieval.py), [/home/user/Рабочий стол/Jasseya/tests/test_memory_policies.py](/home/user/Рабочий стол/Jasseya/tests/test_memory_policies.py)
- Действия:
  - Добавить локальную команду единой проверки (линт + типы + тесты).
  - Написать тесты на валидацию settings.
  - Добавить тесты на обязательные поля структурных логов и новые tool-контракты.
- Результат: базовые регрессии ловятся автоматически до MCP-этапа.

## Порядок выполнения
1. Settings.
2. Logging.
3. Tool-контракты.
4. Quality-gates и тесты.

## Критерии готовности
- Приложение стартует через единый `settings`-слой, невалидные значения валятся с понятной ошибкой.
- В ключевых шагах памяти используется структурный лог с едиными полями.
- Контракты tool-слоя введены и покрыты тестами.
- Локальная команда quality-check проходит стабильно.