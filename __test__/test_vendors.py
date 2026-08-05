"""Vendor registry: schema, mutations, the sync gate and the `vendor` commands.

The registry is the only place the library records who supplies a model and
which effort levels that model accepts, so every rule here is fail-closed: a
malformed entry raises instead of being repaired, and an unfinished
documentation sync blocks the gate rather than passing quietly.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

from skill_library import vendors
from skill_library.cli import main

from .helpers import ROOT, TempDirTestCase

VENDOR_BLOCK = """\
  - name: {name}
    display_name: {display}
    in_use: {in_use}
    effort_param: output_config.effort
    effort_levels: [low, medium, high]
    default_effort: high
    effort_env_var: {env_var}
    docs_models: {docs_models}
    docs_effort: {docs_effort}
    docs_checked_at: {checked_at}
    docs_checked_by: {checked_by}
    docs_refresh_required: {refresh}
    last_refresh_reason: {reason}
"""

MODEL_BLOCK = """\
  - id: {model_id}
    vendor: {vendor}
    effort_levels: {levels}
    default_effort: {default}
    status: {status}
    added_at: {added_at}
    verified: {verified}
"""


def vendor_block(
    name: str = "acme",
    *,
    display: str = "Acme",
    in_use: str = "true",
    env_var: str = "ACME_EFFORT",
    docs_models: str = "https://acme.example/models.md",
    docs_effort: str = "https://acme.example/effort.md",
    checked_at: str = "2026-08-05",
    checked_by: str = "reviewer",
    refresh: str = "false",
    reason: str = "operator-request",
) -> str:
    return VENDOR_BLOCK.format(
        name=name,
        display=display,
        in_use=in_use,
        env_var=env_var,
        docs_models=docs_models,
        docs_effort=docs_effort,
        checked_at=checked_at,
        checked_by=checked_by,
        refresh=refresh,
        reason=reason,
    )


def model_block(
    model_id: str = "acme-1",
    *,
    vendor: str = "acme",
    levels: str = "[low, medium, high]",
    default: str = "high",
    status: str = "current",
    added_at: str = "2026-08-05",
    verified: str = "true",
) -> str:
    return MODEL_BLOCK.format(
        model_id=model_id,
        vendor=vendor,
        levels=levels,
        default=default,
        status=status,
        added_at=added_at,
        verified=verified,
    )


def registry_text(vendors_block: str | None = None, models_block: str | None = None) -> str:
    return (
        "version: 1\nvendors:\n"
        + (vendor_block() if vendors_block is None else vendors_block)
        + "models:\n"
        + (model_block() if models_block is None else models_block)
    )


def run_cli(*argv: str) -> tuple[int, str, str]:
    """Run the CLI in-process; argparse usage errors exit rather than return."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exit_:
            code = int(exit_.code or 0)
    return code, out.getvalue(), err.getvalue()


class TestRegistrySchema(TempDirTestCase):
    def load(self, text: str) -> vendors.Registry:
        return vendors.loads_registry(text)

    def assert_rejected(self, text: str, fragment: str) -> None:
        with self.assertRaises(vendors.VendorError) as caught:
            self.load(text)
        self.assertIn(fragment, str(caught.exception))

    def test_minimal_registry_loads(self):
        registry = self.load(registry_text())
        self.assertEqual(registry.vendor_names, ("acme",))
        self.assertEqual(registry.effort_levels_for("acme", "acme-1"), ["low", "medium", "high"])
        self.assertEqual(registry.effort_env_vars("acme"), {"ACME_EFFORT"})

    def test_model_may_declare_no_effort_levels_at_all(self):
        # An empty list is a fact, not a gap: some models reject the vendor's
        # effort field outright, and a run must not be allowed to name one.
        registry = self.load(registry_text(models_block=model_block(levels="[]", default="null")))
        self.assertEqual(registry.effort_levels_for("acme", "acme-1"), [])

    def test_unknown_top_level_key_is_rejected(self):
        self.assert_rejected(registry_text() + "extra: 1\n", "unknown top-level key(s): extra")

    def test_version_must_be_one(self):
        self.assert_rejected(registry_text().replace("version: 1", "version: 2"), "version: must be 1")

    def test_vendors_must_be_a_list(self):
        self.assert_rejected("version: 1\nvendors: {}\nmodels: []\n", "vendors: must be a list")

    def test_at_least_one_vendor_is_required(self):
        self.assert_rejected("version: 1\nvendors: []\nmodels: []\n", "at least one vendor")

    def test_missing_and_unknown_vendor_fields_are_rejected(self):
        without = vendor_block().replace("    in_use: true\n", "")
        self.assert_rejected(registry_text(vendors_block=without), "missing field(s): in_use")
        extra = vendor_block() + "    temperature: 0\n"
        self.assert_rejected(registry_text(vendors_block=extra), "unknown field(s): temperature")

    def test_names_come_from_a_safe_alphabet(self):
        for bad in ("Acme", "acme_1", "-acme", "a" * 65):
            with self.subTest(name=bad):
                self.assert_rejected(
                    registry_text(
                        vendors_block=vendor_block(name=bad),
                        models_block=model_block(vendor=bad),
                    ),
                    "lowercase latin letters",
                )

    def test_model_ids_come_from_the_same_alphabet(self):
        self.assert_rejected(
            registry_text(models_block=model_block(model_id="Acme-1")), "lowercase latin letters"
        )

    def test_vendor_must_declare_at_least_one_effort_level(self):
        self.assert_rejected(
            registry_text(vendors_block=vendor_block().replace(
                "effort_levels: [low, medium, high]", "effort_levels: []"
            )),
            "at least one level",
        )

    def test_duplicate_effort_level_is_rejected(self):
        self.assert_rejected(
            registry_text(models_block=model_block(levels="[low, low]")),
            "duplicate effort level 'low'",
        )

    def test_default_effort_must_be_a_declared_level(self):
        self.assert_rejected(
            registry_text(models_block=model_block(default="max")),
            "not among the declared effort levels",
        )
        # ...and a model with no levels may not carry a default either.
        self.assert_rejected(
            registry_text(models_block=model_block(levels="[]", default="high")),
            "not among the declared effort levels",
        )
        # ...while a model that has levels must name one.
        self.assert_rejected(
            registry_text(models_block=model_block(default="null")),
            "must name one of low, medium, high",
        )

    def test_model_levels_must_be_a_subset_of_the_vendor_levels(self):
        self.assert_rejected(
            registry_text(models_block=model_block(levels="[low, xhigh]", default="low")),
            "xhigh not declared by vendor 'acme'",
        )

    def test_model_vendor_must_exist(self):
        self.assert_rejected(
            registry_text(models_block=model_block(vendor="nobody")),
            "unknown vendor 'nobody'",
        )

    def test_duplicate_vendor_and_duplicate_model_are_rejected(self):
        self.assert_rejected(
            registry_text(vendors_block=vendor_block() + vendor_block()), "duplicate vendor 'acme'"
        )
        self.assert_rejected(
            registry_text(models_block=model_block() + model_block()), "duplicate model 'acme-1'"
        )

    def test_closed_sets_are_enforced(self):
        self.assert_rejected(
            registry_text(models_block=model_block(status="preview")),
            "status: must be one of current, legacy, retired",
        )
        self.assert_rejected(
            registry_text(vendors_block=vendor_block(reason="curiosity")),
            "must be one of new-model, operator-request",
        )

    def test_dates_flags_urls_and_env_vars_are_typed(self):
        self.assert_rejected(
            registry_text(vendors_block=vendor_block(checked_at="05.08.2026")), "YYYY-MM-DD"
        )
        self.assert_rejected(
            registry_text(models_block=model_block(added_at="soon")), "YYYY-MM-DD"
        )
        self.assert_rejected(
            registry_text(models_block=model_block(verified="yes")), "must be true or false"
        )
        self.assert_rejected(
            registry_text(vendors_block=vendor_block(docs_models="http://acme.example/m.md")),
            "must be an https:// URL",
        )
        self.assert_rejected(
            registry_text(vendors_block=vendor_block(env_var="acme_effort")),
            "UPPER_SNAKE environment variable name",
        )

    def test_missing_file_is_an_error_not_an_empty_registry(self):
        with self.assertRaises(vendors.VendorError):
            vendors.load_registry(self.tmp)


class TestRegistryRoundTrip(TempDirTestCase):
    def test_dump_reload_preserves_every_field(self):
        registry = vendors.loads_registry(registry_text())
        self.assertEqual(vendors.loads_registry(vendors.dumps_registry(registry)).as_dict(),
                         registry.as_dict())

    def test_the_checked_in_registry_is_emitted_byte_for_byte(self):
        # `vendor apply` rewrites the file; if the emitter and the checked-in
        # layout disagreed, every sync would produce a spurious diff.
        registry = vendors.load_registry(ROOT)
        self.assertEqual(
            vendors.dumps_registry(registry),
            (ROOT / vendors.VENDORS_FILENAME).read_text(encoding="utf-8"),
        )

    def test_saving_an_invalid_registry_is_refused(self):
        registry = vendors.loads_registry(registry_text())
        registry.models[0].vendor = "nobody"
        with self.assertRaises(vendors.VendorError):
            vendors.save_registry(self.tmp, registry)
        self.assertFalse((self.tmp / vendors.VENDORS_FILENAME).exists())


class TestAddModel(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.registry = vendors.loads_registry(registry_text())

    def test_registering_a_model_demands_a_new_documentation_sync(self):
        model = vendors.add_model(self.registry, "acme", "acme-2", added_at="2026-09-01")
        self.assertFalse(model.verified)
        self.assertTrue(self.registry.vendor("acme").docs_refresh_required)
        # Defaults are inherited from the vendor when the caller names none.
        self.assertEqual(model.effort_levels, ["low", "medium", "high"])
        self.assertEqual(model.default_effort, "high")

    def test_explicit_levels_and_status_are_honoured(self):
        model = vendors.add_model(
            self.registry,
            "acme",
            "acme-3",
            added_at="2026-09-01",
            effort_levels=["low"],
            default_effort="low",
            status="legacy",
        )
        self.assertEqual((model.effort_levels, model.default_effort, model.status),
                         (["low"], "low", "legacy"))

    def test_duplicate_unknown_vendor_and_foreign_level_are_refused(self):
        with self.assertRaises(vendors.VendorError):
            vendors.add_model(self.registry, "acme", "acme-1", added_at="2026-09-01")
        with self.assertRaises(vendors.VendorError):
            vendors.add_model(self.registry, "nobody", "x-1", added_at="2026-09-01")
        with self.assertRaisesRegex(vendors.VendorError, "not declared by vendor"):
            vendors.add_model(
                self.registry, "acme", "acme-4", added_at="2026-09-01", effort_levels=["max"]
            )


class TestRefreshPlan(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.registry = vendors.loads_registry(registry_text())

    def plan(self, **kwargs) -> str:
        options = {"reason": "operator-request", "reviewed_by": "reviewer", "model_id": None}
        options.update(kwargs)
        return vendors.refresh_plan(self.registry, "acme", **options)

    def test_plan_names_both_pages_the_fields_and_where_the_answer_goes(self):
        plan = self.plan()
        self.assertIn("https://acme.example/models.md", plan)
        self.assertIn("https://acme.example/effort.md", plan)
        for field in ("effort_param", "effort_levels", "default_effort", "effort_env_var"):
            self.assertIn(field, plan)
        self.assertIn("checked_at", plan)
        self.assertIn("vendor apply acme --from", plan)

    def test_a_vendor_without_recorded_pages_says_so(self):
        self.registry.vendor("acme").docs_models = None
        self.assertIn("not recorded", self.plan())

    def test_reason_must_come_from_the_closed_set_and_a_reviewer_is_required(self):
        with self.assertRaises(vendors.VendorError):
            self.plan(reason="because")
        with self.assertRaises(vendors.VendorError):
            self.plan(reviewed_by="  ")

    def test_unknown_vendor_or_foreign_model_is_refused(self):
        with self.assertRaises(vendors.VendorError):
            vendors.refresh_plan(
                self.registry, "nobody", reason="new-model", reviewed_by="r", model_id=None
            )
        with self.assertRaises(vendors.VendorError):
            self.plan(model_id="other-1")


class TestApplyRefresh(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.registry = vendors.loads_registry(
            registry_text(
                vendors_block=vendor_block(refresh="true", checked_at="null", checked_by="null",
                                           reason="null"),
                models_block=model_block(verified="false") + model_block(
                    model_id="acme-2", verified="false"
                ),
            )
        )

    def apply(self, result: dict, reviewed_by: str = "reviewer") -> list[str]:
        return vendors.apply_refresh(self.registry, result, reviewed_by=reviewed_by)

    def test_apply_clears_the_flag_and_records_who_checked_what_and_when(self):
        self.apply({"vendor": "acme", "checked_at": "2026-09-02", "reason": "new-model"})
        vendor = self.registry.vendor("acme")
        self.assertFalse(vendor.docs_refresh_required)
        self.assertEqual(vendor.docs_checked_at, "2026-09-02")
        self.assertEqual(vendor.docs_checked_by, "reviewer")
        self.assertEqual(vendor.last_refresh_reason, "new-model")
        self.assertTrue(all(m.verified for m in self.registry.models_of("acme")))

    def test_models_verified_may_name_a_subset(self):
        self.apply(
            {
                "vendor": "acme",
                "checked_at": "2026-09-02",
                "reason": "new-model",
                "models_verified": ["acme-1"],
            }
        )
        self.assertTrue(self.registry.model("acme-1").verified)
        self.assertFalse(self.registry.model("acme-2").verified)

    def test_vendor_fields_are_updated(self):
        self.apply(
            {
                "vendor": "acme",
                "checked_at": "2026-09-02",
                "reason": "operator-request",
                "effort_param": "reasoning.effort",
                "effort_levels": ["low", "high"],
                "default_effort": "low",
                "effort_env_var": None,
                "docs_effort": "https://acme.example/new-effort.md",
                # A level the vendor no longer offers has to leave its models in
                # the same sync — see the containment test below.
                "models": [
                    {"id": "acme-1", "effort_levels": ["low", "high"]},
                    {"id": "acme-2", "effort_levels": ["low", "high"]},
                ],
            }
        )
        vendor = self.registry.vendor("acme")
        self.assertEqual(vendor.effort_param, "reasoning.effort")
        self.assertEqual(vendor.effort_levels, ["low", "high"])
        self.assertEqual(vendor.default_effort, "low")
        self.assertIsNone(vendor.effort_env_var)
        self.assertEqual(vendor.docs_effort, "https://acme.example/new-effort.md")

    def test_per_model_corrections_are_applied(self):
        self.apply(
            {
                "vendor": "acme",
                "checked_at": "2026-09-02",
                "reason": "operator-request",
                "models": [
                    {"id": "acme-1", "effort_levels": [], "default_effort": None},
                    {"id": "acme-2", "status": "retired"},
                ],
            }
        )
        self.assertEqual(self.registry.model("acme-1").effort_levels, [])
        self.assertIsNone(self.registry.model("acme-1").default_effort)
        self.assertEqual(self.registry.model("acme-2").status, "retired")

    def test_a_shrunk_level_set_never_strands_a_model_default(self):
        # The vendor drops a level the model's default pointed at; the registry
        # must not be left naming a default that no longer exists.
        self.apply(
            {
                "vendor": "acme",
                "checked_at": "2026-09-02",
                "reason": "operator-request",
                "models": [{"id": "acme-1", "effort_levels": ["low", "medium"]}],
            }
        )
        self.assertIsNone(self.registry.model("acme-1").default_effort)

    def test_dropping_a_vendor_level_a_model_still_claims_is_refused(self):
        # Silently trimming the model would hide a real disagreement between
        # the sync and the registry; the sync has to state both.
        with self.assertRaisesRegex(vendors.VendorError, "not declared by vendor"):
            self.apply(
                {
                    "vendor": "acme",
                    "checked_at": "2026-09-02",
                    "reason": "operator-request",
                    "effort_levels": ["low", "high"],
                    "default_effort": "low",
                }
            )

    def test_a_vendor_level_set_that_strands_its_own_default_is_refused(self):
        with self.assertRaisesRegex(vendors.VendorError, "no longer among the declared"):
            self.apply(
                {
                    "vendor": "acme",
                    "checked_at": "2026-09-02",
                    "reason": "operator-request",
                    "effort_levels": ["low"],
                }
            )

    def test_malformed_results_are_refused(self):
        for result, fragment in (
            ({"vendor": "acme", "checked_at": "2026-09-02"}, "missing field(s): reason"),
            (
                {"vendor": "acme", "checked_at": "2026-09-02", "reason": "later"},
                "must be one of new-model, operator-request",
            ),
            (
                {"vendor": "acme", "checked_at": "soon", "reason": "new-model"},
                "YYYY-MM-DD",
            ),
            (
                {"vendor": "nobody", "checked_at": "2026-09-02", "reason": "new-model"},
                "unknown vendor",
            ),
            (
                {"vendor": "acme", "checked_at": "2026-09-02", "reason": "new-model", "note": "x"},
                "unknown field(s): note",
            ),
            (
                {
                    "vendor": "acme",
                    "checked_at": "2026-09-02",
                    "reason": "new-model",
                    "models_verified": ["other-1"],
                },
                "not registered for vendor",
            ),
            (
                {
                    "vendor": "acme",
                    "checked_at": "2026-09-02",
                    "reason": "new-model",
                    "models": [{"id": "other-1"}],
                },
                "not registered for vendor",
            ),
        ):
            with self.subTest(result=result):
                with self.assertRaises(vendors.VendorError) as caught:
                    self.apply(result)
                self.assertIn(fragment, str(caught.exception))

    def test_a_reviewer_is_required(self):
        with self.assertRaises(vendors.VendorError):
            self.apply({"vendor": "acme", "checked_at": "2026-09-02", "reason": "new-model"}, " ")


class TestCheckGate(TempDirTestCase):
    def check(self, text: str) -> list[str]:
        (self.tmp / vendors.VENDORS_FILENAME).write_text(text, encoding="utf-8")
        return vendors.check_registry(vendors.load_registry(self.tmp), self.tmp)

    def write_adapter(self, vendor_name: str) -> None:
        agents = self.tmp / "skills" / "demo" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / f"{vendor_name}.yaml").write_text("interface:\n  display_name: Demo\n", "utf-8")

    def write_manifest(self, tier: dict) -> None:
        manifest = self.tmp / "__test__" / "evals" / "demo" / "cases.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"tiers": {"gate": tier}}), encoding="utf-8")

    def test_a_clean_registry_passes(self):
        self.assertEqual(self.check(registry_text()), [])

    def test_pending_sync_blocks_a_vendor_in_use(self):
        problems = self.check(registry_text(vendors_block=vendor_block(refresh="true")))
        self.assertEqual(len(problems), 1)
        self.assertIn("documentation sync is pending", problems[0])

    def test_pending_sync_of_a_vendor_not_in_use_does_not_block(self):
        # Declared groundwork: nothing measures against it yet, so the gate has
        # nothing to protect.
        text = registry_text(vendors_block=vendor_block(in_use="false", refresh="true"))
        self.assertEqual(self.check(text), [])

    def test_a_sync_older_than_the_newest_model_blocks(self):
        text = registry_text(
            vendors_block=vendor_block(checked_at="2026-08-05"),
            models_block=model_block() + model_block(model_id="acme-2", added_at="2026-09-01"),
        )
        problems = self.check(text)
        self.assertEqual(len(problems), 1)
        self.assertIn("older than the newest registered model", problems[0])

    def test_an_unrecorded_documentation_page_blocks_a_vendor_in_use(self):
        problems = self.check(registry_text(vendors_block=vendor_block(docs_effort="null")))
        self.assertIn("docs_effort is not recorded", problems[0])

    def test_an_unknown_vendor_in_agents_blocks(self):
        self.write_adapter("nobody")
        problems = self.check(registry_text())
        self.assertIn("unknown vendor 'nobody'", problems[0])
        self.assertIn("skills/demo/agents/nobody.yaml", problems[0])

    def test_a_known_vendor_in_agents_passes(self):
        self.write_adapter("acme")
        self.assertEqual(self.check(registry_text()), [])

    def test_an_unknown_vendor_or_model_in_an_eval_manifest_blocks(self):
        self.write_manifest({"vendor": "nobody", "model": "acme-1", "effort": "high"})
        self.assertIn("unknown vendor 'nobody'", self.check(registry_text())[0])
        self.write_manifest({"vendor": "acme", "model": "acme-9", "effort": "high"})
        self.assertIn("unknown model 'acme-9'", self.check(registry_text())[0])

    def test_the_repository_registry_is_consistent_with_its_references(self):
        # Every adapter file and every eval tier in this repository names a
        # vendor and a model the registry knows.
        registry = vendors.load_registry(ROOT)
        dangling = [p for p in vendors.check_registry(registry, ROOT) if "unknown" in p]
        self.assertEqual(dangling, [])


class TestNoNetwork(TempDirTestCase):
    def test_the_registry_module_imports_nothing_that_can_reach_the_network(self):
        # The library prepares the sync and records its result; the trip to the
        # vendor is made by whoever has network access, never by this code.
        source = (ROOT / "src" / "skill_library" / "vendors.py").read_text(encoding="utf-8")
        for module in ("socket", "urllib", "http.client", "requests", "ssl", "subprocess"):
            self.assertNotIn(f"import {module}", source)


class TestVendorCli(TempDirTestCase):
    def cli(self, *argv: str) -> tuple[int, str, str]:
        return run_cli("--library-root", str(self.tmp), "vendor", *argv)

    def setUp(self) -> None:
        super().setUp()
        (self.tmp / vendors.VENDORS_FILENAME).write_text(registry_text(), encoding="utf-8")

    def registry(self) -> vendors.Registry:
        return vendors.load_registry(self.tmp)

    def test_list_and_show(self):
        code, out, _ = self.cli("list")
        self.assertEqual(code, 0)
        self.assertIn("acme", out)
        self.assertIn("acme-1", out)

        code, out, _ = self.cli("show", "acme")
        self.assertEqual(code, 0)
        self.assertIn("output_config.effort", out)

        code, _, err = self.cli("show", "nobody")
        self.assertEqual(code, 1)
        self.assertIn("unknown vendor", err)

    def test_add_model_writes_the_flag_through_to_the_file(self):
        code, out, _ = self.cli("add-model", "acme", "acme-2", "--added-at", "2026-09-01")
        self.assertEqual(code, 0, out)
        self.assertIsNotNone(self.registry().model("acme-2"))
        self.assertTrue(self.registry().vendor("acme").docs_refresh_required)

        code, _, err = self.cli("add-model", "acme", "acme-2", "--added-at", "2026-09-01")
        self.assertEqual(code, 1)
        self.assertIn("already registered", err)

    def test_refresh_requires_a_reason_from_the_closed_set_and_a_reviewer(self):
        code, out, _ = self.cli(
            "refresh", "acme", "--reason", "operator-request", "--reviewed-by", "reviewer"
        )
        self.assertEqual(code, 0, out)
        self.assertIn("REFRESH acme", out)
        # A plan changes nothing — recording the answer is `vendor apply`.
        self.assertFalse(self.registry().vendor("acme").docs_refresh_required)

        code, _, _ = self.cli("refresh", "acme", "--reviewed-by", "reviewer")
        self.assertEqual(code, 2)
        code, _, _ = self.cli("refresh", "acme", "--reason", "operator-request")
        self.assertEqual(code, 2)
        code, _, _ = self.cli(
            "refresh", "acme", "--reason", "boredom", "--reviewed-by", "reviewer"
        )
        self.assertEqual(code, 2)

    def test_apply_records_the_result_and_check_turns_green(self):
        self.cli("add-model", "acme", "acme-2", "--added-at", "2026-09-01")
        code, _, err = self.cli("check")
        self.assertEqual(code, 1, err)

        result = self.tmp / "sync.yaml"
        result.write_text(
            "vendor: acme\nchecked_at: 2026-09-02\nreason: new-model\n", encoding="utf-8"
        )
        code, out, _ = self.cli("apply", "acme", "--from", str(result), "--reviewed-by", "reviewer")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.registry().vendor("acme").docs_checked_by, "reviewer")

        code, out, _ = self.cli("check")
        self.assertEqual(code, 0, out)
        self.assertIn("OK", out)

    def test_apply_accepts_a_json_result_file(self):
        result = self.tmp / "sync.json"
        result.write_text(
            json.dumps({"vendor": "acme", "checked_at": "2026-09-02", "reason": "new-model"}),
            encoding="utf-8",
        )
        code, out, _ = self.cli("apply", "acme", "--from", str(result), "--reviewed-by", "r")
        self.assertEqual(code, 0, out)

    def test_apply_refuses_a_result_for_another_vendor(self):
        result = self.tmp / "sync.yaml"
        result.write_text(
            "vendor: acme\nchecked_at: 2026-09-02\nreason: new-model\n", encoding="utf-8"
        )
        code, _, err = self.cli("apply", "other", "--from", str(result), "--reviewed-by", "r")
        self.assertEqual(code, 1)
        self.assertIn("other", err)

    def test_a_missing_registry_is_reported_not_ignored(self):
        Path(self.tmp / vendors.VENDORS_FILENAME).unlink()
        code, _, err = self.cli("list")
        self.assertEqual(code, 1)
        self.assertIn(vendors.VENDORS_FILENAME, err)


if __name__ == "__main__":
    import unittest

    unittest.main()
