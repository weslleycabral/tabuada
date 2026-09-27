"""Regras do treino: configuração, sorteio de contas e registro das respostas.

Sem entrada/saída: usado tanto pelo terminal quanto pelo modo web.
"""

import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import List, Optional

ALL = list(range(1, 13))


def parse_tabelas(text):
    """'todas', '6,7,8', '2-9' ou combinações como '2-4,7' -> lista ordenada."""
    text = (text or "").strip().lower()
    if text in ("", "todas", "tudo", "all"):
        return list(ALL)
    result = set()
    for part in text.replace(" ", "").split(","):
        if not part:
            continue
        try:
            if "-" in part:
                lo, hi = (int(x) for x in part.split("-", 1))
                if lo > hi:
                    lo, hi = hi, lo
                result.update(range(lo, hi + 1))
            else:
                result.add(int(part))
        except ValueError:
            raise ValueError("Use números de 1 a 12, por exemplo: todas, 6,7,8 ou 2-9.")
    if not result or min(result) < 1 or max(result) > 12:
        raise ValueError("As tabelas vão de 1 a 12, por exemplo: todas, 6,7,8 ou 2-9.")
    return sorted(result)


def format_tabelas(tabelas, sep="-"):
    """[6,7,8,9] -> '6-9'; [1..12] -> 'todas'; [2,3,7] -> '2,3,7'."""
    tabelas = sorted(set(tabelas))
    if tabelas == ALL:
        return "todas"
    parts, start, prev = [], None, None
    for t in tabelas + [None]:
        if start is None:
            start = prev = t
        elif t is not None and t == prev + 1:
            prev = t
        else:
            if prev - start >= 2:
                parts.append("%d%s%d" % (start, sep, prev))
            else:
                parts.extend(str(x) for x in range(start, prev + 1))
            start = prev = t
    return ",".join(parts)


def format_duration(seconds):
    m, s = divmod(int(seconds), 60)
    if m and s:
        return "%d min %d s" % (m, s)
    return "%d min" % m if m else "%d s" % s


@dataclass
class Config:
    tabelas: List[int] = field(default_factory=lambda: list(ALL))
    n: Optional[int] = 20
    tempo: Optional[int] = None
    min: int = 1
    max: int = 12
    foco: bool = False

    @classmethod
    def from_dict(cls, d):
        known = {k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__}
        cfg = cls(**known)
        if cfg.tempo:
            cfg.n = None
        elif not cfg.n:
            cfg.n = 20
        return cfg

    def to_dict(self):
        return asdict(self)

    def mode_desc(self):
        if self.tempo:
            return format_duration(self.tempo)
        return "%d perguntas" % self.n

    def describe(self):
        parts = ["tabelas " + format_tabelas(self.tabelas, "–"), self.mode_desc()]
        if (self.min, self.max) != (1, 12):
            parts.append("fator %d a %d" % (self.min, self.max))
        if self.foco:
            parts.append("foco nos pontos fracos")
        return " · ".join(parts)

    def command(self):
        cmd = ["tabuada", "treinar"]
        if self.tabelas != ALL:
            cmd += ["--tabelas", format_tabelas(self.tabelas)]
        cmd += ["--tempo", str(self.tempo)] if self.tempo else ["-n", str(self.n)]
        if self.min != 1:
            cmd += ["--min", str(self.min)]
        if self.max != 12:
            cmd += ["--max", str(self.max)]
        if self.foco:
            cmd.append("--foco")
        return " ".join(cmd)


def fact_key(a, b):
    return (a, b) if a <= b else (b, a)


def median(values):
    values = sorted(values)
    if not values:
        return 0
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def fact_stats(sessions):
    """Por conta (a×b == b×a): vezes vista, erros e tempos."""
    stats = {}
    for s in sessions:
        for ans in s.get("answers", []):
            st = stats.setdefault(fact_key(ans["a"], ans["b"]),
                                  {"seen": 0, "errors": 0, "ms": []})
            st["seen"] += 1
            if not ans["ok"]:
                st["errors"] += 1
            if not ans.get("skipped"):
                st["ms"].append(ans["ms"])
    return stats


def weakness_weights(pairs, sessions):
    """Peso de sorteio por conta: mais erros e mais lentidão = aparece mais."""
    stats = fact_stats(sessions)
    all_ms = [ms for st in stats.values() for ms in st["ms"]]
    med = median(all_ms) or 1
    known = {}
    for key, st in stats.items():
        err_rate = st["errors"] / st["seen"]
        slow = max(0.0, (sum(st["ms"]) / len(st["ms"])) / med - 1) if st["ms"] else 0
        known[key] = 1 + 6 * err_rate + 2 * min(slow, 3)
    default = sum(known.values()) / len(known) if known else 1
    return [known.get(fact_key(a, b), default) for a, b in pairs]


class Drill:
    """Sorteia contas e guarda as respostas de uma sessão."""

    def __init__(self, config, history=(), rng=None):
        self.config = config
        self.rng = rng or random.Random()
        self.pairs = [(a, b) for a in config.tabelas
                      for b in range(config.min, config.max + 1)]
        if not self.pairs:
            raise ValueError("Nenhuma conta para treinar com essa configuração.")
        self.weights = (weakness_weights(self.pairs, list(history))
                        if config.foco else [1] * len(self.pairs))
        self.answers = []
        self.retry = []  # [(pergunta_em, (a, b))]
        self.last = None

    def next_question(self):
        asked = len(self.answers)
        for i, (due, pair) in enumerate(self.retry):
            if due <= asked and pair != self.last:
                del self.retry[i]
                self.last = pair
                return pair
        choices = [(p, w) for p, w in zip(self.pairs, self.weights) if p != self.last]
        if not choices:
            choices = list(zip(self.pairs, self.weights))
        pairs, weights = zip(*choices)
        pair = self.rng.choices(pairs, weights=weights)[0]
        self.last = pair
        return pair

    def record(self, a, b, resp, ms, skipped=False):
        ok = (not skipped) and resp == a * b
        ans = {"a": a, "b": b, "resp": None if skipped else resp,
               "ok": ok, "skipped": skipped, "ms": int(ms)}
        self.answers.append(ans)
        if not ok:
            self.retry.append((len(self.answers) + self.rng.randint(2, 4), (a, b)))
        return ans

    def done(self, elapsed_s):
        if self.config.tempo:
            return elapsed_s >= self.config.tempo
        return len(self.answers) >= self.config.n

    def is_slow(self, ms):
        """Resposta acima de 2× a mediana da sessão (a partir de 3 respostas)."""
        prior = [x["ms"] for x in self.answers[:-1] if not x["skipped"]]
        return len(prior) >= 3 and ms > 2 * median(prior)

    def to_session(self, started, duration_ms, interrupted):
        return {
            "started": started.isoformat(timespec="seconds"),
            "config": self.config.to_dict(),
            "duration_ms": int(duration_ms),
            "interrupted": interrupted,
            "answers": self.answers,
        }


def now():
    return datetime.now()


def max_digits(a, b):
    """Dígitos do maior produto possível com fatores desse tamanho: 9×9 -> 2, 12×12 -> 4."""
    return len(str(abs(a))) + len(str(abs(b)))


def answer_complete(typed, a, b):
    """A resposta vai sem Enter quando é a certa ou já tem o máximo de dígitos da conta."""
    return typed.isdigit() and (int(typed) == a * b or len(typed) >= max_digits(a, b))


INSTANT_KEYS = {"q": "quit", "p": "skip", "a": "toggle"}  # atalhos que agem sem Enter


def parse_answer(text):
    """Entrada do usuário -> ('num', n) | ('quit'|'skip'|'toggle', None) | ('invalid', None)."""
    t = text.strip().lower()
    if t in ("q", "sair"):
        return "quit", None
    if t in ("p", "pular"):
        return "skip", None
    if t == "a":
        return "toggle", None
    if t.isdigit():
        return "num", int(t)
    return "invalid", None
