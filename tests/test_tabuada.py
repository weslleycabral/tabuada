import io
import json
import os
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from tabuada import render, report, session, storage, term
from datetime import datetime

from tabuada.drill import (AUTOMATIC, HESITATED, THOUGHT, WRONG, Config, Drill, answer_complete, format_tabelas,
                           grade, max_digits, memory, parse_answer, parse_tabelas, review_weights, typical_grade)


def make_session(answers, tabelas=(6, 7, 8, 9), started="2026-09-27T14:03:00", sid=1):
    return {"id": sid, "started": started, "config": Config(tabelas=list(tabelas)).to_dict(),
            "duration_ms": sum(a["ms"] for a in answers), "interrupted": False, "answers": answers}


def ans(a, b, resp=None, ms=2000, skipped=False):
    resp = a * b if resp is None and not skipped else resp
    return {"a": a, "b": b, "resp": resp, "ok": not skipped and resp == a * b,
            "skipped": skipped, "ms": ms}


class TempHome(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"TABUADA_HOME": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class ParseTest(unittest.TestCase):
    def test_tabelas(self):
        self.assertEqual(parse_tabelas("todas"), list(range(1, 13)))
        self.assertEqual(parse_tabelas(""), list(range(1, 13)))
        self.assertEqual(parse_tabelas("6,7,8"), [6, 7, 8])
        self.assertEqual(parse_tabelas("2-9"), list(range(2, 10)))
        self.assertEqual(parse_tabelas("9-7, 2"), [2, 7, 8, 9])
        for bad in ("0", "13", "a", "1-20"):
            with self.assertRaises(ValueError):
                parse_tabelas(bad)

    def test_format_tabelas(self):
        self.assertEqual(format_tabelas(range(1, 13)), "todas")
        self.assertEqual(format_tabelas([6, 7, 8, 9]), "6-9")
        self.assertEqual(format_tabelas([2, 3, 7, 8, 9, 12]), "2,3,7-9,12")

    def test_answer(self):
        self.assertEqual(parse_answer(" 42 "), ("num", 42))
        self.assertEqual(parse_answer("Q"), ("quit", None))
        self.assertEqual(parse_answer("p"), ("skip", None))
        self.assertEqual(parse_answer("a"), ("toggle", None))
        self.assertEqual(parse_answer("4 2"), ("invalid", None))

    def test_answer_complete(self):
        self.assertEqual((max_digits(9, 9), max_digits(12, 12), max_digits(123, 456789)), (2, 4, 9))
        self.assertTrue(answer_complete("81", 9, 9))    # certa
        self.assertTrue(answer_complete("75", 9, 9))    # errada, mas já tem 2 dígitos
        self.assertFalse(answer_complete("8", 9, 9))
        self.assertTrue(answer_complete("9", 3, 3))     # certa com menos dígitos que o máximo
        self.assertFalse(answer_complete("1", 3, 3))
        self.assertFalse(answer_complete("14", 12, 12))
        self.assertTrue(answer_complete("144", 12, 12))
        self.assertFalse(answer_complete("", 2, 2))
        self.assertFalse(answer_complete("p", 2, 2))

    def test_command(self):
        cfg = Config(tabelas=[6, 7, 8, 9], n=20, foco=True)
        self.assertEqual(cfg.command(), "tabuada treinar --tabelas 6-9 -n 20 --foco")
        self.assertEqual(Config(tempo=120, n=None).command(), "tabuada treinar --tempo 120")
        self.assertEqual(Config(tempo=90, n=None).describe(), "tabelas todas · 1 min 30 s")


class DrillTest(unittest.TestCase):
    def test_respects_filters_and_no_repeat(self):
        d = Drill(Config(tabelas=[7, 8], min=3, max=5), rng=random.Random(1))
        prev = None
        for _ in range(200):
            a, b = d.next_question()
            self.assertIn(a, (7, 8))
            self.assertTrue(3 <= b <= 5)
            self.assertNotEqual((a, b), prev)
            prev = (a, b)

    def test_wrong_answer_comes_back_in_3_to_5(self):
        for seed in range(20):
            d = Drill(Config(), rng=random.Random(seed))
            a, b = d.next_question()
            d.record(a, b, 0, 1000)
            seen_at = None
            for i in range(1, 7):
                q = d.next_question()
                if q == (a, b):
                    seen_at = i
                    break
                d.record(q[0], q[1], q[0] * q[1], 1000)
            self.assertIsNotNone(seen_at)
            self.assertTrue(3 <= seen_at <= 5, seen_at)

    def test_done(self):
        d = Drill(Config(n=2))
        self.assertFalse(d.done(0))
        d.record(2, 2, 4, 100)
        d.record(2, 3, 6, 100)
        self.assertTrue(d.done(0))
        self.assertTrue(Drill(Config(tempo=60, n=None)).done(61))

    def test_grade_by_time(self):
        self.assertEqual([grade(ans(2, 2, ms=ms)) for ms in (1500, 2000, 3000, 4000, 4100)],
                         [AUTOMATIC, AUTOMATIC, HESITATED, HESITATED, THOUGHT])
        self.assertEqual(grade(ans(2, 2, resp=5, ms=500)), WRONG)
        self.assertEqual(grade(ans(2, 2, skipped=True, ms=500)), WRONG)
        self.assertEqual(typical_grade([WRONG, AUTOMATIC, AUTOMATIC, AUTOMATIC]), AUTOMATIC)
        self.assertEqual(typical_grade([AUTOMATIC, WRONG]), WRONG)  # na dúvida, a pior

    def test_spaced_repetition_boxes(self):
        day = lambda d: "2026-09-%02dT10:00:00" % d
        fast = lambda: make_session([ans(7, 8, ms=1500)] * 3, started=day(d))
        sessions = []
        for d in (1, 2, 4, 8):  # automática a cada revisão vencida: sobe uma caixa por vez
            sessions.append(fast())
        self.assertEqual(memory(sessions)[(7, 8)]["box"], 4)
        # rever antes da hora não sobe de caixa
        self.assertEqual(memory([make_session([ans(7, 8, ms=1500)] * 10, started=day(1))])[(7, 8)]["box"], 1)
        # hesitar limita a 2, pensar a 1, errar zera
        for extra, box in ((ans(8, 7, ms=3000), 2), (ans(8, 7, ms=9000), 1), (ans(8, 7, resp=1), 0)):
            s = sessions + [make_session([extra], started=day(29))]
            self.assertEqual(memory(s)[(7, 8)]["box"], box)

    def test_review_weights_follow_schedule(self):
        s = [make_session([ans(2, 2, ms=1500)] * 1, started="2026-09-01T10:00:00"),
             make_session([ans(2, 2, ms=1500), ans(3, 3, resp=1)], started="2026-09-02T10:00:00")]
        pairs = [(2, 2), (3, 3), (4, 4)]
        at = datetime(2026, 9, 2, 12, 0)
        w = dict(zip(pairs, review_weights(pairs, s, at)))
        self.assertLess(w[(2, 2)], 1)          # automática e em dia: quase não aparece
        self.assertGreater(w[(3, 3)], w[(4, 4)])  # errada pesa mais que nunca vista
        later = dict(zip(pairs, review_weights(pairs, s, datetime(2026, 9, 10))))
        self.assertGreater(later[(2, 2)], 1)   # revisão vencida volta a aparecer

    def test_in_session_repetition_by_grade(self):
        d = Drill(Config(tabelas=[2, 3], min=2, max=3), rng=random.Random(1))
        d.record(2, 2, 4, 1000)
        d.record(3, 3, 9, 9000)
        w = dict(zip(d.pairs, d.weights))
        self.assertAlmostEqual(w[(2, 2)], 0.1)   # automática quase não se repete
        self.assertEqual(w[(2, 3)], w[(3, 2)])  # 2×3 e 3×2 contam juntas
        self.assertIn((3, 3), [p for _, p in d.retry])  # pensou: volta mais tarde
        due = [at for at, p in d.retry if p == (3, 3)][0]
        self.assertTrue(len(d.answers) + 5 <= due <= len(d.answers) + 8)

    def test_focus_prefers_weak_facts(self):
        history = [make_session([ans(7, 8, resp=54, ms=9000)] * 10 + [ans(2, 2)] * 10)]
        d = Drill(Config(tabelas=[2, 7], min=2, max=8, foco=True), history, random.Random(3))
        w = dict(zip(d.pairs, d.weights))
        self.assertGreater(w[(7, 8)], w[(2, 2)])


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.answers = [ans(6, 7), ans(7, 8, resp=54, ms=6100), ans(8, 7, ms=50200),
                        ans(8, 6, skipped=True, ms=8400), ans(9, 3, ms=1200), ans(9, 9, ms=1900)]
        self.s = make_session(self.answers, sid=2)

    def test_summary(self):
        sm = report.summary(self.s, [])
        self.assertEqual((sm["total"], sm["ok"], sm["errors"], sm["skipped"]), (6, 4, 1, 1))
        self.assertEqual(sm["pct"], 67)
        self.assertIsNone(sm["delta_pct"])

    def test_time_group_keeps_long_answers(self):
        t = report.time_group(self.s, [])
        self.assertEqual(t["slowest"]["ms"], 50200)
        self.assertEqual([a["ms"] for a in t["top"]][:2], [50200, 8400])
        self.assertIn(50200, [a["ms"] for a in t["slow_ok"]])

    def test_tables_and_recommendation(self):
        rep = report.build(self.s, [])
        worst = [r for r in rep["tables"] if r["worst"]]
        self.assertEqual(worst[0]["t"], 7)
        self.assertIn("--tabelas 7", rep["recommendation"]["command"])

    def test_compare_record(self):
        before = [make_session([ans(2, 2)] * 3, sid=1)]
        c = report.compare_group(make_session([ans(2, 2)] * 5), before)
        self.assertTrue(c["new_record"])
        self.assertEqual(c["prev"]["pct"], 100)

    def test_day_streaks(self):
        sessions = [make_session([ans(2, 2)], started="2026-09-%02dT10:00:00" % d) for d in (20, 21, 22, 25, 26)]
        self.assertEqual(report.day_streaks(sessions, today=date(2026, 9, 27)), (2, 3))
        self.assertEqual(report.day_streaks(sessions, today=date(2026, 9, 30))[0], 0)

    def test_weak_facts(self):
        history = [make_session([ans(7, 8, resp=54)] * 3 + [ans(2, 2)] * 5)]
        rows = report.weak_facts(history)["rows"]
        self.assertEqual((rows[0]["a"], rows[0]["b"]), (7, 8))
        self.assertIn("erra", rows[0]["reasons"])

    def test_weak_fact_only_skipped_has_no_time(self):
        history = [make_session([ans(3, 4, skipped=True)] + [ans(2, 2)] * 5)]
        row = next(r for r in report.weak_facts(history)["rows"] if (r["a"], r["b"]) == (3, 4))
        self.assertIsNone(row["ms"])
        term.T.color = False
        self.assertIn("  —  ", "\n".join(render.weak_lines(report.weak_facts(history))))

    def test_render_all_groups_ascii_and_unicode(self):
        rep = report.build(self.s, [make_session([ans(2, 2)])])
        for uni in (True, False):
            term.T.unicode, term.T.color = uni, False
            text = "\n".join(render.report_lines(rep, {"t", "e", "d", "c"}) + render.menu_lines(rep, set()))
            self.assertIn("50,2 s", text)
            if not uni:
                term.to_ascii(text).encode("latin-1")  # só letras acentuadas fora do ASCII
        term.T.unicode = True


class StorageTest(TempHome):
    def test_ids_and_config(self):
        self.assertEqual(storage.add_session(make_session([ans(2, 2)])), 1)
        self.assertEqual(storage.add_session(make_session([ans(2, 3)])), 2)
        self.assertEqual([s["id"] for s in storage.load_history()], [1, 2])
        storage.update_config(show_shortcuts=False)
        self.assertFalse(storage.load_config()["show_shortcuts"])
        self.assertEqual(storage.load_config()["last"]["n"], 20)

    def test_corrupted_file_is_moved_aside(self):
        Path(self.tmp.name, "history.json").write_text("{nope", encoding="utf-8")
        with mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(storage.load_history(), [])
        self.assertTrue(any(p.name.startswith("history.json.corrompido") for p in Path(self.tmp.name).iterdir()))


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class SessionTest(TempHome):
    def test_toggle_time_not_counted_and_slow_answer_kept(self):
        term.T.ansi = term.T.color = False
        clock = FakeClock()
        replies = iter([("a", 5.0), ("zz", 1.0), (None, 50.0), ("q", 0.5)])

        def fake_input(prompt=""):
            text, took = next(replies)
            clock.t += took
            if text is None:  # responde certo, lendo a conta do prompt
                nums = [int(x) for x in prompt.replace("=", " ").split() if x.isdigit()]
                text = str(nums[0] * nums[1])
            return text

        with mock.patch("builtins.input", fake_input), mock.patch("time.monotonic", clock), \
                redirect_stdout(io.StringIO()) as out:
            sess, before = session.play(Config(tabelas=[7], n=5))
        self.assertEqual(len(sess["answers"]), 1)
        self.assertEqual(sess["answers"][0]["ms"], 51000)  # 1 s (inválida) + 50 s, sem os 5 s do toggle
        self.assertTrue(sess["answers"][0]["ok"])
        self.assertTrue(sess["interrupted"])
        self.assertFalse(storage.load_config()["show_shortcuts"])
        self.assertIn("[a] atalhos", out.getvalue())


class WebTest(TempHome):
    def test_flow(self):
        from tabuada.webserver import App
        app = App()
        st = app.start({"config": {"tabelas": "7", "n": "2"}})["state"]
        a, b = st["question"]
        r = app.answer({"input": str(a * b)})
        self.assertTrue(r["feedback"]["ok"])
        self.assertTrue(app.answer({"input": "xx"})["invalid"])
        r = app.answer({"input": "1"})
        self.assertTrue(r["done"])
        self.assertEqual(r["report"]["summary"]["total"], 2)
        self.assertEqual(len(app.history({})["rows"]), 1)
        json.dumps(app.stats({}))


if __name__ == "__main__":
    unittest.main()
