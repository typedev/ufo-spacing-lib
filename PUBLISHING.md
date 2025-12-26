# Публикация ufo-spacing-lib

## Шаг 1: Создание нового репозитория

```bash
# Создать новую папку для библиотеки
mkdir -p ~/WORKS/PythonWorks/ufo-spacing-lib
cd ~/WORKS/PythonWorks/ufo-spacing-lib

# Инициализировать git
git init
```

## Шаг 2: Структура репозитория

Скопировать файлы и организовать структуру:

```
ufo-spacing-lib/
├── src/
│   └── ufo_spacing_lib/
│       ├── __init__.py
│       ├── contexts.py
│       ├── groups_core.py
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── kerning.py
│       │   └── margins.py
│       └── editors/
│           ├── __init__.py
│           ├── kerning.py
│           └── margins.py
├── tests/
│   ├── __init__.py
│   ├── mocks.py
│   ├── test_kerning_commands.py
│   ├── test_editors.py
│   └── test_groups_manager.py
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

### Команды для копирования:

```bash
# Из папки KernTool4
cd ~/WORKS/PythonWorks/KernTool4

# Создать структуру
mkdir -p ~/WORKS/PythonWorks/ufo-spacing-lib/src/ufo_spacing_lib
mkdir -p ~/WORKS/PythonWorks/ufo-spacing-lib/tests

# Скопировать исходники
cp -r source/ufo_spacing_lib/*.py ~/WORKS/PythonWorks/ufo-spacing-lib/src/ufo_spacing_lib/
cp -r source/ufo_spacing_lib/commands ~/WORKS/PythonWorks/ufo-spacing-lib/src/ufo_spacing_lib/
cp -r source/ufo_spacing_lib/editors ~/WORKS/PythonWorks/ufo-spacing-lib/src/ufo_spacing_lib/

# Скопировать тесты
cp source/ufo_spacing_lib/tests/*.py ~/WORKS/PythonWorks/ufo-spacing-lib/tests/

# Скопировать конфиги
cp source/ufo_spacing_lib/pyproject.toml ~/WORKS/PythonWorks/ufo-spacing-lib/
cp source/ufo_spacing_lib/README.md ~/WORKS/PythonWorks/ufo-spacing-lib/
```

## Шаг 3: Обновить импорты в тестах

После копирования тесты будут в отдельной папке, нужно исправить импорты:

```python
# Было (относительные):
from ..contexts import FontContext
from ..commands.kerning import SetKerningCommand

# Станет (абсолютные):
from ufo_spacing_lib.contexts import FontContext
from ufo_spacing_lib.commands.kerning import SetKerningCommand
```

## Шаг 4: Создать .gitignore

```bash
cat > ~/WORKS/PythonWorks/ufo-spacing-lib/.gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.nox/

# Type checking
.mypy_cache/

# Build
dist/
*.whl
EOF
```

## Шаг 5: Создать LICENSE

```bash
cat > ~/WORKS/PythonWorks/ufo-spacing-lib/LICENSE << 'EOF'
MIT License

Copyright (c) 2024 Alexander Lubovenko

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF
```

## Шаг 6: Установка инструментов сборки

### С uv (рекомендуется):

```bash
# Установить uv если ещё нет
curl -LsSf https://astral.sh/uv/install.sh | sh

# Перейти в папку проекта
cd ~/WORKS/PythonWorks/ufo-spacing-lib

# Создать виртуальное окружение
uv venv

# Активировать
source .venv/bin/activate

# Установить зависимости разработки
uv pip install -e ".[dev]"

# Запустить тесты
uv run pytest
```

### С pip:

```bash
cd ~/WORKS/PythonWorks/ufo-spacing-lib
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Шаг 7: Сборка пакета

```bash
# С uv
uv build

# Или с pip
pip install build
python -m build
```

Результат будет в папке `dist/`:
- `ufo_spacing_lib-0.1.0.tar.gz` (source distribution)
- `ufo_spacing_lib-0.1.0-py3-none-any.whl` (wheel)

## Шаг 8: Публикация на PyPI

### Тестовый PyPI (рекомендуется сначала):

```bash
# Установить twine
uv pip install twine

# Загрузить на Test PyPI
twine upload --repository testpypi dist/*

# Проверить установку
uv pip install --index-url https://test.pypi.org/simple/ ufo-spacing-lib
```

### Реальный PyPI:

```bash
# Нужен аккаунт на pypi.org и API токен
# Создать токен: https://pypi.org/manage/account/token/

# Загрузить
twine upload dist/*

# После этого можно устанавливать:
pip install ufo-spacing-lib
# или
uv pip install ufo-spacing-lib
```

## Шаг 9: GitHub Actions для автопубликации

Создать `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install uv
        uses: astral-sh/setup-uv@v4
      
      - name: Build package
        run: uv build
      
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          api-token: ${{ secrets.PYPI_API_TOKEN }}
```

## Шаг 10: Версионирование

При каждом релизе обновлять версию в `pyproject.toml`:

```toml
[project]
version = "0.1.0"  # -> "0.1.1" -> "0.2.0" -> "1.0.0"
```

Рекомендуется использовать [Semantic Versioning](https://semver.org/):
- PATCH (0.1.x): исправления багов
- MINOR (0.x.0): новые фичи, обратная совместимость
- MAJOR (x.0.0): breaking changes

---

## Шаги для обновления:

  1. Обновить версию в двух местах:

  # pyproject.toml
  version = "0.2.0"

  # src/ufo_spacing_lib/__init__.py
  __version__ = "0.2.0"

  2. Собрать пакет:

  uv build
  # или
  python -m build

  3. Загрузить на PyPI:

  # С twine (классический способ)
  twine upload dist/*

  # Или с uv (если настроено)
  uv publish

  Требования:
  - Аккаунт на pypi.org
  - API token (создать на https://pypi.org/manage/account/token/)
  - Настроить ~/.pypirc или передать token через переменную TWINE_PASSWORD



## Быстрый старт (одной командой)

```bash
# Скрипт для автоматической настройки
cd ~/WORKS/PythonWorks
mkdir -p ufo-spacing-lib/src/ufo_spacing_lib/{commands,editors}
mkdir -p ufo-spacing-lib/tests

# Копировать всё из KernTool4
cp KernTool4/source/ufo_spacing_lib/*.py ufo-spacing-lib/src/ufo_spacing_lib/
cp KernTool4/source/ufo_spacing_lib/commands/*.py ufo-spacing-lib/src/ufo_spacing_lib/commands/
cp KernTool4/source/ufo_spacing_lib/editors/*.py ufo-spacing-lib/src/ufo_spacing_lib/editors/
cp KernTool4/source/ufo_spacing_lib/tests/*.py ufo-spacing-lib/tests/
cp KernTool4/source/ufo_spacing_lib/pyproject.toml ufo-spacing-lib/
cp KernTool4/source/ufo_spacing_lib/README.md ufo-spacing-lib/

cd ufo-spacing-lib
git init
git add .
git commit -m "Initial commit: ufo-spacing-lib v0.1.0"
```

