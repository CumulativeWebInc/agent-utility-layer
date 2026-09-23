"""Permission declarations and enforcement for the Agent Utility Layer.

Permissions are lowercase "scope:action" strings (e.g. "email:send").
Grant styles:
  "*"            grants everything (god keys — issue sparingly)
  "email:*"      grants every email:* action
  "email:send"   grants exactly that action

`declare()` registers known permissions (documentation + contract
validation). `enforce()` runs at execute time: raises PermissionDenied
when the principal lacks any required permission.
"""

PERMISSION_REGISTRY: dict[str, str] = {}


class PermissionDenied(Exception):
    """Raised when a principal lacks a required permission."""


def declare(scope_action: str, description: str) -> None:
    scope_action = scope_action.strip().lower()
    if not scope_action or ":" not in scope_action:
        raise ValueError(f"bad permission shape (need scope:action): {scope_action!r}")
    PERMISSION_REGISTRY[scope_action] = description


def is_declared(scope_action: str) -> bool:
    return scope_action.strip().lower() in PERMISSION_REGISTRY


def _covers(grant: str, required: str) -> bool:
    grant = grant.strip().lower()
    required = required.strip().lower()
    if grant == "*":
        return True
    if grant == required:
        return True
    if grant.endswith(":*") and required.startswith(grant[:-1]):
        return True
    return False


def missing(granted: list[str], required: list[str]) -> list[str]:
    """Return required permissions not covered by any grant."""
    granted = granted or []
    out = []
    for req in required or []:
        if not any(_covers(g, req) for g in granted):
            out.append(req)
    return out


def enforce(principal: dict, required: list[str]) -> None:
    """Raise PermissionDenied if principal lacks any required permission."""
    unmet = missing(principal.get("permissions", []), required)
    if unmet:
        raise PermissionDenied(
            "agent '%s' lacks permission(s): %s"
            % (principal.get("name", principal.get("id", "?")), ", ".join(unmet))
        )


# ---- core permissions declared by the spine ---------------------------------
declare("system:execute", "Execute any registered capability")
declare("template:demo", "Run the contract reference module (simulated)")
declare("memory:sync", "Store/retrieve scoped user memory")
declare("tools:wrap", "Generate function specs from URL/OpenAPI")
declare("approval:request", "Push a human approval gate")
declare("ui:render", "Render JSON to widget/iframe HTML")
declare("kv:read", "Read scoped key-value memory")
declare("kv:write", "Write scoped key-value memory")
