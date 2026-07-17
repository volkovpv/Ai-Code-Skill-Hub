"""Calibration fixture for the checker's lexical masking.

Every rule of the skill is quoted below inside a string, an f-string's
literal part, a triple-quoted string, or a comment — and none of it is
executable code, so the checker must report ZERO findings for this file.
Code inside f-string interpolations is still scanned (see the tests for
the positive case).

Quoted in this docstring nothing counts: print("x"), os.environ["HOME"],
value: Any = None, except:, assert data, breakpoint(), # type: ignore.
"""

from typing import Final

# In comments nothing counts: print("x") os.environ["HOME"] breakpoint()
# (Suppression tokens are the one comment-scanned rule, so they are quoted
# only inside the strings below, where they are data.)

QUOTED_RULES: Final = {
    "print_ban": 'never call print("anything") in shipped code',
    "env_ban": "os.environ reads must stay in the config layer",
    "any_ban": "a value typed ': Any' defeats strict mode",
    "suppress_ban": "do not write '# type: ignore' or '# noqa' comments",
    "except_ban": "a bare 'except:' clause traps SystemExit too",
    "assert_ban": "an 'assert payload' check vanishes under python -O",
    "debug_ban": "breakpoint() and pdb.set_trace() never ship",
    "pragma_as_data": "skill-check-ignore: PY-ENV -- a pragma in a string is data",
}

LABEL: Final = "widget"

# The literal part of an f-string is masked too — including rule-like text:
BANNER: Final = f"do not print('x') or assert {LABEL} in shipped code"

# A multi-line triple-quoted string stays masked across lines:
DOC: Final = """
examples that must not fire:
    print("boom")
    flag: Any = None
    except: pass
    assert value
    breakpoint()
"""
