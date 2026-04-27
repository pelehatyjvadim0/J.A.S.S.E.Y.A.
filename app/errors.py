class AppError(Exception):
    """Базовый класс для всех ошибок приложения на уровне домена."""


class ConfigurationError(AppError):
    """Ошибка некорректной конфигурации приложения."""


class ExternalServiceError(AppError):
    """Ошибка при обращении к внешнему сервису."""


class EmbeddingError(ExternalServiceError):
    """Ошибка генерации или обработки эмбеддингов."""


class GatewayError(ExternalServiceError):
    """Ошибка запроса к LLM-гейту или обработки ответа."""


class VectorStoreError(ExternalServiceError):
    """Ошибка операций с векторной базой данных."""
