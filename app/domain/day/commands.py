from pydantic import BaseModel

class StartDayCommand(BaseModel):
    day_id: str # идентификатор дня (2026-04-29)

class EndDayCommand(BaseModel):
    day_id: str # идентификатор дня (2026-04-29)
    first_step_tomorrow: str # первый шаг на завтра 