"""Dedicated tests for skills/hexagonal-service (run via `skillctl test hexagonal-service`).

The skill has no scripts — it is a pure architecture standard — so the tests
pin its structural contract: valid layout, language/framework neutrality, the
error-flow invariants the audit mandates, and a consistent OpenAI adapter.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "hexagonal-service"

sys.path.insert(0, str(ROOT / "src"))

from skill_library import yamlio  # noqa: E402
from skill_library.discovery import split_frontmatter  # noqa: E402
from skill_library.validator import validate_skill_dir  # noqa: E402


def skill_texts() -> dict[str, str]:
    return {
        path.relative_to(SKILL).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(SKILL.rglob("*"))
        if path.is_file() and path.suffix in (".md", ".yaml")
    }


class TestStructure(unittest.TestCase):
    def test_skill_directory_validates_clean(self):
        self.assertEqual(validate_skill_dir(SKILL), [])

    def test_description_declares_agnostic_contract(self):
        fm, _ = split_frontmatter((SKILL / "SKILL.md").read_text(encoding="utf-8"))
        description = fm["description"]
        self.assertIn("language- and framework-agnostic", description)
        self.assertIn("ports and adapters", description)
        # The skill is neutral to projects too: the adoption strategy is
        # declared in the host project's rules, never by the skill.
        self.assertIn("project-neutral", description)
        self.assertIn("host project's rules", description)
        for strategy in ("module-first", "domain-first", "layer-first"):
            self.assertIn(strategy, description)

    def test_skill_md_routes_to_approaches_and_strategies(self):
        body = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/approaches.md", body)
        self.assertIn("references/strategies.md", body)

    def test_no_optional_layers_created_for_structure(self):
        # The skill is references-only; empty layer dirs would violate AGENTS.md.
        for layer in ("knowledge", "data", "observations"):
            self.assertFalse((SKILL / layer).exists(), layer)


class TestNeutrality(unittest.TestCase):
    """The skill must not smuggle in language or framework specifics."""

    FORBIDDEN = ("@nestjs", "tsconfig", "class-validator", "sequelize", "NestJS-only")

    def test_no_framework_or_language_mechanics_in_content(self):
        for rel, text in skill_texts().items():
            if rel.startswith("agents/"):
                continue  # the adapter may name sibling skills
            for token in self.FORBIDDEN:
                self.assertNotIn(token, text, f"{rel} mentions {token!r}")


class TestStrategyCatalog(unittest.TestCase):
    """The skill catalogs strategies but defers the choice to project rules."""

    def setUp(self) -> None:
        self.strategies = (SKILL / "references" / "strategies.md").read_text(encoding="utf-8")
        self.approaches = (SKILL / "references" / "approaches.md").read_text(encoding="utf-8")

    def test_layout_strategies_are_cataloged(self):
        for strategy in ("Module-first", "Layer-first", "Domain-first", "Ports-first"):
            self.assertIn(strategy, self.strategies)

    def test_rollout_and_migration_strategies_are_cataloged(self):
        for strategy in ("Walking skeleton", "Inside-out", "Strangler", "Seam"):
            self.assertIn(strategy, self.strategies)

    def test_choice_is_deferred_to_project_rules(self):
        self.assertIn("declared by the project, never by this skill", self.strategies)
        self.assertIn("What the project rules must declare", self.strategies)

    def test_approaches_cover_the_canonical_spectrum(self):
        for approach in ("two-layer", "Layered hexagonal", "Onion", "clean",
                         "Domain-driven design", "CQRS", "Component + Strategy"):
            self.assertIn(approach, self.approaches)

    def test_pattern_does_not_nest(self):
        normalized = " ".join(self.approaches.replace("**", "").split())
        self.assertIn("does not nest", normalized)


class TestErrorFlowInvariants(unittest.TestCase):
    """Pin the audit-mandated error discipline so edits cannot silently drop it."""

    def setUp(self) -> None:
        self.error_flow = (SKILL / "references" / "error-flow.md").read_text(encoding="utf-8")

    def test_raw_throws_forbidden_in_inner_layers(self):
        self.assertIn("Raw throws are forbidden in `domain` and `application`", self.error_flow)

    def test_single_wrap_at_driven_adapter_with_cause(self):
        self.assertIn("exactly once", self.error_flow)
        self.assertIn("driven adapter", self.error_flow)
        self.assertIn("cause", self.error_flow)

    def test_no_rewrapping_in_intermediate_layers(self):
        self.assertIn("Re-wrapping and catch-and-rethrow in intermediate layers are forbidden",
                      self.error_flow)

    def test_boundary_logs_once_with_stack_and_maps_once(self):
        self.assertIn("Log once, with the stack", self.error_flow)
        self.assertIn("Map once", self.error_flow)
        self.assertIn("RFC 9457", self.error_flow)

    def test_skill_md_routes_to_error_flow(self):
        body = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/error-flow.md", body)


class TestOpenAiAdapter(unittest.TestCase):
    def test_adapter_parses_in_yaml_subset_and_aligns_with_skill(self):
        data = yamlio.load_file(SKILL / "agents" / "openai.yaml")
        interface = data["interface"]
        prompt = interface["default_prompt"]
        self.assertTrue(prompt.strip())
        # The prompt states the activation scope and the neutrality boundary...
        self.assertIn("hexagonal-service", prompt)
        self.assertIn("language- and framework-agnostic", prompt)
        # ...and the project-instructions precedence the eval cases exercise.
        self.assertIn("precedence", prompt)


if __name__ == "__main__":
    unittest.main()
