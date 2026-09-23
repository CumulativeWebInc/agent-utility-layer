"""role_assign — assign / revoke RBAC roles for a principal.

Fixed v1 role vocabulary: admin, operator, viewer, auditor.
assign/revoke require ctx.approval_request (security-sensitive).
Writes the ctx.memory store consumed by permission_check.
"""
MEM_ASSIGN = "rbac:assignments"
ROLES = {"admin", "operator", "viewer", "auditor"}


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ("assign", "revoke", "list"):
        raise ModuleError("action must be assign, revoke, or list")
    assignments = ctx.memory_get(MEM_ASSIGN) or {}

    if action == "list":
        principal = inputs.get("principal")
        if principal:
            if not isinstance(principal, str):
                raise ModuleError("principal must be a string")
            return {"action": action, "principal": principal, "roles": assignments.get(principal, [])}
        return {"action": action, "roles": assignments}

    principal = inputs.get("principal")
    role = inputs.get("role")
    if not principal or not isinstance(principal, str):
        raise ModuleError("inputs.principal is required (string)")
    if not role or not isinstance(role, str):
        raise ModuleError("inputs.role is required (string)")
    if role not in ROLES:
        raise ModuleError(f"unknown role '{role}'; v1 roles: {sorted(ROLES)}")

    if action == "assign":
        extra = " — PRIVILEGED: grants full access" if role == "admin" else ""
        ctx.approval_request(f"role_assign: assign role '{role}' to '{principal}'{extra}")
        roles = assignments.get(principal, [])
        if role not in roles:
            roles.append(role)
        assignments[principal] = roles
        ctx.memory_set(MEM_ASSIGN, assignments)
        ctx.log("role_assign", {"action": "assign", "principal": principal, "role": role})
        ctx.bill(0.001, f"role_assign assign {principal}")
        return {"action": action, "principal": principal, "role": role,
                "ok": True, "roles": roles}

    # revoke
    ctx.approval_request(f"role_assign: revoke role '{role}' from '{principal}'")
    roles = [r for r in assignments.get(principal, []) if r != role]
    assignments[principal] = roles
    ctx.memory_set(MEM_ASSIGN, assignments)
    ctx.log("role_assign", {"action": "revoke", "principal": principal, "role": role})
    ctx.bill(0.001, f"role_assign revoke {principal}")
    return {"action": action, "principal": principal, "role": role,
            "ok": True, "roles": roles}
