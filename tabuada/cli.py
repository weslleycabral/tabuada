"""Ponto de entrada: `tabuada` (menu) ou `tabuada <comando> [opções]`."""

import argparse
import sys

from . import __version__, render, report, storage, term
from .drill import Config, parse_tabelas

HELP_COMMANDS = """comandos:
  treinar      começa uma sessão de treino
  relatorio    mostra o relatório da última sessão
  historico    lista as sessões anteriores
  stats        mostra sua evolução e a grade 12×12
  fracos       mostra as contas com mais erros ou mais lentas
  reset        apaga o histórico (pede confirmação)

Cada comando tem a própria ajuda, por exemplo: tabuada treinar --help

"""

HELP_SESSION = """durante a sessão:
  q   sai e mostra o relatório       p       pula a pergunta
  a   mostra ou oculta os atalhos    Ctrl+C  igual a q
  as teclas agem sem Enter, e a resposta vai sozinha quando está certa
  ou já tem o máximo de dígitos da conta (2 em 9×9); Enter manda antes

exemplos:
  tabuada treinar -n 30 --tabelas 7,8
  tabuada treinar --tempo 120 --foco
  tabuada relatorio --sessao 11"""


def _tabelas(text):
    try:
        return parse_tabelas(text)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def _factor(text):
    if text.isdigit() and 1 <= int(text) <= 12:
        return int(text)
    raise argparse.ArgumentTypeError("use um número de 1 a 12")


def _positive(text):
    if text.isdigit() and int(text) > 0:
        return int(text)
    raise argparse.ArgumentTypeError("use um número maior que zero")


class _Formatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=30)

    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, prefix or "uso: ")


def _parser(sub, name, **kw):
    p = sub.add_parser(name, prog="tabuada " + name, add_help=False, formatter_class=_Formatter, **kw)
    _add_help(p)
    p._optionals.title = "opções"
    return p


def _add_help(p):
    p.add_argument("-h", "--help", action="help", help="mostra esta ajuda e sai")


def _add_general(p, suppress):
    kw = {"default": argparse.SUPPRESS} if suppress else {"default": False}
    p.add_argument("--web", action="store_true", help="abre a mesma interface no navegador", **kw)
    p.add_argument("--ascii", action="store_true", help="usa só caracteres simples (terminais antigos)", **kw)
    p.add_argument("--sem-cor", action="store_true", dest="sem_cor",
                   help="desliga as cores (também respeita NO_COLOR)", **kw)


def build_parser():
    p = argparse.ArgumentParser(
        prog="tabuada", usage="tabuada [comando] [opções]", description="Treino de tabuada até 12×12. Sem comando, abre o menu interativo.",
        epilog=HELP_COMMANDS + HELP_SESSION, formatter_class=_Formatter, add_help=False)
    p._optionals.title = "opções"
    _add_help(p)
    p.add_argument("--version", action="version", version="tabuada " + __version__,
                   help="mostra a versão e sai")
    _add_general(p, suppress=False)
    sub = p.add_subparsers(dest="command", metavar="[comando]", help=argparse.SUPPRESS)

    t = _parser(sub, "treinar", help="começa uma sessão de treino",
                description="Começa uma sessão. Sem opções, repete a última configuração.",
                epilog=HELP_SESSION)
    mode = t.add_mutually_exclusive_group()
    mode.add_argument("-n", type=_positive, metavar="N", help="número de perguntas (padrão: 20)")
    mode.add_argument("--tempo", type=_positive, metavar="S", help="contra-relógio: duração total em segundos")
    t.add_argument("--tabelas", type=_tabelas, metavar="LISTA", help="ex.: 6,7,8 ou 2-9 (padrão: todas)")
    t.add_argument("--min", type=_factor, metavar="N", help="menor segundo fator (padrão: 1)")
    t.add_argument("--max", type=_factor, metavar="N", help="maior segundo fator (padrão: 12)")
    t.add_argument("--foco", action="store_true", help="pergunta mais os seus pontos fracos")
    t.add_argument("--sem-historico", action="store_true", dest="sem_historico",
                   help="não salva esta sessão")
    _add_general(t, suppress=True)

    r = _parser(sub, "relatorio", help="mostra o relatório da última sessão")
    r.add_argument("--sessao", type=_positive, metavar="ID", help="relatório de uma sessão específica")
    r.add_argument("--tempo", action="store_true", help="abre o grupo de tempo")
    r.add_argument("--erros", action="store_true", help="abre o grupo de erros e pulos")
    r.add_argument("--tabelas", action="store_true", help="abre o grupo por tabela")
    r.add_argument("--comparacao", action="store_true", help="abre o grupo de comparação")
    r.add_argument("--completo", action="store_true", help="mostra todos os grupos")
    _add_general(r, suppress=True)

    h = _parser(sub, "historico", help="lista as sessões anteriores")
    h.add_argument("--todas", action="store_true", help="lista todas as sessões (padrão: últimas 10)")
    _add_general(h, suppress=True)

    s = _parser(sub, "stats", help="mostra sua evolução e a grade 12×12")
    s.add_argument("--tempo", action="store_true", help="colore a grade por tempo médio (padrão: domínio, que junta acerto e tempo)")
    _add_general(s, suppress=True)

    f = _parser(sub, "fracos", help="mostra as contas com mais erros ou mais lentas")
    f.add_argument("-n", type=_positive, default=10, metavar="N", help="quantas contas mostrar (padrão: 10)")
    _add_general(f, suppress=True)

    z = _parser(sub, "reset", help="apaga o histórico (pede confirmação)")
    z.add_argument("--sim", action="store_true", help="não pede confirmação")
    _add_general(z, suppress=True)
    return p


def _train(args):
    from .session import train

    given = [args.n, args.tempo, args.tabelas, args.min, args.max] + [True if args.foco else None]
    if all(v is None for v in given):
        cfg = Config.from_dict(storage.load_config()["last"])
    else:
        cfg = Config(tabelas=args.tabelas or list(range(1, 13)), n=args.n or (None if args.tempo else 20),
                     tempo=args.tempo, min=args.min or 1, max=args.max or 12, foco=args.foco)
        if cfg.min > cfg.max:
            cfg.min, cfg.max = cfg.max, cfg.min
    if not args.sem_historico:
        storage.update_config(last=cfg.to_dict())
    train(cfg, save=not args.sem_historico)


def _report(args):
    from .session import show_report

    sessions = storage.load_history()
    rep = report.build_for_id(sessions, args.sessao)
    if rep is None:
        msg = "Não achei a sessão %d." % args.sessao if args.sessao else "Nenhuma sessão ainda."
        print(msg + " Veja as sessões com: tabuada historico", file=sys.stderr)
        return 1
    flags = {"t": args.tempo, "e": args.erros, "d": args.tabelas, "c": args.comparacao}
    opened = set(flags) if args.completo else {k for k, v in flags.items() if v}
    show_report(rep, interactive=not (opened or args.completo), opened=opened)
    return 0


def _history(args):
    sessions = storage.load_history()
    rows = report.history_rows(sessions)
    limit = None if args.todas else 10
    print("\n".join(render.history_lines(rows, limit)))
    if rows:
        streak, _ = report.day_streaks(sessions)
        print()
        print(render.history_footer(rows, streak, limit))
        print("  " + term.paint("Ver uma sessão: tabuada relatorio --sessao %d" % rows[0]["id"], "d"))
    print()


def _reset(args):
    n = len(storage.load_history())
    if not n:
        print("O histórico já está vazio.")
        return
    if not args.sim:
        try:
            answer = input("Apagar %d %s do histórico? Isso não tem volta. (s/N): "
                           % (n, "sessão" if n == 1 else "sessões")).strip().lower()
        except (KeyboardInterrupt, EOFError):
            answer = ""
        if answer not in ("s", "sim"):
            print("Nada foi apagado.")
            return
    storage.reset_history()
    print("Histórico apagado.")


def main(argv=None):
    args = build_parser().parse_args(argv)
    term.setup(ascii=args.ascii, no_color=args.sem_cor)
    try:
        if args.web:
            from .webserver import run
            return run()
        if args.command is None:
            from .menu import main_menu
            return main_menu()
        if args.command == "treinar":
            return _train(args)
        if args.command == "relatorio":
            return _report(args)
        if args.command == "historico":
            return _history(args)
        if args.command == "stats":
            print("\n".join(render.stats_lines(report.stats(storage.load_history(),
                                                           "tempo" if args.tempo else "dominio"))))
            print()
            return 0
        if args.command == "fracos":
            print("\n".join(render.weak_lines(report.weak_facts(storage.load_history(), args.n))))
            print()
            return 0
        if args.command == "reset":
            return _reset(args)
    except (KeyboardInterrupt, EOFError):
        print("\n\n  Até a próxima!\n")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
