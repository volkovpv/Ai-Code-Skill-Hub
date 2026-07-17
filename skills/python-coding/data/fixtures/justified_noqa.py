"""Minimal, project-independent reproduction of the sanctioned noqa form.

Some linters flag intentionally-unused loop products; where the rule has a
documented limitation for a legitimate pattern, the narrow, justified,
single-rule `# noqa` below is the sanctioned linter-level escape hatch:
line-scoped, naming exactly one rule code, with a written reason after
`--`. Everything blanket, multi-rule, or unjustified stays a finding.
"""

from collections.abc import Iterator


def consume(source: Iterator[bytes]) -> int:
    """Drain an iterator, counting chunks without keeping them."""
    count = 0
    for chunk in source:  # noqa: B007 -- upstream rule limitation: draining is the point, chunk is unused
        count += 1
    return count
