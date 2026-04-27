def present_service_error(error: Exception) -> str:
    """Формирует понятное сообщение об ошибке сервиса."""
    return f"[ошибка сервиса] {error}"


def present_shutdown_message() -> str:
    """Возвращает сообщение о штатном завершении приложения."""
    return "\nЗавершение по Ctrl+C."
