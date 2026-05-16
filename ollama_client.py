import os
from openai import AsyncOpenAI


class OllamaClient:
    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=os.environ["OLLAMA_CLOUD_API_KEY"],
            base_url=os.environ.get("OLLAMA_BASE_URL", "https://api.ollama.ai/v1"),
        )
        self.model = os.environ.get("OLLAMA_MODEL", "deepseek-v4-pro")

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        kwargs: dict = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            return {
                "tool_calls": [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]
            }

        return {"content": choice.message.content or ""}
