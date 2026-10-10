from __future__ import annotations

from collections.abc import Callable

from openai import OpenAI

from .config import BASE_URL, MODEL, REASONING_EFFORT, api_key, base_dir
from .prompts import SYSTEM_PROMPT
from .tools import TOOL_SCHEMAS, execute

ToolCallback = Callable[[str, str], None]
TextCallback = Callable[[str], None]
DeltaCallback = Callable[[str], None]
ReasoningCallback = Callable[[str], None]

SUMMARY_THRESHOLD = 40
KEEP_RECENT = 15
THINKING_ENABLED = {"thinking": {"type": "enabled"}}
THINKING_DISABLED = {"thinking": {"type": "disabled"}}


class Agent:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=api_key(), base_url=BASE_URL)
        self.history: list[dict] = []
        self.summary: str = ""

    def reset(self) -> None:
        self.history.clear()
        self.summary = ""

    def _system(self) -> str:
        parts = [SYSTEM_PROMPT]
        if self.summary:
            parts.append("# Память о прошлых обсуждениях\n" + self.summary)
        preferences = self._preferences()
        if preferences:
            parts.append(
                "# Предпочтения пользователя (соблюдай обязательно)\n" + preferences
            )
        return "\n\n".join(parts)

    def _preferences(self) -> str:
        path = base_dir() / "preferences.md"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return ""
        lines = text.splitlines()
        if lines and lines[0].strip() == "# Предпочтения":
            lines = lines[1:]
        return "\n".join(lines).strip()

    def send(
        self,
        user_text: str,
        on_tool: ToolCallback | None = None,
        on_text: TextCallback | None = None,
        on_delta: DeltaCallback | None = None,
        on_reasoning: ReasoningCallback | None = None,
    ) -> str:
        self.history.append({"role": "user", "content": user_text})
        self._maybe_summarize()

        while True:
            messages = [{"role": "system", "content": self._system()}] + self.history
            stream = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                stream=True,
                reasoning_effort=REASONING_EFFORT,
                extra_body=THINKING_ENABLED,
            )

            content_parts: list[str] = []
            reasoning_parts: list[str] = []
            calls: dict[int, dict] = {}
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    reasoning_parts.append(reasoning)
                    if on_reasoning:
                        on_reasoning(reasoning)
                if delta.content:
                    content_parts.append(delta.content)
                    if on_delta:
                        on_delta(delta.content)
                for tc in delta.tool_calls or []:
                    entry = calls.setdefault(
                        tc.index, {"id": "", "name": "", "arguments": ""}
                    )
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            entry["name"] = tc.function.name
                        if tc.function.arguments:
                            entry["arguments"] += tc.function.arguments

            text = "".join(content_parts)
            assistant: dict = {"role": "assistant", "content": text}
            reasoning_text = "".join(reasoning_parts)
            if reasoning_text:
                assistant["reasoning_content"] = reasoning_text
            if calls:
                assistant["tool_calls"] = [
                    {
                        "id": calls[i]["id"],
                        "type": "function",
                        "function": {
                            "name": calls[i]["name"],
                            "arguments": calls[i]["arguments"],
                        },
                    }
                    for i in sorted(calls)
                ]
            self.history.append(assistant)

            if not calls:
                if on_text:
                    on_text(text)
                return text

            for i in sorted(calls):
                call = calls[i]
                if on_tool:
                    on_tool(call["name"], call["arguments"])
                result = execute(call["name"], call["arguments"])
                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": result,
                    }
                )

    def _maybe_summarize(self) -> None:
        if len(self.history) <= SUMMARY_THRESHOLD:
            return
        cut = len(self.history) - KEEP_RECENT
        while cut < len(self.history) and self.history[cut].get("role") != "user":
            cut += 1
        if cut >= len(self.history) or cut == 0:
            return
        prefix = self.history[:cut]
        self.summary = (self.summary + "\n" + self._summarize(prefix)).strip()
        self.history = self.history[cut:]

    def _summarize(self, prefix: list[dict]) -> str:
        transcript_lines = []
        for msg in prefix:
            role = msg.get("role")
            content = msg.get("content") or ""
            if role == "tool":
                content = content[:500]
            transcript_lines.append(f"{role}: {content}")
            for call in msg.get("tool_calls", []) or []:
                fn = call.get("function", {})
                transcript_lines.append(
                    f"  [tool_call] {fn.get('name')}({fn.get('arguments')})"
                )
        transcript = "\n".join(transcript_lines)
        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Сожми диалог в компактный пересказ на русском. Сохрани все "
                            "финансовые факты: счета, балансы, траты, цели, условия карт, "
                            "решения и договорённости."
                        ),
                    },
                    {"role": "user", "content": transcript},
                ],
                extra_body=THINKING_DISABLED,
            )
            return response.choices[0].message.content or ""
        except Exception:
            return ""
