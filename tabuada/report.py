"""Cálculos do relatório de sessão e das estatísticas gerais.

Tudo aqui devolve dicionários simples (serializáveis em JSON), usados
pelo terminal (render.py) e pelo modo web.
"""

from datetime import date, datetime, timedelta

from .drill import (ALL, AUTOMATIC, FAST_MS, HESITATED, SLOW_MS, THOUGHT, WRONG, Config, fact_key,
                    fact_stats, format_duration, median, memory, typical_grade)


def _ans(a):
    d = dict(a)
    d["right"] = a["a"] * a["b"]
    return d


def _pct(ok, total):
    return round(100 * ok / total) if total else 0


def _mean(values):
    return sum(values) / len(values) if values else 0


def session_numbers(session):
    answers = session.get("answers", [])
    ok = sum(1 for a in answers if a["ok"])
    ms = [a["ms"] for a in answers if not a.get("skipped")]
    return {"total": len(answers), "ok": ok, "pct": _pct(ok, len(answers)),
            "mean": _mean(ms)}


def best_streak(answers):
    best = cur = 0
    for a in answers:
        cur = cur + 1 if a["ok"] else 0
        best = max(best, cur)
    return best


def summary(session, before):
    ans = session["answers"]
    nums = session_numbers(session)
    prev = session_numbers(before[-1]) if before else None
    return {
        "total": nums["total"],
        "ok": nums["ok"],
        "errors": sum(1 for a in ans if not a["ok"] and not a.get("skipped")),
        "skipped": sum(1 for a in ans if a.get("skipped")),
        "pct": nums["pct"],
        "duration_ms": session.get("duration_ms", 0),
        "delta_pct": (nums["pct"] - prev["pct"]) if prev else None,
    }


def time_group(session, before):
    timed = [a for a in session["answers"] if not a.get("skipped")]
    ms = [a["ms"] for a in timed]
    med = median(ms)
    prev = session_numbers(before[-1]) if before else None
    mean = _mean(ms)
    slow_ok = sorted((a for a in timed if a["ok"] and a["ms"] > SLOW_MS),
                     key=lambda a: -a["ms"])
    return {
        "mean": mean,
        "median": med,
        "fastest": _ans(min(timed, key=lambda a: a["ms"])) if timed else None,
        "slowest": _ans(max(timed, key=lambda a: a["ms"])) if timed else None,
        "top": [_ans(a) for a in sorted(session["answers"], key=lambda a: -a["ms"])[:5]],
        "slow_threshold": SLOW_MS,
        "slow_ok": [_ans(a) for a in slow_ok],
        "delta_mean": (mean - prev["mean"]) if prev and prev["mean"] and ms else None,
    }


def errors_group(session):
    return [_ans(a) for a in session["answers"] if not a["ok"]]


def tables_group(session):
    cfg = Config.from_dict(session.get("config"))
    rows = []
    for t in cfg.tabelas:
        items = [a for a in session["answers"] if a["a"] == t]
        if not items:
            continue
        ms = [a["ms"] for a in items if not a.get("skipped")]
        rows.append({"t": t, "n": len(items),
                     "pct": _pct(sum(1 for a in items if a["ok"]), len(items)),
                     "mean": _mean(ms), "worst": False})
    if len(rows) > 1:
        worst = min(rows, key=lambda r: (r["pct"], -r["mean"]))
        if worst["pct"] < 100 or worst["mean"] > 1.3 * _mean([r["mean"] for r in rows]):
            worst["worst"] = True
    return rows


def compare_group(session, before):
    nums = session_numbers(session)
    prev = session_numbers(before[-1]) if before else None
    if before:
        all_before = [session_numbers(s) for s in before]
        avg = {"pct": _mean([x["pct"] for x in all_before]),
               "mean": _mean([x["mean"] for x in all_before if x["mean"]])}
    else:
        avg = None
    streak = best_streak(session["answers"])
    record = max([best_streak(s["answers"]) for s in before] or [0])
    return {
        "pct": nums["pct"],
        "mean": nums["mean"],
        "prev": prev,
        "avg": avg,
        "best_streak": streak,
        "record_streak": record,
        "new_record": bool(before) and streak > record,
    }


def recommendation(session, tables):
    cfg = Config.from_dict(session.get("config"))
    ans = session["answers"]
    weak = []
    for a in sorted(ans, key=lambda a: (a["ok"], -a["ms"])):
        key = fact_key(a["a"], a["b"])
        slow = a["ms"] > SLOW_MS
        if (not a["ok"] or slow) and key not in [fact_key(*w) for w in weak]:
            weak.append((a["a"], a["b"]))
    worst = next((r for r in tables if r["worst"]), None)
    if worst:
        target = [worst["t"]]
        text = "treine a do %d" % worst["t"]
    elif weak:
        target = sorted({w[0] for w in weak[:3]})
        text = "treine as contas que pegaram"
    else:
        tempo = Config(tabelas=cfg.tabelas, n=None, tempo=120)
        return {"text": "tudo certo e rápido, tente o contra-relógio",
                "facts": [], "command": tempo.command()}
    facts = [w for w in weak if w[0] in target or w[1] in target][:2] or weak[:2]
    cmd = Config(tabelas=target, n=20, foco=True)
    return {"text": text, "facts": facts, "command": cmd.command()}


def build(session, before):
    """Relatório completo de uma sessão; `before` = sessões anteriores a ela."""
    cfg = Config.from_dict(session.get("config"))
    tables = tables_group(session)
    return {
        "id": session.get("id"),
        "started": session.get("started"),
        "config_desc": cfg.describe(),
        "interrupted": session.get("interrupted", False),
        "summary": summary(session, before),
        "recommendation": recommendation(session, tables),
        "time": time_group(session, before),
        "errors": errors_group(session),
        "tables": tables,
        "compare": compare_group(session, before),
    }


def build_for_id(sessions, session_id=None):
    if not sessions:
        return None
    if session_id is None:
        idx = len(sessions) - 1
    else:
        idx = next((i for i, s in enumerate(sessions) if s.get("id") == session_id), None)
        if idx is None:
            return None
    return build(sessions[idx], sessions[:idx])


# ---------- estatísticas gerais ----------

def history_rows(sessions):
    rows = []
    for s in reversed(sessions):
        cfg = Config.from_dict(s.get("config"))
        nums = session_numbers(s)
        rows.append({
            "id": s.get("id"), "started": s.get("started"),
            "tabelas": _tabelas_short(cfg.tabelas), "mode": cfg.mode_desc(),
            "total": nums["total"], "pct": nums["pct"], "mean": nums["mean"],
            "interrupted": s.get("interrupted", False),
        })
    return rows


def _tabelas_short(tabelas):
    from .drill import format_tabelas
    return format_tabelas(tabelas, "–").replace(",", ", ")


def _day(s):
    return datetime.fromisoformat(s["started"]).date()


def day_streaks(sessions, today=None):
    days = sorted({_day(s) for s in sessions})
    if not days:
        return 0, 0
    today = today or date.today()
    record, run = 1, 1
    for prev, cur in zip(days, days[1:]):
        run = run + 1 if cur - prev == timedelta(days=1) else 1
        record = max(record, run)
    current = 0
    if today - days[-1] <= timedelta(days=1):
        current = 1
        for prev, cur in zip(reversed(days[:-1]), reversed(days[1:])):
            if cur - prev != timedelta(days=1):
                break
            current += 1
    return current, record


# Nota típica -> nível de cor da célula (1 ótimo ... 4 ruim, 0 nunca vista)
_GRADE_LEVEL = {AUTOMATIC: 1, HESITATED: 2, THOUGHT: 3, WRONG: 4}


def level(st, mem, mode):
    """Nível de cor da célula: 0 nunca vista, 1 ótimo ... 4 ruim."""
    if not st or not st["seen"]:
        return 0
    if mode == "tempo":
        if not st["ms"]:
            return 4
        avg = _mean(st["ms"])
        return 1 if avg <= FAST_MS else 2 if avg <= SLOW_MS else 3 if avg <= 2 * SLOW_MS else 4
    return _GRADE_LEVEL[typical_grade(mem["grades"])]


def stats(sessions, mode="dominio", today=None):
    fs = fact_stats(sessions)
    mem = memory(sessions)
    grid = [[level(fs.get(fact_key(a, b)), mem.get(fact_key(a, b)), mode) for b in ALL] for a in ALL]
    recent = sessions[-12:]
    per_table = {}
    for s in sessions:
        for a in s["answers"]:
            for t in {a["a"], a["b"]}:
                pt = per_table.setdefault(t, [0, 0])
                pt[0] += 1
                pt[1] += 1 if a["ok"] else 0
    tables = [{"t": t, "pct": _pct(v[1], v[0])} for t, v in sorted(per_table.items())]
    current, record = day_streaks(sessions, today)
    return {
        "mode": mode,
        "sessions": len(sessions),
        "answers": sum(len(s["answers"]) for s in sessions),
        "since": sessions[0]["started"] if sessions else None,
        "grid": grid,
        "trend_pct": [session_numbers(s)["pct"] for s in recent],
        "trend_mean": [session_numbers(s)["mean"] for s in recent],
        "best_table": max(tables, key=lambda r: r["pct"]) if tables else None,
        "worst_table": min(tables, key=lambda r: r["pct"]) if tables else None,
        "streak": current,
        "streak_record": record,
        "total_ms": sum(s.get("duration_ms", 0) for s in sessions),
    }


_REASON = {WRONG: "erra", THOUGHT: "pensa", HESITATED: "hesita"}


def weak_facts(sessions, n=10, at=None):
    """Contas que ainda não são automáticas, da pior para a melhor.

    O motivo vem da nota típica das 3 últimas respostas: erra, pensa (>4 s)
    ou hesita (2–4 s). A revisão segue a repetição espaçada de drill.memory."""
    fs = fact_stats(sessions)
    mem = memory(sessions)
    at = at or datetime.now()
    rows = []
    for key, m in mem.items():
        g = typical_grade(m["grades"])
        if g == AUTOMATIC:
            continue
        st = fs[key]
        recent_ms = st["ms"][-3:]
        rows.append({"a": key[0], "b": key[1], "seen": st["seen"], "errors": st["errors"],
                     "ms": median(recent_ms) if recent_ms else None,
                     "grade": g, "reasons": [_REASON[g]], "box": m["box"],
                     "due": m["due_at"] <= at, "review_in": max(0, (m["due_at"].date() - at.date()).days)})
    rows.sort(key=lambda r: (r["grade"], -(r["ms"] or 0)))
    return {"fast_ms": FAST_MS, "slow_ms": SLOW_MS, "rows": rows[:n]}


def duration_text(ms):
    return format_duration(round(ms / 1000))
