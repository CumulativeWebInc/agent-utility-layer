"""cost_track: spend ledger per agent/capability (sqlite-backed). Feeds spine billing."""
import os
import sqlite3
import time
import uuid


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _store_dir(ctx):
    d = getattr(ctx, "store_dir", None) or os.environ.get("AUL_STORE_DIR") \
        or os.path.expanduser("~/.aul/data")
    os.makedirs(d, exist_ok=True)
    return d


def _db(ctx):
    path = os.path.join(_store_dir(ctx), "cost_track.sqlite3")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE IF NOT EXISTS costs ("
        " id TEXT PRIMARY KEY, agent TEXT NOT NULL, capability TEXT NOT NULL,"
        " amount_usd REAL NOT NULL, memo TEXT NOT NULL DEFAULT '', ts REAL NOT NULL)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_costs_agent ON costs (agent, ts)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_costs_cap ON costs (capability, ts)")
    return con


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    op = inputs.get("op")
    if op not in ("record", "totals", "by_capability", "by_agent"):
        raise ModuleError("op must be one of record|totals|by_capability|by_agent")
    con = _db(ctx)
    try:
        if op == "record":
            agent = inputs.get("agent")
            if not agent or not isinstance(agent, str):
                raise ModuleError("agent must be a non-empty string")
            capability = inputs.get("capability")
            if not capability or not isinstance(capability, str):
                raise ModuleError("capability must be a non-empty string")
            amount = inputs.get("amount_usd")
            if not isinstance(amount, (int, float)) or amount < 0:
                raise ModuleError("amount_usd must be a non-negative number")
            memo = inputs.get("memo", "")
            if not isinstance(memo, str):
                raise ModuleError("memo must be a string")
            cid = uuid.uuid4().hex
            ts = time.time()
            con.execute(
                "INSERT INTO costs (id, agent, capability, amount_usd, memo, ts)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (cid, agent, capability, float(amount), memo, ts))
            con.commit()
            return {"status": "ok", "id": cid, "ts": ts}
        since = inputs.get("since_ts")
        if since is not None and not isinstance(since, (int, float)):
            raise ModuleError("since_ts must be a number")
        agent = inputs.get("agent")
        filt = " WHERE 1=1"
        args = []
        if agent:
            filt += " AND agent=?"
            args.append(agent)
        if since is not None:
            filt += " AND ts >= ?"
            args.append(since)
        if op == "totals":
            row = con.execute(
                f"SELECT COALESCE(SUM(amount_usd),0), COUNT(*) FROM costs{filt}",
                args).fetchone()
            return {"status": "ok", "total_usd": round(row[0], 6), "count": row[1]}
        if op == "by_capability":
            rows = con.execute(
                f"SELECT capability, COALESCE(SUM(amount_usd),0), COUNT(*) FROM costs{filt}"
                " GROUP BY capability ORDER BY 2 DESC", args).fetchall()
            return {"status": "ok", "rows": [
                {"capability": r[0], "total_usd": round(r[1], 6), "count": r[2]}
                for r in rows]}
        rows = con.execute(
            f"SELECT agent, COALESCE(SUM(amount_usd),0), COUNT(*) FROM costs{filt}"
            " GROUP BY agent ORDER BY 2 DESC", args).fetchall()
        return {"status": "ok", "rows": [
            {"agent": r[0], "total_usd": round(r[1], 6), "count": r[2]}
            for r in rows]}
    finally:
        con.close()
