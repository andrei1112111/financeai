from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import base_dir


class ToolError(Exception):
    pass


def _resolve(rel_path: str) -> Path:
    base = base_dir()
    base.mkdir(parents=True, exist_ok=True)
    candidate = (base / rel_path).resolve()
    if candidate != base and base not in candidate.parents:
        raise ToolError(
            f"Путь '{rel_path}' выходит за пределы рабочей папки {base}. Доступ запрещён."
        )
    return candidate


def list_files(subdir: str = "") -> str:
    target = _resolve(subdir)
    if not target.exists():
        return f"Папка '{subdir or '.'}' не существует."
    if not target.is_dir():
        return f"'{subdir}' — это файл, а не папка."
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name)):
        if child.name.startswith("."):
            continue
        marker = "/" if child.is_dir() else ""
        entries.append(f"{child.name}{marker}")
    base = base_dir()
    shown = target.relative_to(base) if target != base else Path(".")
    if not entries:
        return f"{shown}/ — пусто."
    return f"{shown}/:\n" + "\n".join(entries)


def read_file(path: str) -> str:
    target = _resolve(path)
    if not target.exists():
        return f"Файл '{path}' не найден."
    if target.is_dir():
        return f"'{path}' — это папка. Используй list_files."
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"'{path}' не является текстовым файлом.")


def write_file(path: str, content: str) -> str:
    target = _resolve(path)
    if target.suffix.lower() != ".md":
        raise ToolError("Разрешено записывать только .md файлы.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    length = len(content)
    return f"Записано {length} символов в {path}."


def append_file(path: str, content: str) -> str:
    target = _resolve(path)
    if target.suffix.lower() != ".md":
        raise ToolError("Разрешено дозаписывать только .md файлы.")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if existing and not existing.endswith("\n"):
            existing += "\n"
    else:
        existing = ""
    target.write_text(existing + content, encoding="utf-8")
    return f"Дописано {len(content)} символов в {path}."


def create_dir(path: str) -> str:
    target = _resolve(path)
    target.mkdir(parents=True, exist_ok=True)
    return f"Папка {path} готова."


def search_files(query: str) -> str:
    base = base_dir()
    base.mkdir(parents=True, exist_ok=True)
    needle = query.lower()
    hits: list[str] = []
    for md in sorted(base.rglob("*.md")):
        try:
            lines = md.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        rel = md.relative_to(base)
        for i, line in enumerate(lines, 1):
            if needle in line.lower():
                hits.append(f"{rel}:{i}: {line.strip()}")
    if not hits:
        return f"По запросу '{query}' ничего не найдено."
    return "\n".join(hits)


_ACCOUNT_KNOWLEDGE_SECTION = "## Знания по счетам"


def add_account_knowledge(account: str, knowledge: str) -> str:
    account = account.strip()
    knowledge = " ".join(knowledge.split())
    if not account or not knowledge:
        raise ToolError("Нужно указать и счёт, и знание о нём.")
    target = _resolve("accounts.md")
    if target.exists():
        lines = target.read_text(encoding="utf-8").splitlines()
    else:
        lines = [
            "# Счета",
            "",
            "| Счёт | Тип | Баланс | Валюта | Лимит | Заметки |",
            "|---|---|---|---|---|---|",
            "",
            _ACCOUNT_KNOWLEDGE_SECTION,
        ]

    def is_section(line: str) -> bool:
        return line.strip() == _ACCOUNT_KNOWLEDGE_SECTION

    if not any(is_section(line) for line in lines):
        while lines and not lines[-1].strip():
            lines.pop()
        if lines:
            lines.append("")
        lines.append(_ACCOUNT_KNOWLEDGE_SECTION)

    sec_i = next(i for i, line in enumerate(lines) if is_section(line))
    header = f"### {account}"
    acc_i = next(
        (i for i in range(sec_i + 1, len(lines)) if lines[i].strip() == header),
        None,
    )

    if acc_i is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines.append("")
        lines.append(header)
        acc_i = len(lines) - 1

    insert_at = len(lines)
    for i in range(acc_i + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("### ") or stripped.startswith("## "):
            insert_at = i
            break
    lines.insert(insert_at, f"- {knowledge}")

    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return f"Добавлено знание о счёте «{account}»."


def add_preference(preference: str) -> str:
    preference = " ".join(preference.split())
    if not preference:
        raise ToolError("Пустое предпочтение.")
    target = _resolve("preferences.md")
    if target.exists():
        text = target.read_text(encoding="utf-8")
        if text and not text.endswith("\n"):
            text += "\n"
        if not text.strip():
            text = "# Предпочтения\n\n"
    else:
        text = "# Предпочтения\n\n"
    text += f"- {preference}\n"
    target.write_text(text, encoding="utf-8")
    return f"Записал предпочтение: «{preference}»."


_WEEKDAYS_RU = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]

_RELATIVE_DATES = {
    "today": 0,
    "сегодня": 0,
    "now": 0,
    "сейчас": 0,
    "tomorrow": 1,
    "завтра": 1,
    "yesterday": -1,
    "вчера": -1,
}


def _parse_date(value: str) -> date:
    raw = (value or "").strip().lower()
    if raw in _RELATIVE_DATES:
        return date.today() + timedelta(days=_RELATIVE_DATES[raw])
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d.%m"):
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if fmt == "%d.%m":
            parsed = parsed.replace(year=date.today().year)
        return parsed.date()
    raise ToolError(f"Не удалось разобрать дату {value!r}. Используй формат YYYY-MM-DD.")


def _parse_holidays(value: str) -> set[date]:
    result: set[date] = set()
    for chunk in (value or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk:
            result.add(_parse_date(chunk))
    return result


def _add_months(day: date, months: int) -> date:
    total = day.month - 1 + months
    year = day.year + total // 12
    month = total % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last))


_RU_FIXED_HOLIDAYS: tuple[tuple[int, int], ...] = (
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (1, 5),
    (1, 6),
    (1, 7),
    (1, 8),
    (2, 23),
    (3, 8),
    (5, 1),
    (5, 9),
    (6, 12),
    (11, 4),
)


def _ru_holidays(start: date, end: date) -> set[date]:
    holidays: set[date] = set()
    for year in range(start.year, end.year + 1):
        for month, day in _RU_FIXED_HOLIDAYS:
            holidays.add(date(year, month, day))
    return holidays


def _iter_workdays(start: date, end: date, holidays: set[date]) -> list[date]:
    workdays: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in holidays:
            workdays.append(cursor)
        cursor += timedelta(days=1)
    return workdays


def current_datetime() -> str:
    now = datetime.now().astimezone()
    today = now.date()
    iso = today.isocalendar()
    return (
        f"Сейчас: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        f"Дата: {today.isoformat()} ({_WEEKDAYS_RU[today.weekday()]})\n"
        f"ISO-неделя: {iso.year}-W{iso.week:02d}\n"
        f"День года: {today.timetuple().tm_yday}\n"
        f"Дней до конца месяца: {calendar.monthrange(today.year, today.month)[1] - today.day}"
    ).strip()


def date_info(date_str: str) -> str:
    day = _parse_date(date_str)
    iso = day.isocalendar()
    return (
        f"{day.isoformat()} — {_WEEKDAYS_RU[day.weekday()]}\n"
        f"ISO-неделя: {iso.year}-W{iso.week:02d}\n"
        f"День года: {day.timetuple().tm_yday}\n"
        f"Выходной: {'да' if day.weekday() >= 5 else 'нет'}"
    ).strip()


def date_add(
    date_str: str,
    days: int = 0,
    weeks: int = 0,
    months: int = 0,
    years: int = 0,
) -> str:
    day = _parse_date(date_str)
    if months or years:
        day = _add_months(day, int(months) + int(years) * 12)
    day += timedelta(days=int(days) + int(weeks) * 7)
    return f"{day.isoformat()} — {_WEEKDAYS_RU[day.weekday()]}"


def date_diff(start: str, end: str) -> str:
    a = _parse_date(start)
    b = _parse_date(end)
    days = (b - a).days
    lo, hi = min(a, b), max(a, b)
    holidays = _ru_holidays(lo, hi)
    workdays = len(_iter_workdays(lo, hi, holidays))
    return (
        f"От {a.isoformat()} до {b.isoformat()}: {days} календарных дней, "
        f"{workdays} рабочих дней (пн–пт без гос. праздников РФ, включая границы)."
    )


def workdays(start: str, end: str, holidays: str = "") -> str:
    a = _parse_date(start)
    b = _parse_date(end)
    if b < a:
        a, b = b, a
    holiday_set = _ru_holidays(a, b) | _parse_holidays(holidays)
    found = _iter_workdays(a, b, holiday_set)
    total_days = (b - a).days + 1
    weekend = sum(1 for i in range(total_days) if (a + timedelta(days=i)).weekday() >= 5)
    holidays_in_range = sum(1 for h in holiday_set if a <= h <= b and h.weekday() < 5)
    result = (
        f"Рабочих дней с {a.isoformat()} по {b.isoformat()}: {len(found)} "
        f"(из {total_days} календарных; выходных {weekend}"
    )
    if holidays_in_range:
        result += f", учтённых праздников {holidays_in_range}"
    result += ")."
    if len(found) <= 31:
        result += "\n" + ", ".join(d.isoformat() for d in found)
    return result


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Показать содержимое папки внутри рабочей директории.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subdir": {
                        "type": "string",
                        "description": "Относительный путь папки, например 'transactions' или 'cards'. Пусто = корень.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Прочитать .md файл с данными (счета, траты, профиль, условия карт).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Относительный путь файла."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Создать или полностью перезаписать .md файл. Используй для обновления таблиц и памяти агента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Относительный путь .md файла."},
                    "content": {"type": "string", "description": "Полное новое содержимое файла."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Дописать строку(и) в конец .md файла. Удобно для добавления одной транзакции.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Относительный путь .md файла."},
                    "content": {"type": "string", "description": "Текст для добавления в конец."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_dir",
            "description": "Создать папку внутри рабочей директории.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Относительный путь папки."}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Поиск подстроки по всем .md файлам базы знаний.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Что искать."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_account_knowledge",
            "description": (
                "Добавить накопленное знание/правило о конкретном счёте в accounts.md "
                "(например ставку, дату зарплаты, комиссии, особенности). Знания копятся со временем."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "account": {"type": "string", "description": "Название счёта, как в таблице accounts.md."},
                    "knowledge": {"type": "string", "description": "Одна мысль/факт о счёте."},
                },
                "required": ["account", "knowledge"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_preference",
            "description": (
                "Сохранить предпочтение пользователя о твоих ответах: стиль, тон, формат, "
                "детализацию, терминологию, единицы, порядок вывода и т.п. Вызывай, когда "
                "пользователь просит что-то запомнить или занести в предпочтения."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "preference": {
                        "type": "string",
                        "description": "Одно предпочтение, кратко, в утвердительной форме.",
                    }
                },
                "required": ["preference"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "current_datetime",
            "description": "Текущие дата и время (локальные), день недели, номер ISO-недели, день года.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "date_info",
            "description": "Сведения о дате: день недели, ISO-неделя, день года, выходной ли.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {
                        "type": "string",
                        "description": "Дата YYYY-MM-DD (или today/tomorrow/yesterday).",
                    }
                },
                "required": ["date_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "date_add",
            "description": "Прибавить/вычесть к дате дни, недели, месяцы, годы. Для сдвигов периода.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {"type": "string", "description": "Исходная дата YYYY-MM-DD или today."},
                    "days": {"type": "integer", "description": "Сдвиг в днях (может быть отрицательным)."},
                    "weeks": {"type": "integer", "description": "Сдвиг в неделях."},
                    "months": {"type": "integer", "description": "Сдвиг в месяцах."},
                    "years": {"type": "integer", "description": "Сдвиг в годах."},
                },
                "required": ["date_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "date_diff",
            "description": (
                "Разница между двумя датами: календарные и рабочие дни. Рабочие дни — строго "
                "пн–пт без гос. праздников РФ (автоматически)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "Начало YYYY-MM-DD."},
                    "end": {"type": "string", "description": "Конец YYYY-MM-DD."},
                },
                "required": ["start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "workdays",
            "description": (
                "Число рабочих дней (пн–пт) в диапазоне включительно. Гос. праздники РФ "
                "(новогодние 1–8 января, 23 февраля, 8 марта, 1 мая, 9 мая, 12 июня, 4 ноября) "
                "учитываются автоматически и в рабочие дни не входят. Параметр holidays — "
                "дополнительные нерабочие дни. Используй для расчёта зарплаты: рабочие дни × ставка."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "Начало YYYY-MM-DD."},
                    "end": {"type": "string", "description": "Конец YYYY-MM-DD."},
                    "holidays": {
                        "type": "string",
                        "description": "Дополнительные нерабочие дни через запятую, YYYY-MM-DD (необязательно).",
                    },
                },
                "required": ["start", "end"],
            },
        },
    },
]

_DISPATCH = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "append_file": append_file,
    "create_dir": create_dir,
    "search_files": search_files,
    "add_account_knowledge": add_account_knowledge,
    "add_preference": add_preference,
    "current_datetime": current_datetime,
    "date_info": date_info,
    "date_add": date_add,
    "date_diff": date_diff,
    "workdays": workdays,
}


def execute(name: str, arguments: str) -> str:
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"Неизвестный инструмент: {name}"
    try:
        kwargs = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as exc:
        return f"Некорректные аргументы инструмента {name}: {exc}"
    try:
        return fn(**kwargs)
    except ToolError as exc:
        return f"Ошибка: {exc}"
    except TypeError as exc:
        return f"Ошибка вызова {name}: {exc}"
