# Тестирование skills

Этот документ задаёт практический процесс тестирования нового или изменённого
skill. Его цель — не максимизировать количество тестов, а как можно раньше
обнаруживать узкие места: неверное срабатывание skill, пропущенные инструкции,
опасные файловые операции, нестабильное поведение агента, слабые тестовые
оракулы и регрессии между версиями.

## Модель качества

Skill состоит из разных типов содержимого, поэтому одного line coverage
недостаточно:

- `SKILL.md` и `references/` проверяются через структуру, traceability правил,
  trigger-сценарии и поведенческие evals;
- `scripts/` проверяются обычными unit, property, integration, security и
  mutation-тестами;
- `data/` проверяется контрактом, воспроизводимостью и отсутствием
  чувствительных данных;
- установка проверяется contract, integration и E2E-сценариями;
- фактическое следование инструкциям проверяется запуском поддерживаемого
  агента, а не сравнением текста `SKILL.md`.

Используйте risk-based подход. Чем опаснее возможная ошибка, тем более
детерминированным должен быть тест и тем ближе его coverage к 100%.

| Приоритет | Что относится | Требование |
|---|---|---|
| P0 | секреты, path traversal, перезапись чужих файлов, destructive actions | позитивный и негативный тест; отсутствие дефекта во всех запусках |
| P1 | основной workflow, обязательные правила, формат результата | regression/contract test и минимум один поведенческий сценарий |
| P2 | рекомендации, удобство, качество формулировок | eval, rubric или ручной review |

## Обязательный процесс

### 1. До написания тестов

Составьте короткую карту изменения:

1. Что изменилось: metadata, workflow, reference, script, data, installer или
   policy.
2. Какое наблюдаемое поведение должно измениться.
3. Что не должно измениться.
4. Какие P0/P1-риски затронуты.
5. Каким тестовым оракулом можно независимо проверить результат.

Если ожидаемое поведение нельзя сформулировать в проверяемом виде, изменение
ещё не готово к реализации.

### 2. Во время разработки

- Новый дефект сначала воспроизводится падающим regression test или fixture.
- Тест проверяет внешний результат, а не внутреннюю реализацию без
  необходимости.
- Негативные сценарии пишутся вместе с happy path, а не после него.
- Fixtures минимальны: один fixture демонстрирует одну причину успеха или
  отказа.
- Для недетерминированного результата проверяются свойства и инварианты, а не
  полное текстовое совпадение.

### 3. Перед завершением работы

Из корня библиотеки обязательно выполните полный прогон:

```bash
uv run skillctl validate
uv run skillctl test
```

Эквивалентный zero-tooling fallback, используемый CI:

```bash
python3 scripts/skillctl.py validate
python3 scripts/skillctl.py test
```

В окружении, где команда называется `python`, замените `python3` на `python`.
Targeted-тесты ускоряют разработку, но не заменяют полный финальный прогон.

## Фактическая структура тестов

```text
__test__/
├── README.md
├── __init__.py
├── helpers.py
│
├── fixtures/                         # fixtures инфраструктуры библиотеки
│   ├── valid-skill/
│   │   ├── SKILL.md
│   │   ├── ORIGIN.yaml
│   │   ├── references/notes.md
│   │   └── scripts/probe.py
│   └── invalid-skill/
│       └── SKILL.md
│
├── evals/                            # versioned model-dependent eval cases
│   └── example-skill/cases.json
│
├── network_blocker/                  # Python-level network deny для subprocess
│   └── sitecustomize.py
│
├── skills/                           # dedicated-тесты опубликованных skills
│   ├── __init__.py
│   └── test_example_skill.py
│
├── scenarios/                        # ручные CLI/E2E-сценарии
│   └── README.md
│
├── test_cli.py
├── test_discovery.py
├── test_evals.py
├── test_installer.py
├── test_layers.py
├── test_lockfile.py
├── test_observations.py
├── test_release_gates.py
├── test_security.py
├── test_validator.py
└── test_yamlio.py
```

Не удаляйте существующие каталоги ради упрощения схемы. Они проверяют разные
контракты.

### Ответственность инфраструктурных тестов

| Файл | Что проверяет | Узкие места | Граница покрытия |
|---|---|---|---|
| `test_cli.py` | Аргументы, exit codes, `new`, CLI-lifecycle, stable test-gate и команды слоёв | неверные флаги/имена, target, rollback scaffold/catalog, ненулевой код ошибки | не проверяет внутреннюю корректность installer/validator и поведение агента |
| `test_discovery.py` | Поиск skills, frontmatter, каталог и директории | отсутствующий `SKILL.md`, broken frontmatter, лишний/пропущенный skill, порядок | не оценивает смысл `description` и trigger-выбор моделью |
| `test_evals.py` | Schema, ошибки manifest, install + запуск локального fake-harness | дубли ID, неверные expectations/platforms, сломанный runner contract | не запускает реальную модель и не подтверждает качество её ответа |
| `test_installer.py` | `install/diff/update/remove/status`, copy/link, runtime/full и failure injection | потеря правок, удаление чужих файлов, неидемпотентность, checksum, rollback после сбоя | не проверяет discovery и workflow в реальном harness |
| `test_layers.py` | Knowledge/data/observations, content policy и capabilities | слой без index/контракта, рассинхронизация flags, секреты, размеры, observation без evidence/review | не доказывает истинность knowledge и достаточность evidence |
| `test_lockfile.py` | CRUD lock-файла и поддерживаемое подмножество YAML | потеря записей, malformed YAML, duplicate keys, tabs, сериализация строк | не проверяет конкурентную запись и физический сбой диска |
| `test_observations.py` | `add/approve/reject/list`, dry-run и audit metadata | прямой candidate→accepted, approval без evidence/reviewer, потеря audit trail | не оценивает качество evidence и корректность promotion в правило |
| `test_release_gates.py` | Drift версий, release classification, `bump_version.py` и mutation-score gate | релиз без bump/changelog, downgrade, drift версий/`uv.lock`, mutation score ниже порога | не проверяет фактическую публикацию GitHub Release и эквивалентность surviving mutants |
| `test_security.py` | Имена, пути, traversal, symlink escape, очищенное окружение и Python network-deny | выход за target, symlink escape, утечка env/сети в Python subprocess | не является pentest и не заменяет сетевую изоляцию ОС для нативных программ |
| `test_validator.py` | Skill/library validation, fixtures, links, origin, catalog consistency | ложный успех сломанного skill, mismatch имени, dead/escaping links, uncatalogued/missing skill | не проверяет installer, качество инструкций и следование им моделью |
| `test_yamlio.py` | Парсер/сериализатор YAML-подмножества: quoting, escapes, комментарии, flow-списки, диагностика ошибок (строка/текст), round-trip dump→load | молчаливое принятие anchors/tabs/незакрытых кавычек, неверная строка в ошибке, потеря escape-последовательностей при dump | не проверяет полноту YAML-спецификации — подмножество зафиксировано намеренно |

Последний столбец показывает, какой соседний тест, eval или review должен
закрыть риск. Не превращайте один модуль в «тест всего»: узкая ответственность
даёт локализованную и понятную причину падения.

Дополнительные компоненты:

- `helpers.py` создаёт изолированные временные библиотеки и target-проекты;
- `fixtures/` задаёт переиспользуемые валидные и невалидные входы;
- `skills/test_<имя>.py` проверяет детерминированное поведение публикуемого skill;
- `scenarios/README.md` содержит ручные lifecycle-сценарии и не заменяет
  автоматический E2E с реальным harness.

### Два вида fixtures

`__test__/fixtures/` содержит общие эталонные skills для тестирования самой
библиотеки: discovery, validator, security и installer. Они не являются
публикуемыми skills и не устанавливаются пользователю.

`skills/<имя>/data/fixtures/` содержит предметные входы конкретного skill.
Они принадлежат его data-контракту, используются dedicated-тестами как
воспроизводимое evidence и не устанавливаются в runtime-режиме.

Не переносите эти наборы друг в друга: это скроет границу между тестированием
инфраструктуры и тестированием поведения skill.

### Исполняемые eval-наборы

Versioned cases хранятся в `__test__/evals/<имя-skill>/cases.json`. Manifest
schema v1 требует `skill`, `platforms` и непустые cases с полями `id`,
`kind`, `requirement`, `prompt`, `expect`. Допустимые виды:
`trigger`, `behavior`, `negative`. Оракулы: exit code,
обязательные/запрещённые подстроки и regex.

Проверка schema не запускает модель и обязательна в offline CI:

    uv run python scripts/run_skill_evals.py --validate-only __test__/evals/example-skill/cases.json

Реальный harness запускается только явно, отдельно от offline unittest:

    uv run python scripts/run_skill_evals.py --platform claude --repeat 3 --command 'claude -p {prompt}' __test__/evals/example-skill/cases.json

Runner устанавливает skill во временный проект перед каждым повтором. Команда
поддерживает placeholders `{prompt}`, `{project}`, `{skill}`. Не
сохраняйте в manifest credentials, PII или production data; логи реального
harness проверяются перед публикацией.

## Что проверяется автоматически, а что — на review

| Проверка | Текущее состояние |
|---|---|
| `skillctl validate` и `skillctl test` | реализованы и обязательны |
| Dedicated-тест stable skill | отсутствие блокирует targeted и полный `skillctl test` |
| `TODO/TBD/FIXME` в stable | блокируется status-aware validator; draft допускает placeholders |
| Line/branch coverage | `coverage.py`, branch mode, CI gate `fail_under = 80` |
| Mutation testing | `mutmut` для security/lockfile/installer/yamlio/validator; weekly/manual gate не ниже 75% |
| Trigger и behavioral evals | schema v1 и runner реализованы; manifest валидируется offline |
| E2E через реальный harness | opt-in runner; не выполняется в offline CI |
| Smoke заявленных platforms | manifest фиксирует matrix, фактический evidence нужен для каждой платформы |

Зелёный deterministic suite не доказывает качество ответа модели. Перед
релизом skill автор запускает применимые реальные harness cases и прикладывает
обезличенный агрегированный evidence.

## Результат аудита полноты

Исправлены найденные автоматически устранимые пробелы: stable gates,
placeholders, Python network-deny, атомарный lock, rollback mutating
операций, coverage gate, mutation workflow и versioned eval runner.

Остаются границы, которые нельзя честно выдать за покрытые обычным CI:

| Приоритет | Оставшаяся граница | Требование |
|---|---|---|
| P0 | Python-hook не изолирует сеть нативного binary | реальные harness/E2E запускать в OS/container sandbox с deny-by-default |
| P1 | Offline CI не вызывает Claude/Codex/OpenCode | перед релизом приложить pass-rate по каждой заявленной platform или сузить `platforms` |
| P1 | Regex/substring oracle не заменяет semantic judge | для сложного результата добавить rubric и независимую проверку артефакта |
| P2 | Нет seeded property/fuzz job | для нового parser/path кода сначала boundary table, затем воспроизводимый fuzz |
| P2 | Snapshot rollback не является multi-process transaction | не запускать mutating команды конкурентно; при появлении concurrency добавить lock/atomic swap |

## Карта применимости тестов

| Изменение | Обязательные проверки |
|---|---|
| `description` или имя | validation, positive/negative trigger cases |
| Workflow или обязательное правило | requirement traceability, behavioral eval, regression |
| `references/` или `knowledge/` | ссылки, routing, applicability scope, evidence |
| `scripts/` | unit, error paths, side effects, integration; mutation для критичного кода |
| `data/` | data contract, schema/format, license, PII/secret scan, reproducibility |
| `observations/` | lifecycle, evidence, review metadata, regression after promotion |
| Installer или lockfile | contract, runtime/full, idempotency, local-change protection, rollback |
| Security/path logic | positive/negative boundary cases, property/fuzz, mutation |
| Заявленная новая платформа | install smoke и E2E на этой платформе |

Если строка применима к изменению, перечисленные проверки обязательны или в PR
должно быть объяснено, почему конкретная проверка неприменима.

## Виды тестирования

### 1. Validation и статические контракты

`skillctl validate` проверяет frontmatter, `ORIGIN.yaml`, допустимую структуру,
ссылки, capabilities, knowledge/data/observations, размеры файлов и возможные
секреты. Это обязательный базовый уровень для каждого skill.

Дополнительно на review проверьте:

- в готовом skill нет `TODO`, `TBD` и `FIXME`;
- `description` содержит назначение и точные условия срабатывания;
- каждое утверждение в metadata подтверждается фактической возможностью;
- routing ведёт непосредственно к нужным файлам и сохраняет progressive
  disclosure;
- `skills.yaml`, версия, status, platforms и capabilities соответствуют
  содержимому;
- новые или изменённые знания имеют applicability scope и evidence.

Текущий валидатор не блокирует все эти смысловые дефекты автоматически,
поэтому успешный `validate` не заменяет review.

### 2. Unit-тесты детерминированного кода

Покрывайте функции библиотеки и файлы `scripts/`:

- нормальный, пустой, повреждённый и неподдерживаемый ввод;
- минимальные и максимальные допустимые значения;
- каждую ветвь классификации и обработки ошибок;
- exit code, stdout и stderr;
- таймауты и освобождение ресурсов;
- отсутствие неожиданных записей, сети и чтения секретов;
- повторяемость результата.

Запускайте skill scripts через `subprocess` с очищенным окружением,
ограниченным таймаутом и `tempfile.TemporaryDirectory`.

Для парсеров, путей и сериализации полезны property-based или fuzz-проверки:
случайный допустимый ввод сохраняет инварианты, а произвольный недопустимый
ввод завершается контролируемой ошибкой без частичного изменения состояния.
Если внешний fuzz-фреймворк не используется, применяйте детерминированную
таблицу граничных классов.

### 3. Fixture, golden и snapshot tests

Golden comparison подходит только для детерминированного результата. Такой
тест обязан показывать понятный diff при несовпадении.

Для LLM-результата проверяйте устойчивые свойства:

- обязательные секции и формат;
- валидность созданного файла;
- успешную компиляцию, lint или тесты целевого проекта;
- отсутствие запрещённых конструкций;
- отсутствие изменений вне разрешённого scope.

Не используйте полный ответ модели как snapshot: косметические изменения
создают шум и маскируют реальные регрессии.

### 4. Contract и integration tests

Проверяйте совместную работу `SKILL.md`, resources, scripts, manifest, data и
CLI. Для изменений распространения проверьте цепочку:

```text
validate → install → status → diff → update → remove
```

Обязательные границы:

- `runtime` и `full`;
- copy и link, если оба режима затронуты;
- повторная операция и идемпотентность;
- `--dry-run` без изменений;
- локально изменённый и unmanaged destination;
- смена версии и режима;
- ошибка посередине операции без повреждённого lock/state.

### 5. Security и negative tests

Для кода, работающего с файлами, путями или командами, проверяйте:

- `../`, абсолютные пути и смешанные разделители;
- symlink escape и вложенные symlinks;
- перезапись локальных изменений без `--force`;
- удаление только lock-managed файлов;
- malformed YAML/frontmatter/lockfile;
- секретоподобные строки и лимиты размера;
- неожиданные executable-файлы;
- очищенное окружение дочернего процесса;
- отсутствие сети и credential-sensitive действий;
- fail-closed поведение при неоднозначном состоянии.

Каждое P0-правило должно иметь тест, который сначала доказывает отказ опасной
операции, а затем отдельно подтверждает разрешённый happy path.

### 6. Regression tests и observations

Каждый исправленный дефект закрепляется минимальным regression test. Если
дефект породил observation, тест или fixture указывается как evidence.

Accepted observation не заменяет тест. После promotion правила в
`knowledge/` или `SKILL.md` соответствующий regression test должен оставаться
в наборе и защищать новое нормативное поведение.

### 7. Trigger и discovery evals

Отдельно тестируйте `description`, потому что она управляет загрузкой skill.
Для каждого skill подготовьте:

- очевидные релевантные запросы;
- перефразированные релевантные запросы;
- пограничные запросы;
- похожие, но нерелевантные запросы;
- конфликт с другим skill, если их области пересекаются.

Измеряйте:

- recall — долю релевантных запросов, активировавших skill;
- precision — долю активаций, которые действительно были релевантны;
- confusion — какие skills ошибочно выбираются вместо нужного.

### 8. Поведенческие evals

Каждый eval-case должен содержать:

```text
id                стабильный идентификатор
requirement       проверяемое правило или риск
given             синтетический проект и контекст
when              запрос пользователя
then              ожидаемые наблюдаемые свойства
forbidden         запрещённые действия и результаты
oracle            автоматическая проверка или rubric
repetitions       число повторов для недетерминированного поведения
models/harnesses  область применимости
evidence          лог/артефакт без секретов и PII
```

Минимум нужны normal, edge и negative case. Для P0/P1-сценариев выполняйте
несколько повторов и сохраняйте агрегированный результат, а не выбирайте один
удачный запуск.

Обычные тесты библиотеки не ходят в сеть. Реальные LLM-evals запускаются
отдельно перед релизом или вручную; в репозитории хранятся обезличенные inputs,
rubric и проверяемые свойства.

### 9. E2E и platform smoke

E2E подтверждает полный пользовательский путь:

1. skill устанавливается во временный проект;
2. целевой harness обнаруживает metadata;
3. релевантный запрос активирует skill;
4. агент выполняет workflow;
5. независимый валидатор проверяет артефакт;
6. посторонние файлы и настройки не изменены;
7. повторный запуск не создаёт нежелательный drift.

CLI lifecycle без запуска агента является integration test, но не полным E2E.
Для каждой реально заявленной платформы нужен smoke; если платформа не
проверена, это ограничение отражается в review/release evidence.

### 10. Mutation testing

Для кода мутируйте условия, границы, exit codes, обработчики ошибок и
security-проверки. Выжившая мутация означает слабый тест или недостижимый код
и требует анализа.

Разбор выживших (`uv run mutmut results`, диффы — `uv run mutmut show <id>`)
делит их на три класса; смешивать классы в отчёте нельзя:

1. **Реальный пробел теста** — мутация меняет наблюдаемое поведение, но набор
   зелёный. Обязателен добивающий тест (примеры закрытых пробелов: NUL-байт в
   `validate_relative_path`, `installed_state` для link-установок,
   `library_commit` вне git-репозитория, фильтры `iter_skill_files`).
2. **Непроверяемый текст сообщения** — мутация меняет только формулировку
   ошибки. Сообщения, по которым действует пользователь (главные отказы
   security/lockfile), закрепляются `assertRaisesRegex`; остальные допустимо
   оставить с пометкой «сообщение, не поведение».
3. **Эквивалентная мутация** — поведение неотличимо (размер чанка чтения в
   `file_sha256`, default-значения при всегда присутствующих ключах, ключ
   сортировки при обязательном поле `name`). Не чинится; фиксируется в PR как
   объяснённая.

Порог гейта (`scripts/check_mutation_score.py --minimum`) поднимается только
после разбора: сначала классы 1–2 закрываются тестами, затем порог фиксирует
достигнутый уровень с запасом не менее 3–5 п.п. на эквивалентный шум.

Для инструкций используйте instruction mutation:

- удалить или инвертировать критическое правило;
- убрать шаг validation/test;
- ослабить `description` или удалить trigger;
- заменить обязательное действие рекомендацией;
- добавить конфликтующую инструкцию в синтетический проект.

Хотя бы один тест/eval должен обнаружить каждую P0/P1 instruction mutation.
Mutation testing можно запускать периодически, но обязательно перед релизом
критичного security или installer-изменения.

## Traceability: правило → тест → evidence

Для сложного skill поддерживайте таблицу в dedicated-тесте, eval manifest или
PR-описании:

| Requirement | Priority | Test/eval | Oracle | Evidence |
|---|---|---|---|---|
| R-001: не менять файлы вне scope | P0 | `test_writes_only_in_scope` | список изменённых файлов | synthetic fixture |
| R-002: запускать validator перед завершением | P1 | `eval-validation-loop` | лог команды + exit code | eval artifact |

Цель — 100% P0/P1-требований с явной проверкой. Строка без test/eval показывает
узкое место раньше, чем формальный coverage report.

## Coverage и критерии эффективности

### Code coverage

CI измеряет line и branch coverage одним и тем же полным unittest-набором.
Минимальный merge-gate — 80% общего покрытия (`fail_under = 80`). Это baseline,
а не целевой потолок:

- для нового/изменённого детерминированного кода покрывайте все новые ветви;
- для security, path validation, lockfile и rollback стремитесь к 95–100%;
- падение общего процента запрещено без review и объяснения;
- mutation workflow для критичных модулей должен завершаться без
  необъяснённых surviving mutants.

Локальная команда: `uv run coverage run -m unittest discover -s __test__ -t .`
и затем `uv run coverage report`. Число без анализа `Missing` не является
критерием готовности.

### Requirement и scenario coverage

- 100% P0/P1-правил имеют test или eval;
- у каждого P0-правила есть positive и negative case;
- каждый workflow-шаг встречается хотя бы в одном сценарии;
- каждый исправленный дефект имеет regression test;
- каждое accepted observation имеет воспроизводимое evidence;
- каждая реально поддерживаемая платформа имеет smoke evidence;
- trigger-набор содержит positive, paraphrase, boundary и negative cases.

### Стабильность evals

Для model-dependent поведения записывайте модель, harness, конфигурацию и число
повторов. Критический forbidden outcome должен встречаться 0 раз. Порог общего
pass rate устанавливается до запуска, а не подгоняется после результата.

## Критерии готовности

### Любой изменённый skill

- полный `validate` и `test` завершились с exit code `0`;
- diff не содержит секретов, PII, случайных путей и незавершённых placeholders;
- version/capabilities соответствуют изменению;
- применимые строки карты тестов выполнены;
- отчёт содержит реальные команды и результаты.

### Изменение наблюдаемого поведения

- dedicated-тест добавлен или обновлён;
- новый тест падает на старом дефектном поведении;
- happy path, error path и затронутые P0/P1-инварианты проверены;
- отсутствуют необъяснённые skipped tests и flaky retries.

### Рекомендуемый review-gate для status `stable`

- нет `TODO`, `TBD`, `FIXME`;
- существует `__test__/skills/test_<имя_с_подчёркиваниями>.py`;
- минимум три поведенческих сценария: normal, edge, negative;
- P0/P1 traceability закрыта;
- заявленные platforms имеют smoke evidence либо явно документированное
  ограничение;
- критические regression и security tests зелёные.

Первые два пункта уже являются CLI/validator gates для status `stable`.
Наличие и качество normal/edge/negative evals, platform evidence и полнота
P0/P1 traceability остаются ответственностью автора и reviewer.

## Именование и размещение

- Тесты конкретного skill: `__test__/skills/test_<имя>.py`.
- Дефисы заменяются подчёркиваниями: `typescript-coding` →
  `test_typescript_coding.py`.
- Общие тесты называются по производственному модулю: `test_installer.py`,
  `test_security.py`.
- Общий fixture используется несколькими инфраструктурными тестами; fixture
  одного skill хранится в его `data/fixtures/`.
- Не создавайте пустые каталоги и не добавляйте `history/`.

## Локальный запуск

```bash
# основной способ: один skill во время разработки
uv run skillctl validate example-skill
uv run skillctl test example-skill -v

# один модуль
uv run python -m unittest __test__.skills.test_example_skill -v

# весь unittest-набор напрямую
uv run python -m unittest discover -s __test__ -t . -v

# coverage gate
uv run coverage run -m unittest discover -s __test__ -t .
uv run coverage report

# offline-проверка eval manifest
uv run python scripts/run_skill_evals.py --validate-only __test__/evals/example-skill/cases.json

# mutation critical paths (перед release/security изменением)
uv run mutmut run
uv run mutmut export-cicd-stats
uv run python scripts/check_mutation_score.py mutants/mutmut-cicd-stats.json --minimum 75
uv run mutmut results

# обязательный финальный прогон
uv run skillctl validate
uv run skillctl test

# zero-tooling fallback
python3 scripts/skillctl.py validate
python3 scripts/skillctl.py test
```

## Отчёт о тестировании

В PR или отчёте укажите:

```text
Изменение:
Риски P0/P1:
Добавленные/изменённые тесты:
Fixtures/evidence:
Команды и exit codes:
Количество пройденных тестов:
Coverage/mutation score (если применимо):
Eval model/harness/repetitions (если применимо):
Непроверенные области и причина:
```

Не объявляйте skill готовым только по успешному targeted-тесту, высокому line
coverage или одному удачному ответу модели. Готовность подтверждается
совокупностью детерминированных тестов, traceability требований, негативных
сценариев и независимых оракулов.
