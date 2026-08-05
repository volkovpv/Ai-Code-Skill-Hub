"""Registry of model vendors, their models and effort levels.

A **vendor** is a model supplier (Anthropic, OpenAI, ...). It is not a harness:
``platforms`` in ``skills.yaml`` names harnesses and stays a separate axis. The
registry answers three questions the rest of the library asks:

* which vendors and models exist, and which effort levels each model accepts —
  so an eval manifest cannot declare an environment nobody can run;
* which adapter files a skill's ``agents/`` directory must hold;
* whether the cached vendor facts have been checked against the vendor's own
  documentation, and when.

The library never goes to the network. ``refresh`` prints the plan for a human
or an agent that *can*, and ``apply`` records the answer they bring back.

Everything is fail-closed: any malformed entry raises :class:`VendorError`
instead of being repaired or skipped.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import yamlio

__all__ = [
    "VENDORS_FILENAME",
    "MODEL_STATUSES",
    "REFRESH_REASONS",
    "VendorError",
    "Vendor",
    "Model",
    "Registry",
    "load_registry",
    "dumps_registry",
    "save_registry",
    "add_model",
    "refresh_plan",
    "apply_refresh",
    "check_registry",
]

VENDORS_FILENAME = "vendors.yaml"

MODEL_STATUSES = ("current", "legacy", "retired")
REFRESH_REASONS = ("new-model", "operator-request")

MAX_NAME_LENGTH = 64
# Vendor and model identifiers name files (agents/<vendor>.yaml) and reach the
# shell through the eval runner, so the alphabet is closed: lowercase latin,
# digits, dot and hyphen.
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
_EFFORT_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URL_RE = re.compile(r"^https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$")

_VENDOR_KEYS = (
    "name",
    "display_name",
    "in_use",
    "effort_param",
    "effort_levels",
    "default_effort",
    "effort_env_var",
    "docs_models",
    "docs_effort",
    "docs_checked_at",
    "docs_checked_by",
    "docs_refresh_required",
    "last_refresh_reason",
)
_MODEL_KEYS = ("id", "vendor", "effort_levels", "default_effort", "status", "added_at", "verified")

_HEADER = """\
# Registry of model vendors, their models and effort levels.
# Facts here are cached: they are refreshed only by `skillctl vendor refresh`
# followed by `skillctl vendor apply`. No other work in this repository goes to
# a vendor's documentation or edits this file.
# A vendor is a model supplier, not a harness: the `platforms` list in
# skills.yaml (universal, codex, opencode, claude, hermes) is a different axis.
# `in_use: true` marks a vendor the library actually measures against; those are
# the ones `skillctl vendor check` holds to a completed documentation sync.
"""


class VendorError(ValueError):
    """Raised when the registry, or an update to it, is not well formed."""


# ----------------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------------

@dataclass
class Vendor:
    """One vendor entry: its effort dial and the state of its documentation sync."""

    name: str
    display_name: str
    in_use: bool = False
    effort_param: str = ""
    effort_levels: list[str] = field(default_factory=list)
    default_effort: str | None = None
    effort_env_var: str | None = None
    docs_models: str | None = None
    docs_effort: str | None = None
    docs_checked_at: str | None = None
    docs_checked_by: str | None = None
    docs_refresh_required: bool = True
    last_refresh_reason: str | None = None

    def as_dict(self) -> dict:
        return {key: getattr(self, key) for key in _VENDOR_KEYS}


@dataclass
class Model:
    """One model entry. ``effort_levels: []`` means the vendor's effort dial
    does not apply to this model at all — not that it is unknown."""

    id: str
    vendor: str
    effort_levels: list[str] = field(default_factory=list)
    default_effort: str | None = None
    status: str = "current"
    added_at: str = ""
    verified: bool = False

    def as_dict(self) -> dict:
        return {key: getattr(self, key) for key in _MODEL_KEYS}


@dataclass
class Registry:
    """The whole ``vendors.yaml``, already validated."""

    version: int = 1
    vendors: list[Vendor] = field(default_factory=list)
    models: list[Model] = field(default_factory=list)

    def vendor(self, name: str) -> Vendor | None:
        return next((v for v in self.vendors if v.name == name), None)

    def model(self, model_id: str) -> Model | None:
        return next((m for m in self.models if m.id == model_id), None)

    def models_of(self, vendor_name: str) -> list[Model]:
        return [m for m in self.models if m.vendor == vendor_name]

    @property
    def vendor_names(self) -> tuple[str, ...]:
        return tuple(v.name for v in self.vendors)

    def effort_levels_for(self, vendor_name: str, model_id: str | None = None) -> list[str]:
        """Levels a run may declare: the model's own, or the vendor's when the
        model is not named. A model that declares none accepts none."""
        if model_id is not None:
            model = self.model(model_id)
            if model is None:
                raise VendorError(f"unknown model {model_id!r}")
            return list(model.effort_levels)
        vendor = self.vendor(vendor_name)
        if vendor is None:
            raise VendorError(f"unknown vendor {vendor_name!r}")
        return list(vendor.effort_levels)

    def effort_env_vars(self, vendor_name: str | None = None) -> set[str]:
        """Environment variables that could pre-set the effort of a run.

        Without a vendor the answer is *every* vendor's variable: a run that
        does not name its vendor must still not inherit the operator's setting.
        """
        vendors = self.vendors if vendor_name is None else [self.vendor(vendor_name)]
        return {v.effort_env_var for v in vendors if v is not None and v.effort_env_var}

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            "vendors": [v.as_dict() for v in self.vendors],
            "models": [m.as_dict() for m in self.models],
        }


# ----------------------------------------------------------------------------
# Field validation
# ----------------------------------------------------------------------------

def _require_mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise VendorError(f"{label}: must be a mapping")
    return value


def _known_keys(data: dict, keys: tuple[str, ...], label: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise VendorError(f"{label}: missing field(s): {', '.join(missing)}")
    unknown = sorted(set(data) - set(keys))
    if unknown:
        raise VendorError(f"{label}: unknown field(s): {', '.join(unknown)}")


def _name(value: object, label: str) -> str:
    if not isinstance(value, str) or not _NAME_RE.match(value) or len(value) > MAX_NAME_LENGTH:
        raise VendorError(
            f"{label}: must be lowercase latin letters, digits, '.' or '-', "
            f"at most {MAX_NAME_LENGTH} characters, got {value!r}"
        )
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise VendorError(f"{label}: must be a non-empty single-line string")
    return value


def _optional(value: object, label: str, check) -> object | None:
    return None if value is None else check(value, label)


def _flag(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise VendorError(f"{label}: must be true or false")
    return value


def _date(value: object, label: str) -> str:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise VendorError(f"{label}: must be a YYYY-MM-DD date, got {value!r}")
    return value


def _url(value: object, label: str) -> str:
    if not isinstance(value, str) or not _URL_RE.match(value):
        raise VendorError(f"{label}: must be an https:// URL, got {value!r}")
    return value


def _env_var(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ENV_VAR_RE.match(value):
        raise VendorError(f"{label}: must be an UPPER_SNAKE environment variable name")
    return value


def _choice(value: object, allowed: tuple[str, ...], label: str) -> str:
    if value not in allowed:
        raise VendorError(f"{label}: must be one of {', '.join(allowed)}, got {value!r}")
    return str(value)


def _levels(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise VendorError(f"{label}: must be a list of effort levels")
    seen: list[str] = []
    for level in value:
        if not isinstance(level, str) or not _EFFORT_RE.match(level):
            raise VendorError(f"{label}: {level!r} is not a valid effort level")
        if level in seen:
            raise VendorError(f"{label}: duplicate effort level {level!r}")
        seen.append(level)
    return seen


def _default_effort(value: object, levels: list[str], label: str) -> str | None:
    """The default must be one of the declared levels; no levels, no default."""
    if value is None:
        if levels:
            raise VendorError(f"{label}: must name one of {', '.join(levels)}")
        return None
    if not isinstance(value, str) or value not in levels:
        raise VendorError(
            f"{label}: {value!r} is not among the declared effort levels "
            f"({', '.join(levels) or 'none'})"
        )
    return value


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------

def _parse_vendor(raw: object, index: int) -> Vendor:
    label = f"vendors[{index}]"
    data = _require_mapping(raw, label)
    _known_keys(data, _VENDOR_KEYS, label)
    name = _name(data["name"], f"{label}.name")
    levels = _levels(data["effort_levels"], f"vendors[{name}].effort_levels")
    if not levels:
        raise VendorError(f"vendors[{name}].effort_levels: must declare at least one level")
    return Vendor(
        name=name,
        display_name=_text(data["display_name"], f"vendors[{name}].display_name"),
        in_use=_flag(data["in_use"], f"vendors[{name}].in_use"),
        effort_param=_text(data["effort_param"], f"vendors[{name}].effort_param"),
        effort_levels=levels,
        default_effort=_default_effort(
            data["default_effort"], levels, f"vendors[{name}].default_effort"
        ),
        effort_env_var=_optional(
            data["effort_env_var"], f"vendors[{name}].effort_env_var", _env_var
        ),
        docs_models=_optional(data["docs_models"], f"vendors[{name}].docs_models", _url),
        docs_effort=_optional(data["docs_effort"], f"vendors[{name}].docs_effort", _url),
        docs_checked_at=_optional(
            data["docs_checked_at"], f"vendors[{name}].docs_checked_at", _date
        ),
        docs_checked_by=_optional(
            data["docs_checked_by"], f"vendors[{name}].docs_checked_by", _text
        ),
        docs_refresh_required=_flag(
            data["docs_refresh_required"], f"vendors[{name}].docs_refresh_required"
        ),
        last_refresh_reason=_optional(
            data["last_refresh_reason"],
            f"vendors[{name}].last_refresh_reason",
            lambda v, label_: _choice(v, REFRESH_REASONS, label_),
        ),
    )


def _parse_model(raw: object, index: int) -> Model:
    label = f"models[{index}]"
    data = _require_mapping(raw, label)
    _known_keys(data, _MODEL_KEYS, label)
    model_id = _name(data["id"], f"{label}.id")
    levels = _levels(data["effort_levels"], f"models[{model_id}].effort_levels")
    return Model(
        id=model_id,
        vendor=_name(data["vendor"], f"models[{model_id}].vendor"),
        effort_levels=levels,
        default_effort=_default_effort(
            data["default_effort"], levels, f"models[{model_id}].default_effort"
        ),
        status=_choice(data["status"], MODEL_STATUSES, f"models[{model_id}].status"),
        added_at=_date(data["added_at"], f"models[{model_id}].added_at"),
        verified=_flag(data["verified"], f"models[{model_id}].verified"),
    )


def _validate_registry(registry: Registry) -> Registry:
    """Cross-entry rules: unique names, resolvable vendors, level containment."""
    seen_vendors: set[str] = set()
    for vendor in registry.vendors:
        if vendor.name in seen_vendors:
            raise VendorError(f"duplicate vendor {vendor.name!r}")
        seen_vendors.add(vendor.name)
    if not registry.vendors:
        raise VendorError("vendors: must declare at least one vendor")

    seen_models: set[str] = set()
    for model in registry.models:
        if model.id in seen_models:
            raise VendorError(f"duplicate model {model.id!r}")
        seen_models.add(model.id)
        vendor = registry.vendor(model.vendor)
        if vendor is None:
            raise VendorError(f"models[{model.id}].vendor: unknown vendor {model.vendor!r}")
        extra = [level for level in model.effort_levels if level not in vendor.effort_levels]
        if extra:
            raise VendorError(
                f"models[{model.id}].effort_levels: {', '.join(extra)} not declared by "
                f"vendor {vendor.name!r} ({', '.join(vendor.effort_levels)})"
            )
    return registry


def loads_registry(text: str) -> Registry:
    try:
        data = yamlio.loads(text)
    except yamlio.YamlError as exc:
        raise VendorError(str(exc)) from exc
    data = _require_mapping(data, VENDORS_FILENAME)
    unknown = sorted(set(data) - {"version", "vendors", "models"})
    if unknown:
        raise VendorError(f"unknown top-level key(s): {', '.join(unknown)}")
    if data.get("version") != 1:
        raise VendorError("version: must be 1")
    for key in ("vendors", "models"):
        if not isinstance(data.get(key), list):
            raise VendorError(f"{key}: must be a list")
    registry = Registry(
        version=1,
        vendors=[_parse_vendor(raw, i) for i, raw in enumerate(data["vendors"])],
        models=[_parse_model(raw, i) for i, raw in enumerate(data["models"])],
    )
    return _validate_registry(registry)


def registry_path(library_root: Path) -> Path:
    return Path(library_root) / VENDORS_FILENAME


def load_registry(library_root: Path) -> Registry:
    """Load ``<library_root>/vendors.yaml``; raises :class:`VendorError`."""
    path = registry_path(library_root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VendorError(f"{VENDORS_FILENAME}: cannot read: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise VendorError(f"{VENDORS_FILENAME}: is not valid UTF-8 ({exc})") from exc
    try:
        return loads_registry(text)
    except VendorError as exc:
        raise VendorError(f"{VENDORS_FILENAME}: {exc}") from exc


# ----------------------------------------------------------------------------
# Emitting
# ----------------------------------------------------------------------------

# Plain (unquoted) output is limited to what this registry actually stores and
# what yamlio reads back unchanged; anything else is double-quoted.
_PLAIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:#?=&%-]*$")
_RESERVED = {"null", "true", "false", "yes", "no", "on", "off", "~"}


def _scalar(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if _PLAIN_RE.match(text) and text.lower() not in _RESERVED and not text.isdigit():
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _entry(data: dict, keys: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    for position, key in enumerate(keys):
        value = data[key]
        rendered = (
            "[" + ", ".join(_scalar(item) for item in value) + "]"
            if isinstance(value, list)
            else _scalar(value)
        )
        lines.append(f"{'  - ' if position == 0 else '    '}{key}: {rendered}")
    return lines


def dumps_registry(registry: Registry) -> str:
    """Serialise the registry in the layout the checked-in file uses.

    yamlio's emitter has no flow lists, and this file is read by humans as much
    as by the CLI, so the registry emits itself rather than round-tripping
    through the generic dumper.
    """
    lines = [_HEADER.rstrip("\n"), "version: 1", "vendors:"]
    for vendor in registry.vendors:
        lines.extend(_entry(vendor.as_dict(), _VENDOR_KEYS))
    lines.append("models:")
    for model in registry.models:
        lines.extend(_entry(model.as_dict(), _MODEL_KEYS))
    return "\n".join(lines) + "\n"


def save_registry(library_root: Path, registry: Registry) -> Path:
    """Write the registry back, refusing to persist an invalid one."""
    _validate_registry(registry)
    text = dumps_registry(registry)
    # Fail closed: a file this process cannot read back is not written at all.
    loads_registry(text)
    path = registry_path(library_root)
    path.write_text(text, encoding="utf-8")
    return path


# ----------------------------------------------------------------------------
# Mutations
# ----------------------------------------------------------------------------

def add_model(
    registry: Registry,
    vendor_name: str,
    model_id: str,
    *,
    added_at: str,
    effort_levels: list[str] | None = None,
    default_effort: str | None = None,
    status: str = "current",
) -> Model:
    """Register a model and mark its vendor as awaiting a documentation sync.

    A new model version is one of the two sanctioned reasons to go to the
    vendor's documentation, so registering one raises the flag that
    ``vendor check`` reads.
    """
    vendor = registry.vendor(vendor_name)
    if vendor is None:
        raise VendorError(f"unknown vendor {vendor_name!r}")
    _name(model_id, "model id")
    if registry.model(model_id) is not None:
        raise VendorError(f"model {model_id!r} is already registered")
    levels = _levels(
        vendor.effort_levels if effort_levels is None else effort_levels, "effort levels"
    )
    extra = [level for level in levels if level not in vendor.effort_levels]
    if extra:
        raise VendorError(
            f"effort levels {', '.join(extra)} are not declared by vendor {vendor_name!r}"
        )
    if default_effort is None and vendor.default_effort in levels:
        default_effort = vendor.default_effort
    model = Model(
        id=model_id,
        vendor=vendor_name,
        effort_levels=levels,
        default_effort=_default_effort(default_effort, levels, "default effort"),
        status=_choice(status, MODEL_STATUSES, "status"),
        added_at=_date(added_at, "added_at"),
        verified=False,
    )
    registry.models.append(model)
    vendor.docs_refresh_required = True
    _validate_registry(registry)
    return model


def refresh_plan(
    registry: Registry, vendor_name: str, *, reason: str, reviewed_by: str, model_id: str | None
) -> str:
    """The sync plan a networked agent or operator executes by hand.

    The library never fetches anything itself, so this is the contract between
    the two halves: what to open, what to extract, where to put the answer.
    """
    vendor = registry.vendor(vendor_name)
    if vendor is None:
        raise VendorError(f"unknown vendor {vendor_name!r}")
    _choice(reason, REFRESH_REASONS, "reason")
    if not reviewed_by.strip():
        raise VendorError("--reviewed-by must name the human or role doing the sync")
    if model_id is not None:
        model = registry.model(model_id)
        if model is None or model.vendor != vendor_name:
            raise VendorError(f"model {model_id!r} is not registered for vendor {vendor_name!r}")

    unrecorded = "(not recorded — find the canonical page and put it in the result file)"
    scope = f"model {model_id}" if model_id else "every registered model"
    known = ", ".join(m.id for m in registry.models_of(vendor_name)) or "(none registered)"
    return "\n".join(
        [
            f"REFRESH {vendor_name} reason={reason} reviewed-by={reviewed_by} scope={scope}",
            "",
            "1. Open the vendor's own documentation:",
            f"   models: {vendor.docs_models or unrecorded}",
            f"   effort: {vendor.docs_effort or unrecorded}",
            "",
            "2. Extract exactly these facts:",
            "   - effort_param      the request field that carries the effort level",
            "   - effort_levels     every level the vendor accepts, in order",
            "   - default_effort    the level applied when the field is omitted",
            "   - effort_env_var    the environment variable that presets it, or null",
            "   - models            new models, retired models, and any model whose",
            "                       effort levels differ from the vendor default set",
            f"   currently registered: {known}",
            "",
            "3. Write the answer as YAML or JSON in the yamlio subset:",
            f"   vendor: {vendor_name}",
            "   checked_at: YYYY-MM-DD        # the date the documentation was read",
            f"   reason: {reason}",
            "   effort_param: ...             # omit any field the sync did not change",
            "   effort_levels: [...]",
            "   default_effort: ...",
            "   effort_env_var: ...",
            "   docs_models: https://...",
            "   docs_effort: https://...",
            "   models:                       # optional per-model corrections",
            "     - id: ...",
            "       effort_levels: [...]",
            "       default_effort: ...",
            "       status: current|legacy|retired",
            "   models_verified: [...]        # defaults to every model of the vendor",
            "",
            "4. Record it:",
            f"   skillctl vendor apply {vendor_name} --from <file> --reviewed-by {reviewed_by}",
            "",
            "New models found during the sync are registered separately with",
            f"   skillctl vendor add-model {vendor_name} <model-id>",
            "which raises the refresh flag again, so the sync is repeated for them.",
        ]
    )


_RESULT_KEYS = (
    "vendor",
    "checked_at",
    "reason",
    "effort_param",
    "effort_levels",
    "default_effort",
    "effort_env_var",
    "docs_models",
    "docs_effort",
    "models",
    "models_verified",
)
_RESULT_REQUIRED = ("vendor", "checked_at", "reason")
_RESULT_MODEL_KEYS = ("id", "effort_levels", "default_effort", "status")


def _apply_model_correction(registry: Registry, vendor: Vendor, raw: object, index: int) -> str:
    data = _require_mapping(raw, f"models[{index}]")
    unknown = sorted(set(data) - set(_RESULT_MODEL_KEYS))
    if unknown:
        raise VendorError(f"models[{index}]: unknown field(s): {', '.join(unknown)}")
    if "id" not in data:
        raise VendorError(f"models[{index}]: missing field(s): id")
    model = registry.model(_name(data["id"], f"models[{index}].id"))
    if model is None or model.vendor != vendor.name:
        raise VendorError(
            f"models[{index}]: {data['id']!r} is not registered for vendor {vendor.name!r}"
        )
    changes: list[str] = []
    if "effort_levels" in data:
        model.effort_levels = _levels(data["effort_levels"], f"models[{model.id}].effort_levels")
        changes.append(f"effort_levels=[{', '.join(model.effort_levels)}]")
        # A shrunk level set can strand the default; re-derive it unless the
        # result file also names one.
        if model.default_effort not in model.effort_levels and "default_effort" not in data:
            model.default_effort = (
                vendor.default_effort if vendor.default_effort in model.effort_levels else None
            )
            changes.append(f"default_effort={model.default_effort}")
    if "default_effort" in data:
        model.default_effort = _default_effort(
            data["default_effort"], model.effort_levels, f"models[{model.id}].default_effort"
        )
        changes.append(f"default_effort={model.default_effort}")
    if "status" in data:
        model.status = _choice(data["status"], MODEL_STATUSES, f"models[{model.id}].status")
        changes.append(f"status={model.status}")
    return f"{model.id}: {', '.join(changes)}" if changes else f"{model.id}: no change"


def apply_refresh(registry: Registry, result: object, *, reviewed_by: str) -> list[str]:
    """Record the outcome of a documentation sync. Returns what changed."""
    data = _require_mapping(result, "refresh result")
    unknown = sorted(set(data) - set(_RESULT_KEYS))
    if unknown:
        raise VendorError(f"refresh result: unknown field(s): {', '.join(unknown)}")
    missing = [key for key in _RESULT_REQUIRED if key not in data]
    if missing:
        raise VendorError(f"refresh result: missing field(s): {', '.join(missing)}")
    if not reviewed_by.strip():
        raise VendorError("--reviewed-by must name the human or role doing the sync")

    vendor = registry.vendor(_name(data["vendor"], "refresh result: vendor"))
    if vendor is None:
        raise VendorError(f"unknown vendor {data['vendor']!r}")
    checked_at = _date(data["checked_at"], "refresh result: checked_at")
    reason = _choice(data["reason"], REFRESH_REASONS, "refresh result: reason")

    changes: list[str] = []
    if "effort_levels" in data:
        vendor.effort_levels = _levels(data["effort_levels"], "effort_levels")
        if not vendor.effort_levels:
            raise VendorError("effort_levels: must declare at least one level")
        changes.append(f"effort_levels=[{', '.join(vendor.effort_levels)}]")
    if "default_effort" in data:
        vendor.default_effort = _default_effort(
            data["default_effort"], vendor.effort_levels, "default_effort"
        )
        changes.append(f"default_effort={vendor.default_effort}")
    elif vendor.default_effort not in vendor.effort_levels:
        raise VendorError(
            f"default_effort {vendor.default_effort!r} is no longer among the declared "
            "effort levels — name the new default in the result file"
        )
    if "effort_param" in data:
        # The request field that carries the level always exists; only the
        # environment variable and the doc URLs may legitimately be absent.
        vendor.effort_param = _text(data["effort_param"], "effort_param")
        changes.append(f"effort_param={vendor.effort_param}")
    for key, check in (
        ("effort_env_var", _env_var),
        ("docs_models", _url),
        ("docs_effort", _url),
    ):
        if key in data:
            setattr(vendor, key, _optional(data[key], key, check))
            changes.append(f"{key}={getattr(vendor, key)}")

    for index, raw in enumerate(data.get("models") or []):
        changes.append(_apply_model_correction(registry, vendor, raw, index))

    owned = [m.id for m in registry.models_of(vendor.name)]
    if "models_verified" in data:
        verified = data["models_verified"]
        if not isinstance(verified, list):
            raise VendorError("models_verified: must be a list of model ids")
        foreign = [str(m) for m in verified if m not in owned]
        if foreign:
            raise VendorError(
                f"models_verified: {', '.join(foreign)} not registered for vendor {vendor.name!r}"
            )
    else:
        verified = owned
    for model_id in verified:
        model = registry.model(str(model_id))
        if model is not None:
            model.verified = True

    vendor.docs_checked_at = checked_at
    vendor.docs_checked_by = reviewed_by
    vendor.docs_refresh_required = False
    vendor.last_refresh_reason = reason
    changes.append(f"verified=[{', '.join(str(m) for m in verified) or 'none'}]")
    changes.append(f"docs_checked_at={checked_at} docs_checked_by={reviewed_by} reason={reason}")
    _validate_registry(registry)
    return changes


# ----------------------------------------------------------------------------
# The gate
# ----------------------------------------------------------------------------

def _referenced(library_root: Path) -> list[tuple[str, str, str]]:
    """Every (kind, name, where) the repository points at the registry with."""
    root = Path(library_root)
    found: list[tuple[str, str, str]] = []
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for adapter in sorted(skills_dir.glob("*/agents/*.yaml")):
            found.append(("vendor", adapter.stem, adapter.relative_to(root).as_posix()))
    evals_dir = root / "__test__" / "evals"
    for manifest in sorted(evals_dir.glob("*/cases.json")):
        where = manifest.relative_to(root).as_posix()
        try:
            tiers = json.loads(manifest.read_text(encoding="utf-8")).get("tiers") or {}
        except (OSError, ValueError):
            continue  # the eval runner owns manifest syntax; this gate reads names only
        if not isinstance(tiers, dict):
            continue
        for tier, dials in tiers.items():
            if not isinstance(dials, dict):
                continue
            for kind, key in (("vendor", "vendor"), ("model", "model")):
                value = dials.get(key)
                if isinstance(value, str) and value:
                    found.append((kind, value, f"{where} ({tier})"))
    return found


def check_registry(registry: Registry, library_root: Path) -> list[str]:
    """Gate: unfinished syncs for vendors in use, and dangling references.

    Referential integrity is enforced for every vendor; the documentation-sync
    obligation only binds vendors declared ``in_use`` — the others are declared
    groundwork and nothing measures against them yet.
    """
    problems: list[str] = []
    for vendor in registry.vendors:
        if not vendor.in_use:
            continue
        if vendor.docs_refresh_required:
            problems.append(
                f"{vendor.name}: documentation sync is pending (docs_refresh_required); "
                f"run 'skillctl vendor refresh {vendor.name} --reason <new-model|"
                "operator-request> --reviewed-by <name>'"
            )
            continue
        if vendor.docs_checked_at is None:
            problems.append(f"{vendor.name}: docs_checked_at is not recorded")
            continue
        newest = max((m.added_at for m in registry.models_of(vendor.name)), default=None)
        if newest is not None and vendor.docs_checked_at < newest:
            problems.append(
                f"{vendor.name}: docs_checked_at {vendor.docs_checked_at} is older than the "
                f"newest registered model ({newest}) — sync the documentation again"
            )
        for missing in ("docs_models", "docs_effort"):
            if getattr(vendor, missing) is None:
                problems.append(f"{vendor.name}: {missing} is not recorded")

    for kind, name, where in _referenced(library_root):
        known = registry.vendor(name) if kind == "vendor" else registry.model(name)
        if known is None:
            problems.append(f"{where}: unknown {kind} {name!r} is not in {VENDORS_FILENAME}")
    return problems
