"""permission_check — RBAC allow/deny evaluation.

Reads role assignments (written by role_assign) and grants from ctx.memory.
Default-deny. Wildcards supported in grant patterns and actions.
Read-only: never mutates anything.
"""
MEM_ASSIGN = "rbac:assignments"
MEM_GRANTS = "rbac:grants"

DEFAULT_GRANTS = {
    "admin": {"*": ["*"]},
    "operator": {
        "http:*": ["request", "send"],
        "net:*": ["dns"],
        "vault:*": ["read"],
        "identity:*": ["auth", "verify"],
    },
    "viewer": {
        "http:*": ["request"],
        "vault:*": ["read"],
    },
    "auditor": {
        "*": ["read"],
    },
}


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _match(pattern: str, value: str) -> bool:
    if pattern == "*":
        return True
    if pattern.endswith(":*"):
        return value == pattern[:-2] or value.startswith(pattern[:-1])
    if pattern.endswith("*"):
        return value.startswith(pattern[:-1])
    return pattern == value


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    resource = inputs.get("resource")
    principal = inputs.get("principal")
    for key, val in (("action", action), ("resource", resource), ("principal", principal)):
        if not val or not isinstance(val, str):
            raise ModuleError(f"inputs.{key} is required (string)")

    assignments = ctx.memory_get(MEM_ASSIGN) or {}
    grants = ctx.memory_get(MEM_GRANTS) or dict(DEFAULT_GRANTS)
    roles = assignments.get(principal, [])

    if not roles:
        ctx.log("permission_check", {"principal": principal, "allowed": False,
                                     "reason": "unknown principal"})
        return {"allowed": False, "rule": None,
                "reason": f"principal '{principal}' has no roles (default-deny)"}

    for role in roles:
        role_grants = grants.get(role, {})
        for pattern, actions in role_grants.items():
            if _match(pattern, resource) and (action in actions or "*" in actions):
                rule = f"{role}:{pattern}:{action}"
                ctx.log("permission_check", {"principal": principal, "allowed": True, "rule": rule})
                ctx.bill(0.001, f"permission_check {principal}")
                return {"allowed": True, "rule": rule,
                        "reason": f"granted by role '{role}'"}

    ctx.log("permission_check", {"principal": principal, "allowed": False,
                                 "reason": "no matching grant"})
    return {"allowed": False, "rule": None,
            "reason": f"no grant for action '{action}' on '{resource}' in roles {roles} (default-deny)"}
