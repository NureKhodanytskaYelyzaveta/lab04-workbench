"""Підмінна модель для тестів: відповідає за сценарієм, без мережі і ключа."""
import json
from collections.abc import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types


class ScriptedLlm(BaseLlm):
    """script: {фрагмент системної інструкції: [відповідь1, відповідь2, ...]}.

    Агента впізнаємо за його інструкцією, тому порядок паралельних
    викликів не впливає на результат. Остання відповідь повторюється.
    """
    script: dict[str, list] = {}
    calls: list[str] = []

    async def generate_content_async(self, llm_request: LlmRequest,
                                     stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        instruction = str(llm_request.config.system_instruction or "")
        for marker, replies in self.script.items():
            if marker in instruction:
                self.calls.append(marker)
                reply = replies.pop(0) if len(replies) > 1 else replies[0]
                text = reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)
                yield LlmResponse(content=types.Content(role="model",
                                                        parts=[types.Part(text=text)]))
                return
        raise AssertionError(f"no scripted reply for instruction: {instruction[:80]}")


class ToolCallingLlm(BaseLlm):
    """Спершу викликає інструменти зі списку calls, потім відповідає текстом answer."""
    calls: list[tuple[str, dict]] = []
    answer: str = ""
    seen_tool_results: list[str] = []

    async def generate_content_async(self, llm_request: LlmRequest,
                                     stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1].parts[0] if llm_request.contents else None
        if last is not None and last.function_response:
            self.seen_tool_results.append(str(last.function_response.response))
        if self.calls:
            name, args = self.calls.pop(0)
            part = types.Part(function_call=types.FunctionCall(name=name, args=args))
        else:
            part = types.Part(text=self.answer)
        yield LlmResponse(content=types.Content(role="model", parts=[part]))
