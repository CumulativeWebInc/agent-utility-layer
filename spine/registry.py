"""Module registry: load and validate every modules/*/capability.json.

Layout walked: <root>/modules/<pillar>/<module>/capability.json
  (module dir "_" prefixed dirs like _template are included;
   pillar dirs starting with "_" are skipped except _template's pillar.)

A module is "live" when: capability.json validates AND handler.py exists.
Live modules get exec API access and demo pages. Everything else is reported
as skeleton/invalid — never silently dropped.
"""

import json
import os

from permissions import is_declared  # noqa: F401  (spine dir on sys.path)

REQUIRED_FIELDS = {
    "name": str,
    "provisional": bool,
    "pillar": str,
    "version": str,
    "description": str,
    "permissions": list,
    "inputs_schema": dict,
    "outputs_schema": dict,
    "setup_price_usd": (int, float),
    "price_per_execution_usd": (int, float),
}

_VERSION_OK = lambda v: isinstance(v, str) and len(v.split(".")) == 3  # noqa: E731


def validate_capability(data: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a capability.json payload."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ["capability.json must be a JSON object"], warnings
    for field, types in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"missing required field: {field}")
        elif not isinstance(data[field], types):
            errors.append(f"field {field!r} must be {types}, got {type(data[field]).__name__}")
    if data.get("name") and not str(data["name"]).replace("_", "").isalnum():
        errors.append("name must be snake_case alphanumeric")
    if "version" in data and not _VERSION_OK(data["version"]):
        errors.append("version must look like X.Y.Z")
    for perm in data.get("permissions", []) or []:
        if not isinstance(perm, str) or ":" not in perm or perm != perm.lower():
            errors.append(f"permission must be lowercase 'scope:action': {perm!r}")
        elif not is_declared(perm):
            warnings.append(f"permission not in spine registry (declare it): {perm!r}")
    for which in ("inputs_schema", "outputs_schema"):
        schema = data.get(which)
        if isinstance(schema, dict):
            if schema.get("type") != "object":
                warnings.append(f"{which}.type should be 'object'")
            if not isinstance(schema.get("properties", {}), dict):
                errors.append(f"{which}.properties must be an object")
    for price_field in ("setup_price_usd", "price_per_execution_usd"):
        value = data.get(price_field)
        if isinstance(value, (int, float)) and value < 0:
            errors.append(f"{price_field} must be >= 0")
    return errors, warnings


# ---- minimal JSON-schema validation (stdlib) --------------------------------

_SCHEMA_TYPES = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def validate_inputs(schema: dict, inputs: dict) -> list[str]:
    """Validate inputs against an inputs_schema. Return list of error strings."""
    errors: list[str] = []
    if not isinstance(inputs, dict):
        return ["inputs must be a JSON object"]
    props = schema.get("properties", {}) or {}
    for name in schema.get("required", []) or []:
        if name not in inputs:
            errors.append(f"missing required input: {name!r}")
    for name, value in inputs.items():
        spec = props.get(name)
        if spec is None:
            errors.append(f"unknown input: {name!r}")
            continue
        errors.extend(_check_value(name, value, spec))
    return errors


def _check_value(path: str, value, spec: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, dict):
        return errors
    want = spec.get("type")
    if want:
        py = _SCHEMA_TYPES.get(want)
        if py and not isinstance(value, py):
            errors.append(f"{path!r} must be {want}, got {type(value).__name__}")
            return errors
        if want == "integer" and isinstance(value, bool):  # bool is subclass of int
            errors.append(f"{path!r} must be integer, got boolean")
    if "enum" in spec and value not in spec["enum"]:
        errors.append(f"{path!r} must be one of {spec['enum']}")
    if isinstance(value, str):
        if "minLength" in spec and len(value) < spec["minLength"]:
            errors.append(f"{path!r} shorter than minLength {spec['minLength']}")
        if "maxLength" in spec and len(value) > spec["maxLength"]:
            errors.append(f"{path!r} longer than maxLength {spec['maxLength']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in spec and value < spec["minimum"]:
            errors.append(f"{path!r} below minimum {spec['minimum']}")
        if "maximum" in spec and value > spec["maximum"]:
            errors.append(f"{path!r} above maximum {spec['maximum']}")
    if want == "object" and isinstance(value, dict):
        sub = {"type": "object", "properties": spec.get("properties", {}),
               "required": spec.get("required", [])}
        for e in validate_inputs(sub, value):
            errors.append(f"{path}.{e}")
    return errors


# ---- registry ----------------------------------------------------------------

class ModuleInfo:
    def __init__(self, name, pillar, directory, capability, errors, warnings, handler_path):
        self.name = name
        self.pillar = pillar
        self.directory = directory
        self.capability = capability
        self.errors = errors
        self.warnings = warnings
        self.handler_path = handler_path

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def live(self) -> bool:
        return self.valid and self.handler_path is not None

    @property
    def state(self) -> str:
        if self.live:
            return "live"
        if self.errors:
            return "invalid"
        return "skeleton"


class ModuleRegistry:
    def __init__(self):
        self.modules: dict[str, ModuleInfo] = {}

    def live_modules(self) -> dict[str, ModuleInfo]:
        return {n: m for n, m in self.modules.items() if m.live}

    def to_listing(self) -> list[dict]:
        out = []
        for name in sorted(self.modules):
            m = self.modules[name]
            cap = m.capability or {}
            out.append({
                "name": name,
                "pillar": m.pillar,
                "version": cap.get("version", ""),
                "description": cap.get("description", ""),
                "permissions": cap.get("permissions", []),
                "setup_price_usd": cap.get("setup_price_usd"),
                "price_per_execution_usd": cap.get("price_per_execution_usd"),
                "state": m.state,
                "provisional": cap.get("provisional", True),
            })
        return out


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_modules(root: str | None = None) -> ModuleRegistry:
    """Walk modules/<pillar>/<module>/capability.json and validate each."""
    root = root or repo_root()
    modules_dir = os.path.join(root, "modules")
    registry = ModuleRegistry()
    if not os.path.isdir(modules_dir):
        return registry
    for pillar in sorted(os.listdir(modules_dir)):
        pillar_dir = os.path.join(modules_dir, pillar)
        if not os.path.isdir(pillar_dir) or pillar.startswith("."):
            continue
        for module in sorted(os.listdir(pillar_dir)):
            module_dir = os.path.join(pillar_dir, module)
            if not os.path.isdir(module_dir) or module.startswith("."):
                continue
            if module == "__pycache__":
                continue
            cap_path = os.path.join(module_dir, "capability.json")
            capability: dict | None = None
            errors: list[str] = []
            warnings: list[str] = []
            if os.path.isfile(cap_path):
                try:
                    with open(cap_path, "r", encoding="utf-8") as fh:
                        capability = json.load(fh)
                    errors, warnings = validate_capability(capability)
                except json.JSONDecodeError as exc:
                    errors.append(f"capability.json is not valid JSON: {exc}")
            else:
                errors.append("missing capability.json")
            name = (capability or {}).get("name", module)
            handler = os.path.join(module_dir, "handler.py")
            registry.modules[name] = ModuleInfo(
                name=name,
                pillar=pillar,
                directory=module_dir,
                capability=capability or {},
                errors=errors,
                warnings=warnings,
                handler_path=handler if os.path.isfile(handler) else None,
            )
    return registry
