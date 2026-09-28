"""Sessão de treino no terminal e relatório interativo."""

import sys
import time

from . import render, report, storage
from .drill import INSTANT_KEYS, Drill, answer_complete, now, parse_answer
from .render import fact, secs
from .term import T, clear, hr, in_screen, key, keys, paint, read_key, screen, sym


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


def _ask(prompt, show, a, b, typed=""):
    """Mostra a pergunta com a barra de atalhos abaixo e lê a resposta.

    Devolve (tipo, valor) como parse_answer. Em "toggle", valor é o que já
    tinha sido digitado, para continuar de onde parou."""
    bar = _bar(show)
    if T.keys:
        sys.stdout.write("\n" + "\n".join(bar) + "\x1b[%dA\r" % len(bar) + prompt + typed)
        sys.stdout.flush()
        try:
            with keys():
                return _read_answer(a, b, typed)
        finally:
            sys.stdout.write("\n\x1b[J")  # como o input(): desce uma linha e apaga a barra
            sys.stdout.flush()
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
    return parse_answer(input(prompt))


def _read_answer(a, b, typed):
    """Tecla a tecla: a resposta vai sozinha quando está certa ou tem o máximo
    de dígitos da conta; q, p e a agem na hora; Enter manda respostas mais curtas."""
    while True:
        k = read_key()
        if k == "enter":
            if typed:
                return "num", int(typed)
        elif k == "backspace":
            if typed:
                typed = typed[:-1]
                sys.stdout.write("\b \b")
                sys.stdout.flush()
        elif len(k) == 1 and k in "0123456789":
            typed += k
            sys.stdout.write(k)
            sys.stdout.flush()
            if answer_complete(typed, a, b):
                return "num", int(typed)
        elif k.lower() in INSTANT_KEYS:
            kind = INSTANT_KEYS[k.lower()]
            return kind, (typed if kind == "toggle" else None)


def play(config, save=True):
    """Roda uma sessão. Devolve (sessão, sessões anteriores) ou (None, None)."""
    with screen():
        session, history = _play(config, save)
    if session is None:
        print("\n  Nenhuma resposta, nada foi salvo.")
    return session, history


def _play(config, save):
    cfg_store = storage.load_config()
    show = cfg_store["show_shortcuts"]
    history = storage.load_history()
    drill = Drill(config, history)
    started = now()
    t_start = time.monotonic()
    interrupted = False

    title = "  %s %s" % (paint("Treino:", "b"), config.describe())
    last_feedback = []
    if not T.ansi:
        print()
        print(title)
    try:
        while not drill.done(time.monotonic() - t_start):
            a, b = drill.next_question()
            if T.ansi:  # tela fixa: cada pergunta substitui a anterior
                clear()
                print(title)
                print("\n".join(last_feedback))
            else:
                print()
            print(_header(drill, time.monotonic() - t_start))
            print()
            prompt = "        %s " % paint("%s =" % fact(a, b), "b")
            counted = 0.0
            typed = ""
            while True:
                t0 = time.monotonic()
                kind, value = _ask(prompt, show, a, b, typed)
                if kind == "toggle":
                    # o tempo gasto para mostrar/ocultar atalhos não conta; tecla a
                    # tecla, o "a" é instantâneo e o tempo pensando até ali conta
                    if T.keys:
                        counted += time.monotonic() - t0
                        typed = value
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
            last_feedback = _feedback(drill, ans)
            if not T.ansi:
                print("\n".join(last_feedback))
    except (KeyboardInterrupt, EOFError):
        interrupted = True
        print()

    duration = (time.monotonic() - t_start) * 1000
    if not drill.answers:
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
    back = "        " + paint("Essa conta volta daqui a pouco.", "d")
    if ans["skipped"]:
        return ["        %s   %s" % (paint("Pulou. %s = %d" % (fact(ans["a"], ans["b"]), right), "d"),
                                    paint(took, "d")), back]
    if ans["ok"]:
        if drill.is_slow(ans["ms"]):
            return ["        %s, mas demorou   %s" % (paint(sym("ok") + " Certo", "g"), paint(took, "y")),
                    "        " + paint("Essa conta volta mais tarde, para ficar automática.", "d")]
        return ["        %s   %s" % (paint(sym("ok") + " Certo", "g"), paint(took, "g"))]
    return ["        %s   %s" % (paint("%s %s = %d" % (sym("err"), fact(ans["a"], ans["b"]), right), "r"),
                                 paint(took, "d")), back]


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
            if not first or in_screen():
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
        if in_screen():  # senão o menu redesenha por cima do aviso
            input("\n  Enter para voltar ao menu ")
        return
    rep = report.build(session, before)
    show_report(rep, saved_id=session.get("id"))
