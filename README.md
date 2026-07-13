# Ai-Code-Skill-Hub — библиотека Agent Skills

Самодостаточная, vendor-neutral библиотека пользовательских **Agent Skills**
для coding harness: OpenAI Codex, Claude Code, OpenCode, Hermes Agent и любых
других инструментов, понимающих каталоги skills с файлом `SKILL.md`.

Библиотека решает три задачи:

1. **Единый источник истины.** Все skills живут в одном репозитории, в
   каноническом каталоге `skills/`, без привязки к конкретному поставщику.
2. **Управляемая установка.** CLI `skillctl` устанавливает, обновляет,
   сравнивает и удаляет skills в целевых проектах, фиксируя происхождение
   каждой копии в lock-файле (`.agent-skills.lock.yaml`).
3. **Качество и безопасность.** Валидация структуры, metadata и content
   policy, тесты, provenance (`ORIGIN.yaml`), review наблюдений, fail-closed
   операции с файлами и CI.

## Концепция: «Git-репозиторий как skill»

Skill здесь — не одна инструкция, а **версионируемый Git-модуль**:
`skill + знания + инструменты + данные`. Люди и разные harness совместно
используют, проверяют, улучшают и синхронизируют не только текст инструкции,
но и накопленную проверенную базу знаний skill. Git даёт версии, diff, review
и историю; библиотека добавляет валидацию, контракт данных и управляемую
дистрибуцию. Поэтому отдельного каталога `history/` нет и не будет: история
изменений — это история Git (`git log -- skills/<имя>`).

### Четыре слоя каждого skill

| Слой | Где живёт | Что содержит |
|---|---|---|
| 1. Короткое описание | frontmatter `SKILL.md` (`name`, `description`) | когда и зачем применять skill; загружается первым |
| 2. Инструкции и правила | тело `SKILL.md` | компактный workflow, политики, routing-правила |
| 3. Инструменты и ресурсы | `scripts/`, `references/`, `assets/`, `agents/` | исполняемые помощники, справочники, статика, vendor-адаптеры |
| 4. Накопленные знания и данные | `knowledge/`, `data/`, `observations/` | проверенные паттерны, обезличенные fixtures/примеры, подтверждённые наблюдения |

Слои 3–4 **опциональны**: skill только с `SKILL.md` и `references/` полностью
валиден. Наличие слоёв объявляется флагами `capabilities` в `skills.yaml`.

## `skills/` в библиотеке vs `.agents/skills/` в проекте

- `skills/` (здесь, в репозитории библиотеки) — **исходники**. Их редактируют,
  версионируют и тестируют. Отсюда ничего не подключается напрямую к агентам.
- `.agents/skills/`, `.claude/skills/` и т.п. (в **целевом проекте**) —
  **установленные копии**, созданные `skillctl install`. Их не редактируют
  руками: локальные правки блокируют обновление и удаление (защита от потери
  изменений), а происхождение каждой копии записано в lock-файле проекта.

## Структура репозитория

```text
<repo-root>/
├── README.md                  # этот документ (для пользователей и разработчиков)
├── LICENSE                    # MIT
├── AGENTS.md                  # правила для разработчиков и coding harness
├── CHANGELOG.md               # история версий проекта; верхняя запись = release notes
├── pyproject.toml             # метаданные пакета; зависимостей нет (stdlib-only)
├── uv.lock                    # локфайл dev-окружения uv (coverage, mutmut)
├── .python-version            # версия CPython для uv (3.12)
├── skills.yaml                # каталог публикуемых skills (версии, capabilities, policy)
│
├── skills/                    # ЕДИНСТВЕННЫЙ источник истины опубликованных skills
│   └── example-skill/         # эталонный skill — полная модель, см. «Анатомия skill»
│
├── templates/skill/           # шаблон для `skillctl new` (НЕ публикуемый skill)
│
├── scripts/
│   ├── skillctl.py            # основной CLI (см. раздел «Команды»)
│   ├── validate_all.py        # то же, что `skillctl validate` (для CI)
│   ├── test_all.py            # то же, что `skillctl test -v` (для CI)
│   ├── bump_version.py        # ЕДИНСТВЕННЫЙ способ поднять версию проекта
│   ├── check_version_drift.py # гейт: pyproject = __init__.py = CHANGELOG
│   ├── check_release_gate.py  # гейт: изменение кода ⇔ поднятие версии
│   ├── check_mutation_score.py# гейт: mutation score не ниже порога
│   └── run_skill_evals.py     # валидация и запуск eval-manifests (offline/opt-in)
│
├── src/skill_library/         # реализация CLI (Python ≥ 3.12, только stdlib)
│   ├── cli.py                 # разбор аргументов и команды
│   ├── discovery.py           # поиск skills, чтение frontmatter и каталога
│   ├── validator.py           # структура, metadata, ссылки, слои, secret-scan, лимиты
│   ├── observations.py        # жизненный цикл наблюдений: add / approve / reject
│   ├── installer.py           # install (runtime/full) / diff / update / remove / status
│   ├── lockfile.py            # чтение/запись .agent-skills.lock.yaml
│   ├── security.py            # имена, пути, защита от traversal и symlink escape
│   ├── models.py              # типизированные модели каталога и skills
│   └── yamlio.py              # безопасный парсер/генератор подмножества YAML
│
├── __test__/                  # ЕДИНСТВЕННЫЙ каталог тестов (unittest, без сети)
│   ├── README.md              # руководство по тестированию skills (виды, гейты, критерии)
│   ├── fixtures/valid-skill/  # позитивный fixture
│   ├── fixtures/invalid-skill/# негативный fixture (нарочно сломан)
│   ├── evals/<skill>/         # versioned eval-manifests (cases.json, schema v1)
│   ├── network_blocker/       # Python-level запрет сети для subprocess-тестов
│   ├── scenarios/README.md    # ручные E2E-сценарии
│   ├── skills/                # тесты отдельных skills (test_<имя_через_подчёркивание>.py)
│   └── test_*.py              # тесты библиотеки (валидация, слои, installer, CLI…)
│
└── .github/workflows/
    ├── ci.yml                 # валидация + тесты с coverage-гейтом + smoke обоих режимов
    ├── release.yml            # гейты версии и авторелиз из main (см. ниже)
    └── mutation.yml           # weekly/manual mutation testing критичных модулей
```

## Анатомия skill (полная модель)

```text
skills/<имя>/
├── SKILL.md                   # ОБЯЗАТЕЛЬНЫЙ: frontmatter (name, description) + workflow + routing
├── ORIGIN.yaml                # ОБЯЗАТЕЛЬНЫЙ: происхождение (original/vendored, лицензия, upstream)
│
├── agents/                    # vendor-адаптеры; канонический SKILL.md остаётся нейтральным
│   └── openai.yaml            #   метаданные интерфейса для OpenAI harness (Codex)
├── references/                # справочные материалы; агент читает по ссылкам из SKILL.md
├── scripts/                   # детерминированные offline-помощники, запускаемые агентом
├── assets/                    # статические файлы (шаблоны, образцы)
│
├── knowledge/                 # ПРОВЕРЕННЫЕ обобщаемые знания (не дублируют workflow)
│   ├── INDEX.md               #   обязательный при наличии слоя: список файлов + когда читать
│   ├── patterns.md            #   устойчивые паттерны с областью применимости и evidence
│   └── pitfalls.md            #   известные ошибки/ограничения и способы диагностики
│
├── data/                      # воспроизводимые ОБЕЗЛИЧЕННЫЕ данные skill
│   ├── README.md              #   обязательный при наличии слоя: контракт набора данных
│   ├── fixtures/              #   test-only входы; НЕ устанавливаются в runtime-режиме
│   └── examples/              #   минимальные пары вход/выход; устанавливаются всегда
│
└── observations/              # ПОДТВЕРЖДЁННЫЕ наблюдения из реального применения
    ├── INDEX.md               #   обязательный при наличии слоя: правила чтения + список
    ├── candidates/            #   новые наблюдения до review; НЕ устанавливаются в runtime
    ├── accepted/              #   прошедшие review, с evidence и метаданными аудита
    └── rejected/              #   отклонённые (audit trail); НЕ устанавливаются в runtime
```

Правила:

- имя папки = `name` во frontmatter: строчные латинские буквы, цифры, дефисы
  (≤ 64 символов); рекомендуемый стиль — короткая глагольная фраза;
- внутри skill запрещены `README.md`, `CHANGELOG.md` и прочие вспомогательные
  документы; единственное исключение — `data/README.md` (контракт данных);
- разрешены только перечисленные каталоги — неизвестная папка (в т.ч.
  `history/`) не пройдёт валидацию;
- пустые слои не создаются «для галочки»: слой существует, только когда в нём
  есть содержимое, и тогда его `INDEX.md`/`README.md` обязателен;
- исполняемые файлы допустимы только в `scripts/`; symlink'и запрещены везде.

### Чем слои отличаются друг от друга

| Каталог | Отвечает на вопрос | Пример |
|---|---|---|
| `references/` | «как правильно делать» — справочник, чеклист | таблица типов Conventional Commits |
| `knowledge/` | «что мы уже проверили и обобщили» | «fix с преобладанием удалений классифицируется скриптом как refactor — переопределяй тип» |
| `data/` | «на чём это воспроизвести» | синтетический diff + ожидаемый вывод скрипта |
| `observations/` | «что наблюдалось в реальном применении» | конкретный сбой с evidence, датой и рецензентом |
| `assets/` | «какие статические файлы нужны skill» | шаблон отчёта |
| Git history | «как skill менялся во времени» | `git log -- skills/example-skill` |

Наблюдение — это **свидетельство, а не правило**. Правилом оно становится
только после promotion в `knowledge/` или в workflow `SKILL.md` отдельным
review-изменением.

## Progressive disclosure — правила загрузки контекста

Трёхуровневая загрузка, экономящая контекст агента:

1. **Metadata** — `name` + `description`; единственное, что агент видит до
   срабатывания skill. `description` обязана объяснять и назначение, и точные
   условия применения.
2. **Тело `SKILL.md`** — загружается при срабатывании; короткое, императивное,
   с routing-таблицей «какой файл открывать при каком типе задачи».
3. **Глубокие слои** — `references/`, `knowledge/`, `data/`, `observations/`,
   `scripts/`, `assets/` читаются **только по явной необходимости**, по
   ссылкам/триггерам из `SKILL.md`.

Правила маршрутизации (см. живой пример в `skills/example-skill/SKILL.md`):

- проверенные обобщения → `knowledge/` (начиная с `knowledge/INDEX.md`);
- воспроизводимые проверки → `data/` (контракт в `data/README.md`);
- диагностика известных edge cases и улучшение skill →
  `observations/accepted/` (и только он);
- агент никогда не читает «весь корпус» заранее и не принимает observation за
  норму без promotion.

## Требования и быстрый старт

Пакетный менеджер проекта — **[uv](https://docs.astral.sh/uv/)**: в репозитории
закоммичены `uv.lock` и `.python-version` (CPython 3.12). `uv sync` создаёт
`.venv` с editable-установкой проекта, после чего доступна консольная команда
`skillctl`; правки кода подхватываются без повторной синхронизации.

```bash
git clone https://github.com/volkovpv/Ai-Code-Skill-Hub.git && cd Ai-Code-Skill-Hub
uv sync                                  # однократная настройка окружения
uv run skillctl list                     # что есть в библиотеке
uv run skillctl validate                 # библиотека консистентна?
uv run skillctl test                     # весь набор тестов
uv run skillctl install example-skill --target /путь/к/проекту
```

Runtime-зависимостей у библиотеки нет — ни для CLI, ни для тестов: uv управляет
окружением, а не зависимостями, и добавлять пакеты в `dependencies` нельзя.
Поэтому работает и **fallback без uv**: `python scripts/skillctl.py <команда>`
эквивалентен `uv run skillctl <команда>` на любом Python 3.12+ без venv —
именно так библиотеку гоняет CI, доказывая самодостаточность. Примеры команд
ниже используют форму `python scripts/skillctl.py …`; всюду допустима замена
на `uv run skillctl …`.

## Команды CLI

Все команды возвращают ненулевой exit code при ошибке. `--library-root`
определяется автоматически; указывать его нужно только при запуске копии
библиотеки из другого места.

### Каталог и валидация

```bash
python scripts/skillctl.py list                    # имя, версия, статус, описание
python scripts/skillctl.py validate                # вся библиотека
python scripts/skillctl.py validate example-skill  # один skill
python scripts/skillctl.py data validate example-skill   # только контракт data/
python scripts/skillctl.py knowledge list example-skill   # файлы knowledge с заголовками
```

### Установка в проект: два режима распространения

- **`--mode runtime`** (по умолчанию) — то, что нужно агенту в работе:
  `SKILL.md`, `agents/`, `references/`, `scripts/`, `assets/`, `knowledge/`,
  `data/` (без `fixtures/`) и `observations/accepted/` + `INDEX.md`.
  **Не** устанавливаются: `data/fixtures/` (test-only),
  `observations/candidates/` и `observations/rejected/`.
- **`--mode full`** — полный модуль skill для разработки и тестирования,
  включая candidates и fixtures. `--link` всегда означает full (symlink
  открывает весь исходный каталог).

```bash
# Codex / OpenCode / универсально → <проект>/.agents/skills/<имя>
python scripts/skillctl.py install example-skill --target ~/work/my-project --agent universal --copy
python scripts/skillctl.py install example-skill --target ~/work/my-project --agent codex

# Claude Code → <проект>/.claude/skills/<имя>
python scripts/skillctl.py install example-skill --target ~/work/my-project --agent claude

# Hermes: каталог skills задаётся явно (конфигурация Hermes может жить вне проекта)
python scripts/skillctl.py install example-skill --target ~/work/my-project \
  --agent hermes --target-skills-dir ~/.hermes/skills

# полный модуль для разработки skill
python scripts/skillctl.py install example-skill --target ~/work/skill-dev --mode full
```

Полезные флаги: `--copy` (по умолчанию) / `--link`, `--dry-run`, `--force`
(явная перезапись чужих/изменённых файлов; также нужен для смены режима
runtime↔full). Повторная установка того же содержимого идемпотентна.

### Статус, diff, обновление, удаление

```bash
python scripts/skillctl.py status --target ~/work/my-project
# example-skill  v0.2.0  state=ok  update=available (0.2.0 -> 0.3.0)  mode=runtime ...

python scripts/skillctl.py diff example-skill --target ~/work/my-project   # unified diff
python scripts/skillctl.py update example-skill --target ~/work/my-project # сначала печатает diff
python scripts/skillctl.py remove example-skill --target ~/work/my-project
```

Diff/update/status сравнивают **набор файлов записанного режима установки**:
изменение candidate-наблюдения в библиотеке не покажет «update available» для
runtime-установки, а изменение `knowledge/` или accepted observation —
покажет. Правила безопасности (fail-closed):

- `update` и `remove` **отказываются** трогать локально изменённую копию —
  включая изменённые файлы `knowledge/` и `data/`; сначала `diff`, затем
  `--force`;
- `remove` удаляет **только** файлы, перечисленные в lock-записи;
- все пути нормализуются: `../`, абсолютные пути и symlink escape отвергаются.

### Наблюдения: candidate → review → accepted/rejected

```bash
# 1. записать наблюдение (ВСЕГДА создаётся candidate; accepted напрямую недостижим)
python scripts/skillctl.py observation add example-skill --from note.md \
  --evidence "data/fixtures/mixed_change.diff" --scope "example-skill/linux"

# 2. посмотреть очередь
python scripts/skillctl.py observation list example-skill --status candidate

# 3. явный review (метаданные аудита сохраняются в файле наблюдения)
python scripts/skillctl.py observation approve example-skill OBS-20260712-003 --reviewed-by volkovpv
python scripts/skillctl.py observation reject  example-skill OBS-20260712-004 \
  --reviewed-by volkovpv --note "не воспроизводится"
```

Правила жизненного цикла:

- `approve` невозможен без непустого `evidence` — сначала добавьте в
  candidate-файл воспроизводимое свидетельство (тест, fixture, commit);
- `approve`/`reject` записывают `reviewed_by`/`reviewed_at` (+ `review_note`);
- candidate/rejected не попадают в runtime-установки;
- наблюдения не изменяют `SKILL.md` автоматически; promotion
  observation → knowledge — отдельное review-изменение;
- субъективное впечатление без evidence не становится знанием.

`add`, `approve`, `reject` поддерживают `--dry-run`.

### Тесты

```bash
python scripts/skillctl.py test                 # вся библиотека (весь __test__/)
python scripts/skillctl.py test example-skill   # валидация + тесты одного skill
python scripts/skillctl.py test -v              # подробный вывод
```

## Lock-файл `.agent-skills.lock.yaml`

Создаётся в корне **целевого проекта** при первой установке. Для каждого
установленного skill фиксируются:

| Поле | Смысл |
|---|---|
| `source` | путь/URL библиотеки, из которой установлен skill |
| `source_commit` | git-commit библиотеки на момент установки (или `null`) |
| `skill_version` | версия из `skills.yaml` |
| `agent`, `mode` | harness и способ установки (`copy`/`link`) |
| `install_mode` | режим распространения: `runtime` или `full` |
| `target_path` | куда установлено (относительно проекта или абсолютно) |
| `checksum` | агрегированный sha256 файлов установленного режима |
| `installed_at`, `updated_at` | время операций (UTC, ISO 8601) |
| `files[]` | каждый управляемый файл со своим sha256 |

По `files[]` CLI отличает свои файлы от чужих (безопасное удаление) и
обнаруживает локальные правки. Checksum учитывает **все установленные слои**,
включая knowledge, data и accepted observations. Lock-файлы, созданные до
появления режимов, читаются без миграции: отсутствующий `install_mode`
трактуется как `full`. Lock стоит коммитить в репозиторий целевого проекта.

## Как создать новый skill

```bash
# минимальный skill (без опциональных слоёв)
python scripts/skillctl.py new my-new-skill

# сразу со слоями знаний/данных/наблюдений
python scripts/skillctl.py new my-new-skill --with knowledge,data,observations

$EDITOR skills/my-new-skill/SKILL.md
python scripts/skillctl.py validate my-new-skill
python scripts/skillctl.py test my-new-skill
```

`new` копирует `templates/skill/`, подставляет имя, регистрирует skill в
`skills.yaml` (status `draft`) и — при `--with` — добавляет флаги
`capabilities` и блок `content_policy`.

## Manifest: capabilities и content policy

Запись skill в `skills.yaml` может (для skills со слоями — должна) объявлять:

```yaml
  - name: example-skill
    path: skills/example-skill
    version: 0.2.0
    status: stable
    summary: Reference skill; drafts a Conventional Commits message from a git diff.
    platforms: [universal, codex, opencode, claude, hermes]
    license: MIT
    capabilities:             # какие опциональные слои есть у skill
      knowledge: true
      data: true
      observations: true
    content_policy:           # политика содержимого (валидируется)
      max_tracked_file_bytes: 262144
      pii_allowed: false      # обязано оставаться false
      secrets_allowed: false  # обязано оставаться false
      observation_review_required: true   # обязано оставаться true
```

Validator проверяет согласованность флагов с фактическими каталогами; старые
записи без этих блоков остаются валидными (слои проверяются структурно по
факту наличия).

## Какие данные можно и нельзя хранить

**Разрешено** (в `data/` при наличии `data/README.md`): синтетические
fixtures; минимальные примеры входов/выходов; эталонные структуры;
синтетические тестовые проекты; небольшие проверенные артефакты.

**Запрещено** (валидация блокирует то, что умеет обнаружить):

- секреты, токены, credentials, приватные ключи — эвристический secret-scan
  fail-closed блокирует публикацию до ручного review; тестовые маркеры должны
  быть очевидно фейковыми (например, `AKIAIOSFODNN7EXAMPLE`);
- персональные и клиентские данные (PII) — `pii_allowed` всегда `false`;
- полные production-логи;
- приватный исходный код без явного разрешения;
- бинарные/большие артефакты без обоснования: файл больше
  `max_tracked_file_bytes` (по умолчанию 256 КиБ, жёсткий потолок 5 МиБ) не
  пройдёт валидацию;
- данные, лицензия которых не позволяет распространение.

**Стратегия для больших данных**: сгенерируйте их скриптом из `scripts/`
(предпочтительно), либо храните во внешнем versioned storage и задокументируйте
источник в `data/README.md`. Git LFS — допустимая, но **необязательная**
стратегия: библиотека не делает его зависимостью; если используете LFS,
поднимите `max_tracked_file_bytes` осознанно и зафиксируйте это в review.

Secret-scan — эвристика, а не гарантия. Его молчание не отменяет ручную
проверку данных перед коммитом; его срабатывание — стоп-сигнал до review.

## Обновление skill с новыми знаниями и данными

1. В библиотеке: измените `knowledge/`/`data/`/наблюдения, прогоните
   `validate` и `test`, повысьте `version` в `skills.yaml` (SemVer: major —
   изменился смысл/контракт, minor — новые материалы и возможности, patch —
   правки текста).
2. В целевом проекте: `skillctl status` покажет `update=available`,
   `skillctl diff` — точные изменения (включая knowledge/data/accepted
   observations), `skillctl update` напечатает diff и применит их, обновив
   checksum и `files[]` в lock.

## Импорт стороннего skill, знаний и данных (vendoring)

Runtime-зависимости от чужих репозиториев нет: стороннее содержимое
**вендорится** — копируется в `skills/` с сохранением происхождения и лицензии.

1. Скопируйте каталог skill в `skills/<имя>/` (имя — по правилам библиотеки).
2. Заполните `ORIGIN.yaml`:

   ```yaml
   type: vendored
   source: https://github.com/vendor/repo
   source_commit: 1a2b3c4d…            # commit, с которого сделана копия
   license: Apache-2.0                 # исходная лицензия
   imported_at: 2026-07-12
   update_policy: follow-upstream      # manual | follow-upstream | frozen
   changes:
     - adapted paths to this library layout
   ```

3. Для сторонних **данных** дополнительно укажите в `data/README.md` источник,
   лицензию и способ обезличивания; для сторонних **знаний** сохраните ссылки
   на первоисточники в самих knowledge-файлах.
4. Добавьте запись в `skills.yaml` и прогоните `validate` + `test`.

**Политика обновления vendored содержимого**: обновление — осознанный повтор
импорта (новый upstream-commit → ручной просмотр diff → обновление
`source_commit`, `imported_at`, `changes` → повышение версии).
`frozen` — не обновлять; `manual` — по необходимости; `follow-upstream` —
регулярно. Автоматической синхронизации нет намеренно: каждый импорт проходит
review.

## Security и privacy checklist перед публикацией

Skills — **доверенный исполняемый контент**: инструкции исполняет агент с
вашими правами, `scripts/` — реальный код. Перед `git push` / review:

- [ ] `skillctl validate` — зелёный (включая secret-scan и лимиты размера);
- [ ] `skillctl test` — зелёный;
- [ ] в `data/` нет PII, клиентских данных, production-логов; `data/README.md`
      честно описывает источник и лицензию;
- [ ] все accepted observations имеют evidence и рецензента;
- [ ] в diff нет случайных локальных путей, имён клиентов, внутренних URL;
- [ ] для vendored содержимого `ORIGIN.yaml` актуален (source, commit, license);
- [ ] версия в `skills.yaml` повышена, capabilities соответствуют каталогам.

Перед **установкой/обновлением** чужого skill: просмотрите `skillctl diff`,
проверьте `ORIGIN.yaml` и не устанавливайте skills из источников, которым не
доверяете. CLI ничего не скачивает из сети — источником служит локальная
копия библиотеки, lock делает состав проверяемым.

## Как писать и запускать тесты

Подробные требования к unit, fixture/golden, integration, security,
поведенческим eval, E2E и mutation-тестам, критериям успеха и coverage описаны
в [руководстве по тестированию skills](__test__/README.md).

- Framework — `unittest` из стандартной библиотеки; каталог — только
  `__test__/` в корне.
- Тесты не ходят в сеть, не используют секреты и создают временные каталоги с
  автоматической очисткой (см. базовый класс в `__test__/helpers.py`).
- Скрипты skills запускаются в тестах только против fixtures/временных
  каталогов и с очищенным окружением (см. `test_security.py`).
- Тесты одного skill — файл `__test__/skills/test_<имя>.py`; используйте
  `data/fixtures/` собственного skill как входы — тогда тесты одновременно
  служат evidence для наблюдений (см. `test_example_skill.py`).
- Автоматические гейты качества: CI считает line+branch coverage
  (`fail_under = 80`, см. `pyproject.toml`), а `mutation.yml` еженедельно/вручную
  гоняет `mutmut` по критичным модулям с порогом score
  (`scripts/check_mutation_score.py`). Оба инструмента — dev-группа uv и на
  runtime-самодостаточность библиотеки не влияют.

```bash
python scripts/skillctl.py test                          # всё
python -m unittest discover -s __test__ -t . -v         # эквивалент напрямую
python -m unittest __test__.test_layers -v              # один модуль
uv run coverage run -m unittest discover -s __test__ -t . && uv run coverage report
```

## Процесс разработки

1. **Ветка**: `git checkout -b feat/my-new-skill`.
2. **Изменение**: skill/слои; наблюдения — только через `observation add` →
   `approve`; при изменении содержимого повысьте `version` в `skills.yaml`.
3. **Validation**: `python scripts/skillctl.py validate` — без ошибок.
4. **Tests**: `python scripts/skillctl.py test` — зелёные; новое поведение
   покрыто тестами.
5. **Review**: pull request; CI гоняет те же команды на Python 3.12 и 3.13
   плюс smoke обоих режимов установки.
6. **Release**: merge в `main`; потребители обновляются через
   `skillctl status` → `diff` → `update`.

## Совместимость и версионирование

- Версии skills — SemVer в `skills.yaml`; `status`: `draft` (не для
  установки), `stable`, `deprecated`.
- Формат lock-файла версионируется полем `version` (сейчас `1`); новые поля
  (`install_mode`) аддитивны — старые lock-файлы читаются без миграции.
- Канонический контракт skill минимален (папка + `SKILL.md` с `name` и
  `description`), поэтому skills совместимы с любым harness, поддерживающим
  Agent Skills; vendor-специфика изолирована в `agents/*` и target-путях
  установщика. Слои `knowledge/`/`data/`/`observations/` — обычные файлы и
  не требуют поддержки harness.
- Skills без опциональных слоёв полностью валидны — обратная совместимость
  закреплена тестами.

## Версия проекта и авторелизы на GitHub

Версия проекта (не путать с версиями отдельных skills в `skills.yaml`) имеет
единственный источник — `pyproject.toml`. С ним обязаны совпадать
`__version__` в `src/skill_library/__init__.py` и первая запись
`## [X.Y.Z]` в `CHANGELOG.md`; любой дрейф роняет CI
(`scripts/check_version_drift.py`).

Релизы публикует workflow `.github/workflows/release.yml` автоматически:

- **только из `main`** (прямой коммит или мерж PR); ветки `test` и `dev`
  релизов не дают — там работает только обычный CI (`ci.yml`);
- релиз привязан к поднятию версии и идемпотентен: если релиз `v<версия>` уже
  существует, публикация молча пропускается;
- ассеты релиза — архив исходников (`git archive`) и его SHA256; бинарная
  сборка не производится, GitHub дополнительно прикладывает свой
  «Source code» архив;
- заметки релиза берутся из секции текущей версии в `CHANGELOG.md`, в конец
  дописывается commit SHA и команда проверки целостности архива.

Поднятие версии — **только** скриптом, руками файлы-носители версии не правим
(это двойная работа и риск дрейфа; правило одинаково для разработчика и
агента):

```bash
python3 scripts/bump_version.py 0.0.1     # явная версия
python3 scripts/bump_version.py --patch   # 0.0.0 -> 0.0.1 (есть --minor, --major)
```

Скрипт атомарно проставит версию в `pyproject.toml`, `__init__.py` и `uv.lock`
(версию пакета проекта; сам `uv` при этом не вызывается — иначе при запуске
через `uv run` lock отставал бы на шаг), вставит заготовку записи в
`CHANGELOG.md`, после чего сам проверит отсутствие дрейфа.
Единственный ручной шаг — заменить строку `TODO` в новой записи CHANGELOG
описанием изменений: этот текст станет release notes на GitHub.

Какую цифру версии поднимать (SemVer проекта):

- **major** (первая цифра) — в библиотеке создан новый skill или удалён
  существующий;
- **minor** (средняя цифра) — изменены правила существующего skill
  (`SKILL.md`, слои, запись в каталоге);
- **patch** (последняя цифра) — исправление ошибки, не меняющее
  функциональность, либо изменение инфраструктуры пакета (`src/`,
  `scripts/`, `templates/`), никак не влияющее на функционал skills.

Правило выбирает цифру только там, где гейт вообще требует поднятия версии:
чисто инфраструктурные пути (`__test__/`, `.github/`, документация) версию
по-прежнему не меняют.

Дисциплина версии (гейт `scripts/check_release_gate.py`, работает на PR в
`main` и на push в `main`):

- изменился **используемый код** (`skills/`, `src/`, `scripts/`,
  `templates/`, `skills.yaml`, `pyproject.toml`, `LICENSE`) → версия обязана
  быть поднята (через `scripts/bump_version.py`) + описание в `CHANGELOG.md`;
- изменилась **только инфраструктура** (`__test__/`, `.github/`, `README.md`,
  `AGENTS.md` и т.п.) → версия не меняется и релиз не собирается;
- версия растёт монотонно; `0.0.0` — базовая линия «релизов ещё не было» и
  никогда не публикуется.

## Типичные ошибки и диагностика

| Симптом | Причина и решение |
|---|---|
| `frontmatter 'name' … does not match directory name` | Переименуйте папку или поле `name` — они обязаны совпадать. |
| `skills.yaml: skill '…' is not listed in the catalog` | Добавьте запись в `skills.yaml` (или удалите осиротевшую папку). |
| `installed copy has local modifications` | Кто-то правил установленную копию. `skillctl diff` → перенесите нужное в библиотеку → `update --force`. |
| `installed in 'runtime' mode; re-run with --force to switch` | Смена режима установки — осознанное действие; повторите с `--force`. |
| `knowledge/ has content but no knowledge/INDEX.md` | Создайте `INDEX.md` со списком файлов и условиями чтения. |
| `data/ has content but no data/README.md` | Опишите контракт данных (назначение, источник, лицензия, PII, лимиты). |
| `possible … detected; secrets are forbidden` | Secret-scan сработал. Уберите значение или замените очевидно фейковым маркером; молча игнорировать нельзя. |
| `… exceeds max_tracked_file_bytes` | Файл больше лимита. Генерация скриптом, внешнее хранилище или осознанное повышение политики. |
| `accepted observation must list non-empty 'evidence'` | Добавьте воспроизводимое свидетельство в candidate до approve. |
| `cannot approve without evidence` | То же на этапе CLI: сначала evidence, потом approve. |
| `unknown directory 'history/'` | Историю хранит Git; переложите материал в knowledge/observations. |
| `agent 'hermes' has no default skills directory` | Для Hermes всегда передавайте `--target-skills-dir`. |
| `path … escapes base directory` | Skill или lock содержит небезопасный путь — это защита; проверьте источник. |
| Тесты не находятся | Каталог называется строго `__test__`, файлы — `test_*.py`; запускайте из корня библиотеки. |

Диагностика в целом: `skillctl validate` (структура и политика),
`skillctl status --target …` (состояние установок), `skillctl diff` (что
изменилось), `skillctl observation list` (очередь наблюдений), содержимое
`.agent-skills.lock.yaml` (что и откуда установлено).

## Почему собственный мини-парсер YAML

Чтобы библиотека оставалась самодостаточной (нулевые зависимости), вместо
PyYAML используется `src/skill_library/yamlio.py` — парсер **узкого
подмножества** YAML: вложенные mappings (отступ 2 пробела), списки, скаляры,
кавычки, комментарии, flow-списки скаляров. Anchors/aliases/tags/многострочные
строки не поддерживаются и отвергаются с ошибкой; десериализация никогда не
создаёт объекты (аналог `safe_load`). Все YAML-файлы библиотеки, frontmatter
наблюдений и lock-файлы укладываются в это подмножество; если вам нужно нечто
большее — это признак, что данные пора упростить.
