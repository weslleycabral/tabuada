"""Saída no terminal: cores, símbolos e compatibilidade entre sistemas."""

import os
import sys


class _State:
    ansi = False       # terminal entende sequências de escape (cursor, limpar tela)
    color = False      # cores ligadas
    truecolor = False  # cores 24 bits, iguais ao mockup
    unicode = True     # símbolos ✓ ✗ ─ █; se False usa ASCII


T = _State()

# nome: ((r, g, b), código ANSI de 16 cores)
PALETTE = {
    "c": ((0x74, 0xC7, 0xEC), "36"),
    "g": ((0x7F, 0xD6, 0x9B), "32"),
    "r": ((0xF2, 0x76, 0x7B), "31"),
    "y": ((0xE8, 0xC4, 0x68), "33"),
    "d": ((0x6D, 0x7A, 0x8B), "90"),
    "l0": ((0x2A, 0x32, 0x3D), "90"),
    "l1": ((0x2F, 0x8F, 0x5B), "32"),
    "l2": ((0x7F, 0xD6, 0x9B), "92"),
    "l3": ((0xE8, 0xC4, 0x68), "33"),
    "l4": ((0xF2, 0x76, 0x7B), "31"),
}

_UNICODE = {
    "ok": "✓", "err": "✗", "hr": "─", "full": "█", "light": "░",
    "spark": "▁▂▃▄▅▆▇█", "times": "×", "minus": "−", "dot": "·",
    "range": "–", "arrow": "←", "to": "→",
}
_ASCII = {
    "ok": "+", "err": "x", "hr": "-", "full": "#", "light": ".",
    "spark": "_.-=+*#@", "times": "x", "minus": "-", "dot": "|",
    "range": "-", "arrow": "<-", "to": "->",
}


_TO_ASCII = str.maketrans({
    **{u: a for u, a in zip(_UNICODE.values(), _ASCII.values()) if len(u) == 1},
    **dict(zip("▁▂▃▄▅▆▇", "_.-=+*#")),
    "–": "-", "—": "-", "≥": ">=", "⏎": "Enter",
})


def to_ascii(text):
    return text.translate(_TO_ASCII)


class _AsciiWriter:
    """Troca símbolos por equivalentes ASCII em tudo que vai para a tela."""

    def __init__(self, inner):
        self._inner = inner

    def write(self, text):
        return self._inner.write(to_ascii(text))

    def __getattr__(self, name):
        return getattr(self._inner, name)


def sym(name):
    return (_UNICODE if T.unicode else _ASCII)[name]


def _enable_windows_vt():
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def _can_encode(text):
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        text.encode(enc)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def setup(ascii=False, no_color=False):
    out = sys.stdout
    if hasattr(out, "reconfigure") and not _can_encode("✓"):
        try:
            out.reconfigure(errors="replace")
        except Exception:
            pass
    tty = out.isatty()
    dumb = os.environ.get("TERM") == "dumb"
    vt = tty and not dumb and (os.name != "nt" or _enable_windows_vt())
    T.ansi = vt
    T.color = vt and not no_color and "NO_COLOR" not in os.environ
    T.truecolor = T.color and (
        os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
        or "WT_SESSION" in os.environ
    )
    T.unicode = (
        not ascii
        and "TABUADA_ASCII" not in os.environ
        and _can_encode("".join(_UNICODE.values()))
    )
    if not T.unicode and not isinstance(sys.stdout, _AsciiWriter):
        sys.stdout = _AsciiWriter(sys.stdout)


def paint(text, *styles):
    """Aplica estilos: nomes de PALETTE, 'b' (negrito) ou 'inv' (tecla)."""
    if not T.color or not styles:
        return text
    codes = []
    for s in styles:
        if s == "b":
            codes.append("1")
        elif s == "inv":
            codes.append("48;2;42;51;64;38;2;241;244;247" if T.truecolor else "7")
        else:
            rgb, basic = PALETTE[s]
            codes.append("38;2;%d;%d;%d" % rgb if T.truecolor else basic)
    return "\x1b[%sm%s\x1b[0m" % (";".join(codes), text)


def key(k):
    """Tecla de atalho: fundo destacado com cor, [k] sem cor."""
    return paint(" %s " % k, "inv") if T.color else "[%s]" % k


def hr(width=56):
    return paint(sym("hr") * width, "d")


def clear():
    if T.ansi:
        sys.stdout.write("\x1b[H\x1b[2J")
        sys.stdout.flush()


def out(*lines):
    for line in lines:
        print(line)
