"""Sessão de treino no terminal e relatório interativo."""

import sys
import time

from . import render, report, storage
from .drill import Drill, now, parse_answer
from .render import fact, secs
from .term import T, clear, hr, key, paint, sym


def _clock(seconds):
    m, s = divmod(max(0, int(seconds)), 60)
    return "%02d:%02d" % (m, s)


def _header(drill, elapsed):
    cfg = drill.config
    answers = drill.answers
    ok = sum(1 for a in answers if a["ok"])
    err = sum(1 for a in answers if not a["ok"] and not a["skipped"])
    skipped = sum(1 for a in answers if a["skipped"])
    if cfg.tempo:
        progress = "%s %s" % (paint("Pergunta", "d"), paint(str(len(answers) + 1), "b"))
        clock = "%s %s" % (paint("restam", "d"), _clock(cfg.tempo - elapsed))
    else:
        progress = "%s %s%s" % (paint("Pergunta", "d"), paint(str(len(answers) + 1), "b"),
                                paint("/%d" % cfg.n, "d"))
        clock = "%s %s" % (paint("tempo", "d"), _clock(elapsed))
    return "  %s      %s   %s   %s        %s" % (
        progress, paint("%s %d" % (sym("ok"), ok), "g"), paint("%s %d" % (sym("err"), err), "r"),
        paint("pulos %d" % skipped, "d"), clock)


def _bar(show):
    if show:
        return ["", "  " + hr(),
                "  %s sair e ver relatório   %s pular   %s ocultar atalhos" % (key("q"), key("p"), key("a"))]
    return ["", "  " + paint("[a] atalhos", "d")]


def _ask(prompt, show):
    """Mostra a pergunta com a barra de atalhos abaixo e lê a resposta."""
    bar = _bar(show)
    if T.ansi:
        sys.stdout.write("\n" + "\n".join(bar) + "\x1b[%dA\r" % len(bar))
        sys.stdout.flush()
        try:
            return input(prompt)
        finally:
            sys.stdout.write("\x1b[J")
            sys.stdout.flush()
    for line in bar[1:]:
        print(line)
    return input(prompt)


def play(config, save=True):
    """Roda uma sessão. Devolve (sessão, sessões anteriores) ou (None, None)."""
    cfg_store = storage.load_config()
    show = cfg_store["show_shortcuts"]
    history = storage.load_history()
    drill = Drill(config, history)
    started = now()
    t_start = time.monotonic()
    interrupted = False

    print()
    print("  %s %s" % (paint("Treino:", "b"), config.describe()))
    try:
        while not drill.done(time.monotonic() - t_start):
            a, b = drill.next_question()
            print()
            print(_header(drill, time.monotonic() - t_start))
            print()
            prompt = "        %s " % paint("%s =" % fact(a, b), "b")
            counted = 0.0
            while True:
                t0 = time.monotonic()
                kind, value = parse_answer(_ask(prompt, show))
                if kind == "toggle":
                    # o tempo gasto para mostrar/ocultar atalhos não conta
                    show = not show
                    storage.update_config(show_shortcuts=show)
                    if T.ansi:  # redesenha a mesma pergunta no lugar
                        sys.stdout.write("\x1b[1A\r\x1b[J")
                    continue
                counted += time.monotonic() - t0
                if kind == "invalid":
                    print("        " + paint("Digite só o resultado em números, ou uma das teclas de atalho.", "r"))
                    continue
                break
            if kind == "quit":
                interrupted = True
                break
            ms = counted * 1000
            ans = drill.record(a, b, value, ms, skipped=(kind == "skip"))
            _feedback(drill, ans)
    except (KeyboardInterrupt, EOFError):
        interrupted = True
        print()

    duration = (time.monotonic() - t_start) * 1000
    if not drill.answers:
        print("\n  Nenhuma resposta, nada foi salvo.")
        return None, None
    session = drill.to_session(started, duration, interrupted)
    if save:
        storage.add_session(session)
    else:
        session["id"] = None
    return session, history


def _feedback(drill, ans):
    took = secs(ans["ms"])
    right = ans["a"] * ans["b"]
    if ans["skipped"]:
        print("        %s   %s" % (paint("Pulou. %s = %d" % (fact(ans["a"], ans["b"]), right), "d"),
                                   paint(took, "d")))
        print("        " + paint("Essa conta volta daqui a pouco.", "d"))
    elif ans["ok"]:
        if drill.is_slow(ans["ms"]):
            print("        %s, mas demorou   %s" % (paint(sym("ok") + " Certo", "g"), paint(took, "y")))
        else:
            print("        %s   %s" % (paint(sym("ok") + " Certo", "g"), paint(took, "g")))
    else:
        print("        %s   %s" % (paint("%s %s = %d" % (sym("err"), fact(ans["a"], ans["b"]), right), "r"),
                                   paint(took, "d")))
        print("        " + paint("Essa conta volta daqui a pouco.", "d"))


def show_report(rep, interactive=True, opened=(), saved_id=None):
    opened = set(opened)
    if not interactive or not sys.stdin.isatty():
        for line in render.report_lines(rep, opened):
            print(line)
        return
    group_keys = {g[0] for g in render.GROUPS}
    first, redraw = True, True
    while True:
        if redraw:
            if not first:
                clear()
            lines = render.report_lines(rep, opened) + render.menu_lines(rep, opened)
            if first and saved_id:
                lines += ["", "  " + paint("Sessão salva no histórico (#%d)." % saved_id, "d")]
            print("\n".join(lines))
            first = False
        redraw = True
        try:
            choice = input("\n  Escolha: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if choice in ("", "enter", "sair", "q"):
            return
        if choice == "x":
            opened = set() if opened == group_keys else set(group_keys)
        elif choice in group_keys:
            opened ^= {choice}
        else:
            print("  " + paint("Use uma das teclas da lista, ou Enter para sair.", "r"))
            redraw = False


def train(config, save=True):
    session, before = play(config, save)
    if session is None:
        return
    rep = report.build(session, before)
    show_report(rep, saved_id=session.get("id"))
