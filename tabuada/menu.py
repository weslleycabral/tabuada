"""Menu interativo e assistente de configuração (tabuada sem argumentos)."""

from datetime import date, datetime

from . import render, report, storage
from .drill import Config, parse_tabelas, format_tabelas
from .session import show_report, train
from .term import hr, paint, sym


def ask(prompt, default=None, parse=lambda s: s):
    """Pergunta até receber algo válido. Enter aceita o padrão."""
    parts = [prompt] if prompt else []
    if default is not None:
        parts.append(paint("[%s]" % default, "d"))
    while True:
        raw = input("  %s: " % " ".join(parts)).strip()
        if not raw and default is not None:
            raw = str(default)
        try:
            return parse(raw)
        except ValueError as e:
            print("  " + paint(str(e), "r"))


def _int_between(lo, hi, example):
    def parse(raw):
        if raw.isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        raise ValueError("Digite um número entre %d e %d, por exemplo %s." % (lo, hi, example))
    return parse


def _yes_no(raw):
    raw = raw.lower()
    if raw in ("s", "sim", "y"):
        return True
    if raw in ("n", "nao", "não", "no"):
        return False
    raise ValueError("Responda s para sim ou n para não.")


def _choice(options):
    def parse(raw):
        if raw in options:
            return raw
        raise ValueError("Escolha uma das opções: %s." % ", ".join(options))
    return parse


def wizard():
    last = Config.from_dict(storage.load_config()["last"])
    print()
    print("  " + paint("Configurar treino", "b"))
    print()
    print("  Quais tabelas?  " + paint("todas %s 6,7,8 %s 2-9" % (sym("dot"), sym("dot")), "d"))
    tabelas = ask("", format_tabelas(last.tabelas), parse_tabelas)
    print()
    print("  Como você quer treinar?")
    print("    %s  Número de perguntas" % paint("1", "c"))
    print("    %s  Contra-relógio %s" % (paint("2", "c"), paint("(responde o máximo que der no tempo)", "d")))
    mode = ask("", "2" if last.tempo else "1", _choice(["1", "2"]))
    print()
    if mode == "1":
        n = ask("Quantas perguntas?", last.n or 20, _int_between(1, 200, "20"))
        tempo = None
    else:
        tempo = ask("Quantos segundos?", last.tempo or 120, _int_between(10, 3600, "120"))
        n = None
    foco = ask("Focar nos seus pontos fracos? %s" % paint("(s/n)", "d"), "s" if last.foco else "n", _yes_no)
    cfg = Config(tabelas=tabelas, n=n, tempo=tempo, foco=foco)
    print()
    print("  %s %s" % (paint(sym("ok"), "g"), cfg.describe()[0].upper() + cfg.describe()[1:]))
    print()
    print("  " + paint("Da próxima vez, pule o menu com:", "d"))
    print("    " + paint(cfg.command(), "c"))
    print()
    input("  Enter para começar ")
    return cfg


def _last_line(sessions):
    if not sessions:
        return "Nenhuma sessão ainda. Escolha 1 para começar."
    s = sessions[-1]
    nums = report.session_numbers(s)
    started = datetime.fromisoformat(s["started"])
    days = (date.today() - started.date()).days
    day = "hoje" if days == 0 else "ontem" if days == 1 else started.strftime("%d/%m")
    dot = sym("dot")
    return "Última sessão: %s às %s %s %d perguntas %s %d%% de acerto" % (
        day, started.strftime("%H:%M"), dot, nums["total"], dot, nums["pct"])


def history_screen():
    sessions = storage.load_history()
    rows = report.history_rows(sessions)
    print("\n".join(render.history_lines(rows, limit=10)))
    if not rows:
        input("\n  Enter para voltar ")
        return
    streak, _ = report.day_streaks(sessions)
    print()
    print(render.history_footer(rows, streak, 10))
    ids = {r["id"] for r in rows}
    while True:
        raw = input("\n  Número da sessão para ver o relatório, Enter para voltar: ").strip().lstrip("#")
        if not raw:
            return
        if raw.isdigit() and int(raw) in ids:
            show_report(report.build_for_id(sessions, int(raw)))
            return
        print("  " + paint("Não achei essa sessão. Use um número da coluna #.", "r"))


def _pause(lines):
    print("\n".join(lines))
    input("\n  Enter para voltar ao menu ")


def main_menu():
    while True:
        sessions = storage.load_history()
        last = Config.from_dict(storage.load_config()["last"])
        dot = sym("dot")
        print()
        print("  %s %s" % (paint("TABUADA", "b"), paint("%s treino até 12%s12" % (dot, sym("times")), "d")))
        print("  " + paint(_last_line(sessions), "d"))
        print()
        print("  O que você quer fazer?")
        print()
        items = [
            ("1", "Treinar (configurar)", ""),
            ("2", "Treinar com a última configuração", last.describe()),
            ("3", "Ver histórico", ""),
            ("4", "Estatísticas", ""),
            ("5", "Pontos fracos", ""),
            ("6", "Sair", ""),
        ]
        for k, label, hint in items:
            print("    %s  %s  %s" % (paint(k, "c"), label.ljust(33), paint(hint, "d")))
        print()
        print("  " + hr())
        print("  " + paint("Digite o número e Enter %s Ctrl+C sai a qualquer momento" % dot, "d"))
        print()
        choice = ask("Escolha", "1", _choice([i[0] for i in items]))
        if choice == "1":
            cfg = wizard()
            storage.update_config(last=cfg.to_dict())
            train(cfg)
        elif choice == "2":
            train(last)
        elif choice == "3":
            history_screen()
        elif choice == "4":
            _pause(render.stats_lines(report.stats(sessions)))
        elif choice == "5":
            _pause(render.weak_lines(report.weak_facts(sessions)))
        else:
            print("\n  Até a próxima!\n")
            return
