from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str  # текст сообщения


class DialogHistoryMessage(ChatMessage):
    index: int  # порядковый номер сообщения в диалоге
