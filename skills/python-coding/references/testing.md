# Test mechanics in Python

A spelling map, not a rule list: it says **how** a test rule is expressed
in Python, not which rules apply or why. The runner is the project's
choice — pytest and the stdlib `unittest` both satisfy everything below.

| What the test needs | Python spelling |
|---------------------|-----------------|
| A stand-in for a seam the project owns | a plain class implementing the `Protocol` the parameter is annotated with — no mock library needed |
| Patching, where no seam exists (last resort) | `monkeypatch.setattr` / `unittest.mock.patch` on a module attribute, with a comment justifying why no seam was available |
| A fixed clock | inject a `now: Callable[[], datetime]` parameter or a clock `Protocol`; never `time.sleep` to let wall-clock time pass |
| An asynchronous test | a real event loop (`asyncio.run`, `pytest-asyncio`, `anyio`); bound every await with `asyncio.timeout` instead of assuming completion |
| A skip that must ship | `@pytest.mark.skip(reason=...)` / `skipif(...)` or `unittest.skip(reason)` — the reason plus a tracking reference, never a bare marker |
| Relaxations confined to test files | `Any`, `cast`, `print` and patching are permitted in test modules only |
| Unit-testing a narrowing predicate | one test per `TypeGuard` / `TypeIs` function, including near-miss values the guard must reject |
| A positive type-level assertion | `typing.assert_type(value, Expected)` next to the utility it pins |
| A negative type-level assertion | a narrowly-scoped `# type: ignore[code]` under mypy `warn_unused_ignores` / pyright `reportUnnecessaryTypeIgnoreComment`, which turn an obsolete ignore into an error — the one sanctioned home of a type-level suppression |
| Runtime enforcement of a harmful bypass | raise a typed error (annotations are not enforcement) and exercise it from a test, since `assert` is stripped under `-O` |
| Generated cases | Hypothesis for parsers, serializers and pure functions with a statable invariant; pin every falsifying example it reports as an ordinary regression test |
| Names the runner discovers | `test_*.py`, `test_<behaviour>_<condition>`, one class or module per unit under test |

## The skill's own checker in test paths

`scripts/check_py_conventions.py` recognizes test paths (`test_*.py`,
`*_test.py`, `conftest.py`, and anything under `test/`, `tests/`,
`__test__/` or `__tests__/`) and drops exactly three rules there —
`PY-PRINT`, `PY-ANY`, `PY-ASSERT`, the relaxations listed above. Every
other rule, the security ones included, keeps firing in test files; see
[../knowledge/pitfalls.md](../knowledge/pitfalls.md) for why, and
[lint-clean.md](lint-clean.md) for the justified
`# skill-check-ignore: <CODE> -- <reason>` that is the only exemption.
