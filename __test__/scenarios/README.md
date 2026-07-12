# Тестовые сценарии

Ручные end-to-end сценарии для проверки CLI. Каждый сценарий покрыт
автоматическими тестами (см. соседние `test_*.py`), но их удобно выполнять
руками при отладке. Все команды запускаются из корня библиотеки.

## Сценарий 1: полный жизненный цикл skill

```bash
PROJ=$(mktemp -d)
python scripts/skillctl.py list
python scripts/skillctl.py validate example-skill
python scripts/skillctl.py install example-skill --target "$PROJ" --agent universal --copy
python scripts/skillctl.py status --target "$PROJ"
cat "$PROJ/.agent-skills.lock.yaml"

# сымитировать «обновление в библиотеке» нельзя без правки исходников,
# поэтому просто проверяем, что diff пуст и update идемпотентен:
python scripts/skillctl.py diff example-skill --target "$PROJ"
python scripts/skillctl.py update example-skill --target "$PROJ"

python scripts/skillctl.py remove example-skill --target "$PROJ"
rm -rf "$PROJ"
```

Ожидается: каждый шаг завершается с кодом 0, после `remove` каталог
`$PROJ/.agents/skills/example-skill` не существует, lock-файл не содержит
записи о skill.

## Сценарий 2: защита локальных изменений

```bash
PROJ=$(mktemp -d)
python scripts/skillctl.py install example-skill --target "$PROJ"
echo "local edit" >> "$PROJ/.agents/skills/example-skill/SKILL.md"
python scripts/skillctl.py status --target "$PROJ"          # state=modified
python scripts/skillctl.py update example-skill --target "$PROJ"; echo "exit=$?"  # отказ, exit=1
python scripts/skillctl.py remove example-skill --target "$PROJ"; echo "exit=$?"  # отказ, exit=1
python scripts/skillctl.py remove example-skill --target "$PROJ" --force
rm -rf "$PROJ"
```

## Сценарий 3: создание нового skill

```bash
python scripts/skillctl.py new my-demo-skill
python scripts/skillctl.py validate my-demo-skill
python scripts/skillctl.py test my-demo-skill
# откат:
git checkout -- skills.yaml && rm -rf skills/my-demo-skill
```

## Сценарий 4: runtime vs full установка

```bash
P1=$(mktemp -d); P2=$(mktemp -d)
python scripts/skillctl.py install example-skill --target "$P1"              # runtime
python scripts/skillctl.py install example-skill --target "$P2" --mode full
ls "$P1/.agents/skills/example-skill/observations" 2>/dev/null   # только INDEX.md + accepted/
ls "$P2/.agents/skills/example-skill/observations/candidates"    # candidates есть только в full
python scripts/skillctl.py remove example-skill --target "$P1"
python scripts/skillctl.py remove example-skill --target "$P2"
rm -rf "$P1" "$P2"
```

## Сценарий 5: жизненный цикл наблюдения

```bash
printf '# Наблюдение\n\nОписание с шагами воспроизведения.\n' > /tmp/obs-note.md
python scripts/skillctl.py observation add example-skill --from /tmp/obs-note.md \
  --evidence "data/examples/feature_change.diff"
python scripts/skillctl.py observation list example-skill --status candidate
# approve без evidence отказал бы; здесь evidence задан при add:
python scripts/skillctl.py observation approve example-skill <OBS-ID> --reviewed-by <вы>
python scripts/skillctl.py validate example-skill
# откат:
git checkout -- skills/example-skill && git clean -fd skills/example-skill
```

## Сценарий 6: Hermes (каталог вне проекта)

```bash
PROJ=$(mktemp -d); HERMES=$(mktemp -d)
python scripts/skillctl.py install example-skill --target "$PROJ" \
  --agent hermes --target-skills-dir "$HERMES"
ls "$HERMES/example-skill"
python scripts/skillctl.py remove example-skill --target "$PROJ"
rm -rf "$PROJ" "$HERMES"
```
