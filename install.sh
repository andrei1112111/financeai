# Установщик financeai.
#
# Локально (из клона репозитория):
#   sh install.sh
#
# Удалённо, одной командой:
#   curl -fsSL https://raw.githubusercontent.com/andrei1112111/financeai/main/install.sh | sh
#
# Другой репозиторий или ветку можно задать переменными окружения:
#   FINANCEAI_REPO=https://github.com/user/repo FINANCEAI_REF=main sh install.sh
set -eu

REPO="${FINANCEAI_REPO:-https://github.com/andrei1112111/financeai}"
REF="${FINANCEAI_REF:-}"

# Если запущено внутри клона financeai и URL не задан явно — берём origin.
if [ -z "${FINANCEAI_REPO:-}" ] && [ -f pyproject.toml ] \
  && git rev-parse --git-dir >/dev/null 2>&1; then
  origin="$(git config --get remote.origin.url 2>/dev/null || true)"
  [ -n "$origin" ] && REPO="$origin"
fi

# Приводим ссылку к виду git+<url>, понятному uv.
case "$REPO" in
  git+*) : ;;
  git@*) REPO="git+ssh://$(printf '%s' "$REPO" | tr ':' '/')" ;;
  *) REPO="git+$REPO" ;;
esac
[ -n "$REF" ] && REPO="$REPO@$REF"

# Ставим uv, если его нет.
if ! command -v uv >/dev/null 2>&1; then
  echo "uv не найден — устанавливаю..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Устанавливаю financeai из $REPO ..."
uv tool install --force "$REPO"

echo
echo "Готово! Запускай:"
echo "  financeai          # чат (при первом запуске спросит ключ DeepSeek)"
echo "  financeai --help   # список команд"
echo
echo "Если команда 'financeai' не найдена, добавь в PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
