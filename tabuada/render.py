"""Desenha relatórios e estatísticas como texto de terminal."""

from datetime import datetime

from .report import duration_text
from .term import T, hr, key, paint, sym

GROUPS = [
    ("t", "time", "Tempo", "velocidade, mais demoradas, contas lentas"),
    ("e", "errors", "Erros e pulos", None),
    ("d", "tables", "Por tabela", "acerto e tempo de cada tabela"),
    ("c", "compare", "Comparação", "sessão anterior, sua média, recordes"),
]


def secs(ms, width=0):
    text = ("%.1f s" % (ms / 1000)).replace(".", ",")
    return text.rjust(width)


def fact(a, b):
    return "%d %s %d" % (a, sym("times"), b)


def signed(value, fmt, good_when_negative=False, suffix=""):
    if value is None:
        return None
    text = (fmt % abs(value)).replace(".", ",")
    if round(abs(value), 1) == 0:
        return paint("igual", "d")
    sign = "+" if value > 0 else sym("minus")
    good = (value < 0) if good_when_negative else (value > 0)
    return paint(sign + text + suffix, "g" if good else "r")


def when(iso):
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")


# ---------- relatório de sessão ----------

def summary_lines(rep):
    s = rep["summary"]
    dot = sym("dot")
    title = "%s %s" % (paint("RELATÓRIO", "b"),
                       paint("%s %s %s %s" % (dot, when(rep["started"]), dot, rep["config_desc"]), "d"))
    if rep["interrupted"]:
        title += paint(" %s interrompida" % dot, "d")
    line1 = "    Acertos %s    Erros %s    Pulos %s     %s de acerto" % (
        paint(str(s["ok"]), "g", "b"), paint(str(s["errors"]), "r", "b"),
        paint(str(s["skipped"]), "b"), paint("%d%%" % s["pct"], "b"))
    line2 = "    Duração %s" % paint(duration_text(s["duration_ms"]), "b")
    if s["delta_pct"] is not None:
        line2 += "     %s %s" % (signed(s["delta_pct"], "%d", suffix=" pp"),
                                  paint("em relação à sessão anterior", "d"))
    rec = rep["recommendation"]
    text = rec["text"]
    if rec["facts"]:
        text += ", com foco em " + " e ".join(fact(a, b) for a, b in rec["facts"])
    return ["", "  " + title, "", line1, line2, "",
            "    Próximo passo: " + text, "    " + paint(rec["command"], "c")]


def _group_header(name):
    bar = sym("hr")
    label = "%s%s %s " % (bar, bar, name)
    return "  " + paint(label + bar * max(4, 56 - len(label)), "c")


def time_lines(rep):
    t = rep["time"]
    lines = ["", _group_header("Tempo"), ""]
    if not t["fastest"]:
        return lines + ["    Nenhuma resposta cronometrada."]
    lines += [
        "    Média %s    Mediana %s" % (paint(secs(t["mean"]), "b"), paint(secs(t["median"]), "b")),
        "    Mais rápida %s  %s" % (paint(secs(t["fastest"]["ms"], 7), "g"),
                                   paint(fact(t["fastest"]["a"], t["fastest"]["b"]), "d")),
        "    Mais lenta  %s  %s" % (paint(secs(t["slowest"]["ms"], 7), "y"),
                                   paint(fact(t["slowest"]["a"], t["slowest"]["b"]), "d")),
        "", "    " + paint("Respostas mais demoradas", "c"),
    ]
    thr = t["slow_threshold"]
    for a in t["top"]:
        f = fact(a["a"], a["b"])
        if a["skipped"]:
            left = f.ljust(13) + paint("pulou".ljust(11), "d")
        else:
            mark = paint(sym("ok"), "g") if a["ok"] else paint(sym("err"), "r")
            left = ("%s = %d" % (f, a["resp"])).ljust(13) + mark + " " * 10
        took = secs(a["ms"], 6)
        lines.append("    " + left + (paint(took, "y") if thr and a["ms"] > thr else took))
    lines += ["", "    %s %s" % (paint("Sabe, mas ainda devagar", "c"),
                                  paint("(acertou em mais de %s = 2%s a mediana)" % (secs(thr), sym("times")), "d"))]
    if t["slow_ok"]:
        items = ["%s  %s" % (fact(a["a"], a["b"]), paint(secs(a["ms"]), "y")) for a in t["slow_ok"][:6]]
        for i in range(0, len(items), 3):
            lines.append("    " + "     ".join(items[i:i + 3]))
    else:
        lines.append("    " + paint("Nenhuma. Os acertos saíram no seu ritmo normal.", "d"))
    if t["delta_mean"] is not None:
        lines += ["", "    Tempo médio %s %s" % (signed(t["delta_mean"] / 1000, "%.1f", True, " s"),
                                                  paint("em relação à sessão anterior", "d"))]
    return lines


def errors_lines(rep):
    lines = ["", _group_header("Erros e pulos"), ""]
    if not rep["errors"]:
        return lines + ["    " + paint("Nenhum erro nesta sessão.", "g")]
    for a in rep["errors"]:
        f = fact(a["a"], a["b"])
        if a["skipped"]:
            lines.append("    %s%s  %s   %s" % (f.ljust(13), paint("pulou", "d"),
                                                paint(str(a["right"]).rjust(3), "g"), secs(a["ms"], 6)))
        else:
            lines.append("    %s = %s   certo: %s   %s" % (
                f, paint(str(a["resp"]).rjust(3), "r"), paint(str(a["right"]).rjust(3), "g"),
                secs(a["ms"], 6)))
    return lines


def tables_lines(rep):
    lines = ["", _group_header("Por tabela"), "",
             "    " + paint("tabela".ljust(22) + "acerto   tempo médio", "d")]
    for r in rep["tables"]:
        filled = round(16 * r["pct"] / 100)
        color = "y" if r["worst"] else "g"
        bar = paint(sym("full") * filled, color) + paint(sym("light") * (16 - filled), "d")
        line = "    %s   %s   %s      %s" % (str(r["t"]).rjust(2), bar, ("%d%%" % r["pct"]).rjust(4),
                                           secs(r["mean"], 6))
        if r["worst"]:
            line += "   " + paint(sym("arrow") + " mais fraca", "y")
        lines.append(line)
    return lines


def compare_lines(rep):
    c = rep["compare"]
    lines = ["", _group_header("Comparação"), ""]
    if not c["prev"]:
        lines.append("    " + paint("Primeira sessão. A comparação aparece a partir da próxima.", "d"))
    else:
        for label, ref in (("Sessão anterior", c["prev"]), ("Sua média", c["avg"])):
            dp = signed(c["pct"] - ref["pct"], "%d", suffix=" pp")
            dm = signed((c["mean"] - ref["mean"]) / 1000, "%.1f", True, " s") if ref["mean"] else "-"
            lines.append("    %s acerto %s %s   tempo médio %s" % (
                label.ljust(17), dp, paint("(%d%% %s %d%%)" % (round(ref["pct"]), sym("to"), c["pct"]), "d"), dm))
    lines += ["", "    Melhor sequência: %s acertos seguidos %s" % (
        paint(str(c["best_streak"]), "b"),
        paint("novo recorde!", "g") if c["new_record"]
        else paint("(seu recorde: %d)" % c["record_streak"], "d") if c["prev"] else "")]
    return lines


GROUP_RENDER = {"t": time_lines, "e": errors_lines, "d": tables_lines, "c": compare_lines}


def menu_lines(rep, opened):
    n_err = len(rep["errors"])
    lines = ["", "  " + hr()]
    if not opened:
        lines.append("  Quer ver mais?")
    for k, _, label, hint in GROUPS:
        if k in opened:
            lines.append("    %s Ocultar %s" % (key(k), label[0].lower() + label[1:]))
            continue
        if k == "e":
            hint = "%d %s, com a resposta certa" % (n_err, "conta" if n_err == 1 else "contas") \
                if n_err else "nenhum nesta sessão"
        lines.append("    %s %s %s" % (key(k), label.ljust(16), paint(hint, "d")))
    all_open = len(opened) == len(GROUPS)
    lines.append("    %s %s" % (key("x"), "Ocultar tudo" if all_open else "Mostrar tudo"))
    lines.append("    %s Sair" % key("Enter"))
    return lines


def report_lines(rep, opened):
    lines = summary_lines(rep)
    for k, *_ in GROUPS:
        if k in opened:
            lines += GROUP_RENDER[k](rep)
    return lines


# ---------- histórico, estatísticas, pontos fracos ----------

def history_lines(rows, limit=10):
    lines = ["", "  " + paint("HISTÓRICO", "b"), ""]
    if not rows:
        return lines + ["  Nenhuma sessão ainda. Comece com: " + paint("tabuada treinar", "c")]
    lines.append("  " + paint("  #  Data          Tabelas   Modo            Perg.  Acerto  Tempo médio", "d"))
    shown = rows if not limit else rows[:limit]
    for r in shown:
        pct_color = "g" if r["pct"] >= 80 else "y" if r["pct"] >= 60 else "r"
        started = datetime.fromisoformat(r["started"]).strftime("%d/%m %H:%M")
        line = "  %s  %s  %s %s %s  %s  %s" % (
            str(r["id"]).rjust(3), started.ljust(12), r["tabelas"][:9].ljust(9),
            r["mode"].ljust(15), str(r["total"]).rjust(5),
            paint(("%d%%" % r["pct"]).rjust(6), pct_color), secs(r["mean"], 11))
        if r["interrupted"]:
            line += "  " + paint("interrompida", "d")
        lines.append(line)
    return lines


def history_footer(rows, streak, limit):
    parts = ["%d %s" % (len(rows), "sessão" if len(rows) == 1 else "sessões")]
    if streak > 1:
        parts.append("%d dias seguidos treinando" % streak)
    if limit and len(rows) > limit:
        parts.append("mostrando %d de %d" % (limit, len(rows)))
    return "  " + paint((" %s " % sym("dot")).join(parts), "d")


def sparkline(values):
    chars = sym("spark")
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    return "".join(chars[round((v - lo) / span * (len(chars) - 1))] for v in values)


def stats_lines(st):
    dot = sym("dot")
    lines = [""]
    if not st["sessions"]:
        return lines + ["  Nenhuma sessão ainda. Comece com: " + paint("tabuada treinar", "c")]
    since = datetime.fromisoformat(st["since"]).strftime("%d/%m")
    lines.append("  %s %s" % (paint("ESTATÍSTICAS", "b"), paint(
        "%s %d sessões %s %d respostas %s desde %s" % (dot, st["sessions"], dot, st["answers"], dot, since), "d")))
    lines.append("")
    if T.color:
        cells = [sym("full") * 2] * 5
    else:  # sem cor, o nível aparece no próprio caractere
        cells = ["··", "██", "▓▓", "▒▒", "░░"] if T.unicode else ["  ", "##", "++", "--", ".."]
    cell = lambda lv: paint(cells[lv], "l%d" % lv)
    if st["mode"] == "tempo":
        lines.append("  " + paint("Tempo médio por conta", "c"))
        legend = [("l1", "<3 s"), ("l2", "3-5 s"), ("l3", "5-8 s"), ("l4", ">8 s"), ("l0", "nunca vista")]
    else:
        lines.append("  " + paint("Acerto por conta", "c"))
        legend = [("l1", ">=95%"), ("l2", "80-94%"), ("l3", "60-79%"), ("l4", "<60%"), ("l0", "nunca vista")]
    lines.append("  " + "  ".join("%s %s" % (cell(int(c[1])), t) for c, t in legend))
    lines.append("")
    lines.append(paint("     " + "".join(str(j).rjust(2) + " " for j in range(1, 13)), "d"))
    for i, row in enumerate(st["grid"], start=1):
        lines.append(paint(str(i).rjust(4), "d") + " " + " ".join(cell(lv) for lv in row))
    lines += ["", "  %s %s" % (paint("Evolução", "c"), paint("(últimas %d sessões)" % len(st["trend_pct"]), "d"))]
    tp, tm = st["trend_pct"], [m for m in st["trend_mean"] if m]
    lines.append("    Acerto        %s   %d%% %s %s" % (
        paint(sparkline(tp), "g"), tp[0], sym("to"), paint("%d%%" % tp[-1], "b")))
    if tm:
        lines.append("    Tempo médio   %s   %s %s %s" % (
            paint(sparkline(tm), "y"), secs(tm[0]), sym("to"), paint(secs(tm[-1]), "b")))
    lines.append("")
    if st["best_table"]:
        lines.append("  %s     %s %d %s   %s %d %s" % (
            paint("Por tabela", "c"), paint("melhor", "d"), st["best_table"]["t"],
            paint("(%d%%)" % st["best_table"]["pct"], "g"), paint("pior", "d"),
            st["worst_table"]["t"], paint("(%d%%)" % st["worst_table"]["pct"], "r")))
    lines.append("  %s     %d %s %s" % (
        paint("Constância", "c"), st["streak"], "dia seguido" if st["streak"] == 1 else "dias seguidos",
        paint("%s recorde %d" % (dot, st["streak_record"]), "d")))
    lines.append("  %s    %s treinando" % (paint("Tempo total", "c"), duration_text(st["total_ms"])))
    lines.append("")
    other = "tabuada stats" if st["mode"] == "tempo" else "tabuada stats --tempo"
    what = "a grade por acerto" if st["mode"] == "tempo" else "a grade por tempo médio"
    lines.append("  " + paint("%s  mostra %s" % (other, what), "d"))
    return lines


def weak_lines(wk):
    lines = ["", "  %s %s" % (paint("PONTOS FRACOS", "b"), paint("%s todas as sessões" % sym("dot"), "d")), ""]
    if not wk["rows"]:
        return lines + ["  Nenhum ponto fraco por enquanto. Treine mais algumas sessões para aparecer aqui."]
    lines.append("  " + paint("      Conta     Vistas  Erros  Tempo médio  Motivo", "d"))
    for i, r in enumerate(wk["rows"], start=1):
        demora = "demora" in r["reasons"]
        reason = " e ".join(paint(x, "r" if x == "erra" else "y") for x in r["reasons"])
        lines.append("   %s   %s %s  %s  %s    %s" % (
            str(i).rjust(2), fact(r["a"], r["b"]).ljust(9), str(r["seen"]).rjust(6),
            paint(str(r["errors"]).rjust(5), "r") if r["errors"] else str(r["errors"]).rjust(5),
            paint(secs(r["mean"], 11), "y") if demora else secs(r["mean"], 11), reason))
    lines += ["", "  " + paint('"demora" = tempo médio acima de 2%s a sua mediana geral (%s)' % (sym("times"), secs(wk["median"])), "d"),
              "", "  Treinar focando nessas contas:", "    " + paint("tabuada treinar --foco", "c")]
    return lines
