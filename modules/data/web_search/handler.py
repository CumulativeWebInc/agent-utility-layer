"""web_search — query builder + provider hook for web search. stdlib only.

Real provider calls via urllib. A search with no configured provider key
raises AuthMissing — results are NEVER fabricated.
"""

import json
import urllib.error
import urllib.parse
import urllib.request


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


_SETUP_HINTS = {
    "tavily": "Get a free API key at https://tavily.com (1,000 searches/mo free) "
              "and store it with the 'tavily' provider.",
    "serper": "Get an API key at https://serper.dev (2,500 searches/mo free) "
              "and store it with the 'serper' provider.",
    "brave": "Get an API key at https://brave.com/search/api/ "
             "and store it with the 'brave' provider.",
}

VALID_PROVIDERS = tuple(_SETUP_HINTS)


def _build_query(inputs):
    q = inputs["query"].strip()
    if not q:
        raise ModuleError("input 'query' must be a non-empty string")
    site = inputs.get("site")
    if site:
        q = f"site:{site} {q}"
    for term in inputs.get("exclude") or []:
        if term:
            q = f"{q} -{term}"
    return q


def _call_tavily(query, key, n, timeout):
    payload = json.dumps({
        "api_key": key,
        "query": query,
        "max_results": n,
        "include_answer": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        }
        for r in data.get("results", [])
    ]


def _call_serper(query, key, n, timeout):
    payload = json.dumps({"q": query, "num": n}).encode("utf-8")
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=payload,
        headers={"Content-Type": "application/json", "X-API-KEY": key},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("link", ""),
            "snippet": r.get("snippet", ""),
        }
        for r in data.get("organic", [])
    ]


def _call_brave(query, key, n, timeout):
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
        {"q": query, "count": n}
    )
    req = urllib.request.Request(
        url, headers={"X-Subscription-Token": key, "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("description", ""),
        }
        for r in (data.get("web") or {}).get("results", [])
    ]


_CALLERS = {"tavily": _call_tavily, "serper": _call_serper, "brave": _call_brave}


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. ctx is duck-typed per CONTRACT.md."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be a dict")
    provider = inputs.get("provider", "tavily")
    if provider not in _CALLERS:
        raise ModuleError(
            f"unknown provider '{provider}'. valid: {', '.join(VALID_PROVIDERS)}"
        )
    query = _build_query(inputs)
    n = inputs.get("max_results", 10)
    if not isinstance(n, int) or isinstance(n, bool) or not (1 <= n <= 50):
        raise ModuleError("input 'max_results' must be an integer 1..50")
    timeout = inputs.get("timeout_seconds", 20)
    if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 120:
        raise ModuleError("input 'timeout_seconds' must be a number in (0, 120]")

    # No key -> AuthMissing, never fabricated results.
    try:
        key = ctx.auth_get(provider)
    except AuthMissing:
        raise AuthMissing(
            f"No API key configured for search provider '{provider}'. "
            f"{_SETUP_HINTS[provider]}"
        )
    if not key or not str(key).strip():
        raise AuthMissing(
            f"Empty API key for search provider '{provider}'. "
            f"{_SETUP_HINTS[provider]}"
        )

    try:
        results = _CALLERS[provider](query, key, n, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        raise ModuleError(f"provider '{provider}' request failed: {e}")
    except (ValueError, KeyError) as e:
        raise ModuleError(f"provider '{provider}' returned an unparsable response: {e}")

    ctx.log("web_search", {"provider": provider, "query": query, "count": len(results)})
    return {
        "status": "ok",
        "query_used": query,
        "provider": provider,
        "results": results,
        "result_count": len(results),
    }
