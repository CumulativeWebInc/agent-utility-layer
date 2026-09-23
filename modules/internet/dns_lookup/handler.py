"""dns_lookup — real hostname resolution via stdlib socket.

Supports A / AAAA / CNAME only (stdlib limit). MX/TXT/etc. raise ModuleError
honestly instead of faking an answer.
"""
import socket


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass

_RECORDS = {"A": socket.AF_INET, "AAAA": socket.AF_INET6}


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    hostname = inputs.get("hostname")
    if not hostname or not isinstance(hostname, str):
        raise ModuleError("inputs.hostname is required (string)")
    record_type = str(inputs.get("record_type", "A")).upper()
    if record_type not in ("A", "AAAA", "CNAME"):
        raise ModuleError(
            "record_type must be A, AAAA, or CNAME in v1 (stdlib has no MX/TXT resolver)"
        )
    timeout = inputs.get("timeout_seconds", 5)
    if not isinstance(timeout, (int, float)) or not (0 < timeout <= 30):
        raise ModuleError("timeout_seconds must be a number in (0, 30]")

    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(float(timeout))
    try:
        if record_type == "CNAME":
            answers = _cname(hostname)
        else:
            answers = _addr(hostname, _RECORDS[record_type])
    except (socket.gaierror, UnicodeError) as e:
        raise ModuleError(f"DNS resolution failed for {hostname}: {e}")
    finally:
        socket.setdefaulttimeout(old_timeout)

    resolved = len(answers) > 0
    ctx.log("dns_lookup", {"hostname": hostname, "record_type": record_type, "resolved": resolved})
    ctx.bill(0.001, f"dns_lookup {record_type} {hostname}")
    return {
        "hostname": hostname,
        "record_type": record_type,
        "answers": answers,
        "resolved": resolved,
    }


def _addr(hostname, family):
    out = []
    for _fam, _type, _proto, _canon, sockaddr in socket.getaddrinfo(hostname, None, family, socket.SOCK_STREAM):
        ip = sockaddr[0]
        if ip not in out:
            out.append(ip)
    return out


def _cname(hostname):
    # stdlib has no direct CNAME query; getaddrinfo canonical name is the honest
    # stdlib-only approximation. If it equals the input, no CNAME indirection seen.
    # Try AF_INET first (some stacks lack AF_UNSPEC/IPv6); unresolvable -> [].
    for family in (socket.AF_INET, socket.AF_UNSPEC):
        try:
            info = socket.getaddrinfo(hostname, None, family, socket.SOCK_STREAM)
        except socket.gaierror:
            continue
        canon = info[0][3] if info else ""
        if canon and canon.rstrip(".") != hostname.rstrip("."):
            return [canon]
        return []
    return []
