"""Shared test fixtures for Crew F (business pillar) module tests.

Provides FakeCtx: a duck-typed stand-in for the spine runtime context
(ctx.auth_get / ctx.approval_request / ctx.memory_get / ctx.memory_set /
ctx.log / ctx.bill). Each handler defines ModuleError/AuthMissing/
ApprovalDenied; FakeCtx raises the handler's own exception classes so
tests exercise the real error types.
"""
import sys
import os


class _ExcFactory:
    """Builds exception classes compatible with a handler module."""

    def __init__(self, handler):
        self.ModuleError = getattr(handler, "ModuleError", Exception)
        self.AuthMissing = getattr(handler, "AuthMissing", self.ModuleError)
        self.ApprovalDenied = getattr(handler, "ApprovalDenied", self.ModuleError)


class FakeCtx:
    """Duck-typed spine ctx for tests. Fake providers are clearly labeled."""

    def __init__(self, handler=None, auth=None, approve="ok"):
        self.mem = {}
        self.auth = dict(auth or {})
        self.approve = approve  # "ok" | "deny"
        self.bills = []
        self.logs = []
        self.approvals_requested = []
        if handler is not None:
            exc = _ExcFactory(handler)
            self._AuthMissing = exc.AuthMissing
            self._ApprovalDenied = exc.ApprovalDenied
        else:
            self._AuthMissing = Exception
            self._ApprovalDenied = Exception

    def auth_get(self, provider):
        if provider not in self.auth:
            raise self._AuthMissing(
                "no credential configured for provider '%s' "
                "(DEMO: use FakeCtx(auth={'%s': 'demo-credential'}))" % (provider, provider)
            )
        return self.auth[provider]

    def approval_request(self, summary, timeout_seconds=300):
        self.approvals_requested.append({"summary": summary, "timeout": timeout_seconds})
        if self.approve == "deny":
            raise self._ApprovalDenied("human denied approval: %s" % summary)
        return "appr_test_%03d" % len(self.approvals_requested)

    def memory_get(self, key):
        return self.mem.get(key)

    def memory_set(self, key, value):
        self.mem[key] = value

    def log(self, event, data=None):
        self.logs.append((event, dict(data or {})))

    def bill(self, amount_usd, memo):
        self.bills.append({"amount_usd": amount_usd, "memo": memo})
