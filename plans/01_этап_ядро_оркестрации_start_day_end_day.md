# Этап 01. Ядро оркестрации `start_day` / `end_day`

## Цель этапа

Собрать минимальный и предсказуемый контур рабочего дня: одна команда поднимает окружение и контекст, вторая команда корректно закрывает день и готовит точку входа на завтра.

## Ключевое архитектурное решение

- Логику этапа 01 **не смешиваем** с каркасом памяти (`app/application/memory/*`).
- Причина:
  - у памяти задача про извлечение/сохранение фактов;
  - у `start_day/end_day` задача про оркестрацию рабочего процесса.
- Что можно переиспользовать из memory:
  - стиль use-case (`execute`);
  - стиль логирования шагов и `report`.
- Что нельзя делать:
  - вызывать внутренние memory use-case напрямую из day use-case.

## Где создаём новые файлы

### Application (бизнес-оркестрация дня)

- `app/application/day/use_cases/start_day.py` — `StartDayUseCase`.
- `app/application/day/use_cases/end_day.py` — `EndDayUseCase`.
- `app/application/day/services/day_orchestration_service.py` — запуск шагов строго по порядку.
- `app/application/day/services/brief_builder.py` — сборка утреннего/вечернего брифа.
- `app/application/day/services/health_check_service.py` — проверки доступности зависимостей и деградация.

### Domain (чистые модели и контракты)

- `app/domain/day/commands.py` — `StartDayCommand`, `EndDayCommand`.
- `app/domain/day/results.py` — `StartDayResult`, `EndDayResult`.
- `app/domain/day/entities.py` — `MorningBrief`, `EveningSummary`, `DependencyHealth`, `StepExecutionReport`.

### Infrastructure (адаптеры внешнего мира)

- `app/infrastructure/day/environment_gateway.py` — управление IDE/браузером/музыкой.
- `app/infrastructure/day/state_repository.py` — хранение "где остановились" и "первый шаг на завтра".

### Interface (точка входа команд)

- `app/interfaces/cli/commands/day_commands.py` — обработка команд `start_day` и `end_day`.

## Контракты классов и методов (что писать в коде)

### `StartDayUseCase`

- `execute(command: StartDayCommand) -> StartDayResult`
- Делает:
  1. запускает `HealthCheckService.run()`;
  2. запускает `DayEnvironmentGateway.prepare_workspace()`;
  3. читает предыдущую точку из `DayStateRepository.load_checkpoint()`;
  4. собирает `MorningBrief` через `BriefBuilder.build_morning_brief()`;
  5. возвращает `StartDayResult`.

### `EndDayUseCase`

- `execute(command: EndDayCommand) -> EndDayResult`
- Делает:
  1. собирает факты дня через `BriefBuilder.collect_day_facts()`;
  2. строит `EveningSummary` через `BriefBuilder.build_evening_summary()`;
  3. сохраняет точку на завтра через `DayStateRepository.save_checkpoint()`;
  4. возвращает `EndDayResult`.

### `DayOrchestrationService`

- `run_steps(steps: list[Callable], fail_fast: bool) -> list[StepExecutionReport]`
- Нужен, чтобы не дублировать одинаковую логику:
  - запуск шага;
  - замер времени;
  - фиксация ошибки/успеха;
  - единый `StepExecutionReport`.

### `HealthCheckService`

- `run() -> list[DependencyHealth]`
- Проверяет:
  - LLM gateway;
  - Qdrant;
  - локальные зависимости, нужные для старта дня.
- Не валит весь процесс при частичной ошибке: возвращает статус `degraded` и причину.

### `BriefBuilder`

- `build_morning_brief(...) -> MorningBrief`
- `collect_day_facts(...) -> dict`
- `build_evening_summary(...) -> EveningSummary`
- Держит в одном месте формат вывода, чтобы `use_case` не занимался текстовой сборкой.

### `DayEnvironmentGateway`

- `prepare_workspace(...) -> list[StepExecutionReport]`
- Внутри:
  - открыть IDE;
  - открыть браузер с последними вкладками;
  - запустить фокус-трек.
- Возвращает подробный отчет по каждому шагу, а не только `True/False`.

### `DayStateRepository`

- `load_checkpoint() -> dict | None`
- `save_checkpoint(payload: dict) -> None`
- Минимальная ответственность: чтение/запись состояния дня, без доменной логики.

## Пошаговая реализация (в каком порядке писать)

### Шаг 1. Создать `domain/day` модели и команды

- Что делаем:
  - создаем `commands.py`, `results.py`, `entities.py`;
  - фиксируем минимальные поля DTO.
- Почему:
  - это контракт, на который сразу опираются все остальные слои.
- Проверка:
  - use-case можно типизировать без `dict[str, Any]`.

### Шаг 2. Создать сервисы application-слоя

- Что делаем:
  - `brief_builder.py`;
  - `health_check_service.py`;
  - `day_orchestration_service.py`.
- Почему:
  - чтобы разложить ответственность и не раздувать use-case.
- Проверка:
  - каждый сервис имеет 1-2 публичных метода и узкую роль.

### Шаг 3. Создать инфраструктурные адаптеры `infrastructure/day`

- Что делаем:
  - `environment_gateway.py`;
  - `state_repository.py`.
- Почему:
  - внешний мир должен быть изолирован от бизнес-логики.
- Проверка:
  - use-case получает зависимости через конструктор и не знает деталей OS/API.

### Шаг 4. Реализовать `StartDayUseCase`

- Что делаем:
  - последовательный pipeline с фиксированным порядком;
  - fallback при деградации зависимостей.
- Почему:
  - старт дня должен быть предсказуемым и стабильным.
- Проверка:
  - на выходе всегда есть `StartDayResult`, даже при частичных ошибках.

### Шаг 5. Реализовать `EndDayUseCase`

- Что делаем:
  - сбор итогов дня;
  - сохранение первого шага на завтра.
- Почему:
  - без зафиксированной точки входа теряется утренний фокус.
- Проверка:
  - после `end_day` доступен короткий и однозначный `EveningSummary`.

### Шаг 6. Подключить команды и smoke-проверку

- Что делаем:
  - регистрация `start_day`/`end_day` в CLI-слое;
  - ручной прогон 3 дня подряд.
- Почему:
  - этап считается готовым только при повторяемом цикле.
- Проверка:
  - каждый день старт/финиш проходит по одному и тому же контракту.

## Сценарии сбоев и fallback

- Qdrant недоступен:
  - поведение: `start_day` продолжается в режиме `degraded`;
  - результат: бриф строится из локальных данных.
- LLM timeout:
  - поведение: использовать шаблонный краткий morning brief;
  - результат: команда не прерывается.
- IDE/браузер не запускаются:
  - поведение: 1 повтор + запись причины в `StepExecutionReport`;
  - результат: пользователь получает понятное следующее действие.
- Ошибка записи итогов дня:
  - поведение: сохранить временный snapshot и вернуть предупреждение;
  - результат: контекст не теряется.

## Критерии готовности этапа (кодовый уровень)

- Есть отдельный модуль `day`, не смешанный с `memory`.
- Для `start_day` и `end_day` определены конкретные use-case и DTO.
- У каждого шага есть явный `Input -> Output` и fallback.
- Сценарий повторяем 3 дня подряд без потери "точки входа на завтра".
