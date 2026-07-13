# Test scenarios

Manual end-to-end scenarios for exercising the CLI. Every scenario is covered
by automated tests (see the sibling `test_*.py` modules), but they are handy to
run by hand while debugging. All commands are executed from the library root.

## Scenario 1: full skill lifecycle

```bash
PROJ=$(mktemp -d)
python scripts/skillctl.py list
python scripts/skillctl.py validate example-skill
python scripts/skillctl.py install example-skill --target "$PROJ" --agent universal --copy
python scripts/skillctl.py status --target "$PROJ"
cat "$PROJ/.agent-skills.lock.yaml"

# A "library-side update" cannot be simulated without editing the sources,
# so just check that the diff is empty and update is idempotent:
python scripts/skillctl.py diff example-skill --target "$PROJ"
python scripts/skillctl.py update example-skill --target "$PROJ"

python scripts/skillctl.py remove example-skill --target "$PROJ"
rm -rf "$PROJ"
```

Expected: every step exits with code 0; after `remove` the directory
`$PROJ/.agents/skills/example-skill` does not exist and the lock file has no
entry for the skill.

## Scenario 2: protection of local edits

```bash
PROJ=$(mktemp -d)
python scripts/skillctl.py install example-skill --target "$PROJ"
echo "local edit" >> "$PROJ/.agents/skills/example-skill/SKILL.md"
python scripts/skillctl.py status --target "$PROJ"          # state=modified
python scripts/skillctl.py update example-skill --target "$PROJ"; echo "exit=$?"  # refusal, exit=1
python scripts/skillctl.py remove example-skill --target "$PROJ"; echo "exit=$?"  # refusal, exit=1
python scripts/skillctl.py remove example-skill --target "$PROJ" --force
rm -rf "$PROJ"
```

## Scenario 3: creating a new skill

```bash
python scripts/skillctl.py new my-demo-skill
python scripts/skillctl.py validate my-demo-skill
python scripts/skillctl.py test my-demo-skill
# rollback:
git checkout -- skills.yaml && rm -rf skills/my-demo-skill
```

## Scenario 4: runtime vs full installation

```bash
P1=$(mktemp -d); P2=$(mktemp -d)
python scripts/skillctl.py install example-skill --target "$P1"              # runtime
python scripts/skillctl.py install example-skill --target "$P2" --mode full
ls "$P1/.agents/skills/example-skill/observations" 2>/dev/null   # only INDEX.md + accepted/
ls "$P2/.agents/skills/example-skill/observations/candidates"    # candidates exist only in full
python scripts/skillctl.py remove example-skill --target "$P1"
python scripts/skillctl.py remove example-skill --target "$P2"
rm -rf "$P1" "$P2"
```

## Scenario 5: observation lifecycle

```bash
printf '# Observation\n\nDescription with reproduction steps.\n' > /tmp/obs-note.md
python scripts/skillctl.py observation add example-skill --from /tmp/obs-note.md \
  --evidence "data/examples/feature_change.diff"
python scripts/skillctl.py observation list example-skill --status candidate
# approve without evidence would be refused; here evidence was set at add time:
python scripts/skillctl.py observation approve example-skill <OBS-ID> --reviewed-by <you>
python scripts/skillctl.py validate example-skill
# rollback:
git checkout -- skills/example-skill && git clean -fd skills/example-skill
```

## Scenario 6: Hermes (skills directory outside the project)

```bash
PROJ=$(mktemp -d); HERMES=$(mktemp -d)
python scripts/skillctl.py install example-skill --target "$PROJ" \
  --agent hermes --target-skills-dir "$HERMES"
ls "$HERMES/example-skill"
python scripts/skillctl.py remove example-skill --target "$PROJ"
rm -rf "$PROJ" "$HERMES"
```
