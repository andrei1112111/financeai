from __future__ import annotations

import json
import os
import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from .agent import Agent
from .config import base_dir, config_file, has_api_key, save_api_key
from .prompts import scaffold

console = Console()

HELP = """\
Команды:
  /help    — эта справка
  /files   — показать файлы базы знаний
  /reset   — очистить историю диалога
  /exit    — выйти (или Ctrl-D)\
"""


def _format_args(raw: str) -> str:
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return raw
    parts = []
    for key, value in data.items():
        text = str(value).replace("\n", " ⏎ ")
        if len(text) > 60:
            text = text[:57] + "…"
        parts.append(f"{key}={text!r}")
    return ", ".join(parts)


def _print_tool(name: str, args: str) -> None:
    console.print(Text(f"→ {name}({_format_args(args)})", style="dim"))


class StreamRenderer:
    def __init__(self, console: Console) -> None:
        self.console = console
        self.buffer = ""
        self.reasoning_buffer = ""
        self.shown = False
        self._live: Live | None = None
        self._mode: str | None = None
        self._last = 0.0

    def _start(self, renderable, mode: str) -> None:
        self._stop()
        self._mode = mode
        self._live = Live(
            renderable,
            console=self.console,
            refresh_per_second=20,
            vertical_overflow="visible",
        )
        self._live.start()
        self._last = time.monotonic()

    def reasoning(self, chunk: str) -> None:
        self.reasoning_buffer += chunk
        renderable = Text(self.reasoning_buffer, style="dim italic")
        if self._mode != "reasoning":
            self._start(renderable, "reasoning")
            return
        now = time.monotonic()
        if now - self._last >= 0.05:
            self._live.update(renderable)
            self._last = now

    def delta(self, chunk: str) -> None:
        self.buffer += chunk
        renderable = Markdown(self.buffer)
        if self._mode != "content":
            self._start(renderable, "content")
            self.shown = True
            return
        now = time.monotonic()
        if now - self._last >= 0.05:
            self._live.update(renderable)
            self._last = now

    def tool(self, name: str, args: str) -> None:
        self.flush()
        _print_tool(name, args)

    def _stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    def flush(self) -> None:
        if self._live is not None and self._mode == "content" and self.buffer:
            self._live.update(Markdown(self.buffer))
        self._stop()
        self.buffer = ""
        self.reasoning_buffer = ""
        self._mode = None


def _ensure_api_key() -> None:
    if has_api_key():
        return
    console.print(
        Panel.fit(
            "Ключ DeepSeek не найден. Укажем его один раз — он сохранится локально.\n"
            "Получить ключ: [link=https://platform.deepseek.com/api_keys]"
            "https://platform.deepseek.com/api_keys[/link]",
            border_style="yellow",
            title="Первый запуск",
        )
    )
    try:
        key = Prompt.ask("[bold cyan]Вставьте API-ключ DeepSeek[/]", password=True)
    except (EOFError, KeyboardInterrupt):
        console.print("\n[red]Ключ не задан — выходим.[/]")
        raise SystemExit(1)
    if not key.strip():
        console.print("[red]Пустой ключ — выходим.[/]")
        raise SystemExit(1)
    save_api_key(key)
    console.print(
        f"[green]Готово![/] Ключ сохранён в [dim]{config_file()}[/dim]\n"
    )


def _banner() -> None:
    console.print(
        Panel.fit(
            f"Финансовый ассистент (DeepSeek v3)\n[dim]папка: {base_dir()}[/dim]",
            border_style="cyan",
        )
    )
    console.print("[dim]Введите вопрос или команду. /help — справка.[/dim]\n")


@click.group(invoke_without_command=True)
@click.option(
    "--dir",
    "directory",
    type=click.Path(),
    default=None,
    help="Рабочая папка с .md-файлами (по умолчанию ~/.financeai).",
)
@click.pass_context
def cli(ctx: click.Context, directory: str | None) -> None:
    if directory:
        os.environ["FINANCE_DIR"] = str(Path(directory).expanduser().resolve())
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


@cli.command()
def chat() -> None:
    _ensure_api_key()
    scaffold()
    _banner()
    try:
        agent = Agent()
    except Exception as exc:
        console.print(f"[red]Не удалось подключиться к DeepSeek:[/] {exc}")
        raise SystemExit(1)

    while True:
        try:
            user = console.input("[bold cyan]вы ›[/] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Пока.[/dim]")
            break

        user = user.strip()
        if not user:
            continue
        if user in {"/exit", "/quit"}:
            console.print("[dim]Пока.[/dim]")
            break
        if user == "/help":
            console.print(HELP)
            continue
        if user == "/reset":
            agent.reset()
            console.print("[dim]История очищена.[/dim]")
            continue
        if user == "/files":
            from .tools import list_files

            console.print(list_files(""))
            continue

        renderer = StreamRenderer(console)
        console.print()
        try:
            answer = agent.send(
                user,
                on_tool=renderer.tool,
                on_delta=renderer.delta,
                on_reasoning=renderer.reasoning,
            )
        except Exception as exc:
            renderer.flush()
            console.print(f"[red]Ошибка:[/] {exc}")
            continue
        finally:
            renderer.flush()

        if not renderer.shown:
            console.print(Markdown(answer or "_(пустой ответ)_"))
        console.print()


@cli.command()
def init() -> None:
    scaffold()
    console.print(f"[green]Структура готова:[/] {base_dir()}")


@cli.command()
def where() -> None:
    console.print(str(base_dir()))


@cli.command()
def config() -> None:
    console.print(f"Файл конфигурации: {config_file()}")
    status = "[green]задан[/]" if has_api_key() else "[red]не задан[/]"
    console.print(f"Ключ DeepSeek: {status}")
    console.print(f"Рабочая папка: {base_dir()}")


@cli.command("set-key")
def set_key() -> None:
    try:
        key = Prompt.ask("[bold cyan]Новый API-ключ DeepSeek[/]", password=True)
    except (EOFError, KeyboardInterrupt):
        console.print("\n[red]Отменено.[/]")
        raise SystemExit(1)
    if not key.strip():
        console.print("[red]Пустой ключ — ничего не изменил.[/]")
        raise SystemExit(1)
    save_api_key(key)
    console.print(f"[green]Ключ сохранён в[/] [dim]{config_file()}[/dim]")


def main() -> None:
    cli()
