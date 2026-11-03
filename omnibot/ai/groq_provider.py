from groq import AsyncGroq

from omnibot.ai.base import ChatProvider, ChatResult
from omnibot.config import get_settings


class GroqProvider(ChatProvider):
    def __init__(self) -> None:
        key = get_settings().groq_api_key
        if not key:
            raise RuntimeError("GROQ_API_KEY is not configured")
        self.client = AsyncGroq(api_key=key)

    async def complete(self, model: str, messages: list[dict[str, str]]) -> ChatResult:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=700,
            temperature=0.7,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage
        return ChatResult(
            content=content[:3500],
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
