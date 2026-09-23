"""oauth_connect — OAuth2 flow scaffolding (RFC 6749).

build_auth_url: pure URL construction (no approval, no network).
exchange_code: real POST to the token endpoint; client_secret from
  ctx.auth_get(secret_provider); requires ctx.approval_request.
Tokens are returned in outputs and NEVER logged.
"""
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request


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
    if action not in ("build_auth_url", "exchange_code"):
        raise ModuleError("action must be build_auth_url or exchange_code")
    provider = inputs.get("provider")
    client_id = inputs.get("client_id")
    redirect_uri = inputs.get("redirect_uri")
    for key, val in (("provider", provider), ("client_id", client_id), ("redirect_uri", redirect_uri)):
        if not val or not isinstance(val, str):
            raise ModuleError(f"inputs.{key} is required (string)")

    if action == "build_auth_url":
        return _build_auth_url(inputs, ctx, provider, client_id, redirect_uri)
    return _exchange_code(inputs, ctx, provider, client_id, redirect_uri)


def _build_auth_url(inputs, ctx, provider, client_id, redirect_uri):
    authorization_endpoint = inputs.get("authorization_endpoint")
    if not authorization_endpoint or not isinstance(authorization_endpoint, str):
        raise ModuleError("inputs.authorization_endpoint is required (string)")
    parts = urllib.parse.urlsplit(authorization_endpoint)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ModuleError("authorization_endpoint must be an absolute http(s) URL")
    scope = inputs.get("scope", []) or []
    if not isinstance(scope, list):
        raise ModuleError("scope must be an array of strings")
    state = inputs.get("state") or secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scope),
        "state": state,
    }
    auth_url = authorization_endpoint + ("&" if "?" in authorization_endpoint else "?") + \
        urllib.parse.urlencode(params)
    ctx.log("oauth_connect", {"action": "build_auth_url", "provider": provider})
    ctx.bill(0.001, f"oauth_connect build_auth_url {provider}")
    return {"provider": provider, "auth_url": auth_url, "state": state}


def _exchange_code(inputs, ctx, provider, client_id, redirect_uri):
    token_endpoint = inputs.get("token_endpoint")
    code = inputs.get("code")
    secret_provider = inputs.get("secret_provider")
    if not token_endpoint or not isinstance(token_endpoint, str):
        raise ModuleError("inputs.token_endpoint is required (string)")
    parts = urllib.parse.urlsplit(token_endpoint)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ModuleError("token_endpoint must be an absolute http(s) URL")
    if not code or not isinstance(code, str):
        raise ModuleError("inputs.code is required (string)")
    if not secret_provider or not isinstance(secret_provider, str):
        raise ModuleError("inputs.secret_provider is required (string) for exchange_code")

    client_secret = ctx.auth_get(secret_provider)  # raises AuthMissing
    ctx.approval_request(f"oauth_connect: exchange authorization code for tokens ({provider})")

    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode("utf-8")
    req = urllib.request.Request(token_endpoint, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 method="POST")
    timeout = inputs.get("timeout_seconds", 15)
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 120):
        raise ModuleError("timeout_seconds must be a number in (0, 120]")
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            status = resp.status
            raw = resp.read(256 * 1024)
    except urllib.error.HTTPError as e:
        raise ModuleError(f"token exchange failed: HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ModuleError(f"token exchange failed: {e}")
    if not (200 <= status < 300):
        raise ModuleError(f"token exchange failed: HTTP {status}")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ModuleError("token endpoint returned non-JSON")
    if "access_token" not in data:
        raise ModuleError("token endpoint response missing access_token")

    # Log metadata only — never the tokens.
    ctx.log("oauth_connect", {"action": "exchange_code", "provider": provider,
                              "token_type": data.get("token_type"),
                              "refresh_token_issued": bool(data.get("refresh_token"))})
    ctx.bill(0.001, f"oauth_connect exchange_code {provider}")
    out = {
        "provider": provider,
        "access_token": data["access_token"],
        "token_type": data.get("token_type", "Bearer"),
        "expires_in": data.get("expires_in"),
        "refresh_token_issued": bool(data.get("refresh_token")),
    }
    # Deliberately exclude the refresh token value from outputs in v1 — the
    # calling agent re-exchanges via the provider's own refresh flow.
    return out
