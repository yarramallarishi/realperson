from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChatResult:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ChatProvider(ABC):
    @abstractmethod
    async def complete(self, model: str, messages: list[dict[str, str]]) -> ChatResult:
        raise NotImplementedError
