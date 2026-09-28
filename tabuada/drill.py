"""Regras do treino: configuração, sorteio de contas e registro das respostas.

Sem entrada/saída: usado tanto pelo terminal quanto pelo modo web.
"""

import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
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


# Um acerto em até 2 s é lembrança; acima disso você teve que pensar.
FAST_MS = 2000
SLOW_MS = 4000

# Nota de cada resposta
WRONG, THOUGHT, HESITATED, AUTOMATIC = 0, 1, 2, 3


def grade(ans):
    """0 errou ou pulou, 1 acertou pensando (>4 s), 2 hesitou (2–4 s), 3 automático (≤2 s)."""
    if not ans["ok"]:
        return WRONG
    if ans["ms"] <= FAST_MS:
        return AUTOMATIC
    return HESITATED if ans["ms"] <= SLOW_MS else THOUGHT


# Repetição espaçada (caixas de Leitner): quanto maior a caixa, mais tempo até a
# próxima revisão. Só sobe de caixa quem responde automático depois do intervalo.
REVIEW_AFTER = [timedelta(0), timedelta(minutes=10), timedelta(days=1),
                timedelta(days=3), timedelta(days=7), timedelta(days=21)]
TOP_BOX = len(REVIEW_AFTER) - 1


def next_box(box, g, due):
    if g == WRONG:
        return 0
    if g == THOUGHT:
        return min(box, 1)
    if g == HESITATED:
        return min(max(box, 1), 2)
    return min(box + 1, TOP_BOX) if due else max(box, 1)


def memory(sessions):
    """Por conta (a×b == b×a): caixa de revisão, última vez vista e as notas em ordem."""
    mem = {}
    for s in sessions:
        when = datetime.fromisoformat(s["started"])
        for ans in s.get("answers", []):
            m = mem.setdefault(fact_key(ans["a"], ans["b"]), {"box": 0, "last": None, "grades": []})
            due = m["last"] is None or when - m["last"] >= REVIEW_AFTER[m["box"]]
            g = grade(ans)
            m["box"] = next_box(m["box"], g, due)
            m["grades"].append(g)
            m["last"] = when
    for m in mem.values():
        m["due_at"] = m["last"] + REVIEW_AFTER[m["box"]]
    return mem


def typical_grade(grades):
    """Como você costuma responder: mediana das 3 últimas notas (na dúvida, a pior)."""
    last = sorted(grades[-3:])
    return last[(len(last) - 1) // 2] if last else None


# Peso de sorteio no --foco: vencida para revisão pesa pela caixa; em dia, quase não aparece.
DUE_WEIGHT = [8, 6, 4, 3, 2, 2]
NEW_WEIGHT = 4
NOT_DUE_WEIGHT = 0.25


def review_weights(pairs, sessions, at=None):
    mem = memory(sessions)
    at = at or datetime.now()
    weights = []
    for a, b in pairs:
        m = mem.get(fact_key(a, b))
        if m is None:
            weights.append(NEW_WEIGHT)
        elif at >= m["due_at"]:
            weights.append(DUE_WEIGHT[m["box"]])
        else:
            weights.append(NOT_DUE_WEIGHT)
    return weights


class Drill:
    """Sorteia contas e guarda as respostas de uma sessão."""

    def __init__(self, config, history=(), rng=None):
        self.config = config
        self.rng = rng or random.Random()
        self.pairs = [(a, b) for a in config.tabelas
                      for b in range(config.min, config.max + 1)]
        if not self.pairs:
            raise ValueError("Nenhuma conta para treinar com essa configuração.")
        self.weights = (review_weights(self.pairs, list(history))
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
        g = grade(ans)
        if g == WRONG:  # volta em 3 a 5 perguntas
            self.retry.append((len(self.answers) + self.rng.randint(2, 4), (a, b)))
        elif g == THOUGHT:  # sabe, mas pensou: volta mais tarde, em 6 a 9
            self.retry.append((len(self.answers) + self.rng.randint(5, 8), (a, b)))
        else:  # automática quase não se repete na sessão; hesitante, menos
            key = fact_key(a, b)
            for i, p in enumerate(self.pairs):
                if fact_key(*p) == key:
                    self.weights[i] *= 0.1 if g == AUTOMATIC else 0.5
        return ans

    def done(self, elapsed_s):
        if self.config.tempo:
            return elapsed_s >= self.config.tempo
        return len(self.answers) >= self.config.n

    def is_slow(self, ms):
        """Acertou pensando: acima de SLOW_MS."""
        return ms > SLOW_MS

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
