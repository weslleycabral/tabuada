"use strict";
// Interface web do tabuada: as mesmas telas do terminal, desenhadas no navegador.

const screen = document.getElementById("screen");
const titleEl = document.getElementById("title");
let acts = {};   // ação -> função, para cliques em [data-act]
let keys = {};   // tecla -> ação, quando nenhum campo está focado
let home = null; // último /api/home
let clockTimer = null;

// ---------- utilidades ----------

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const sp = (cls, text) => `<span class="${cls}">${esc(text)}</span>`;
const ln = (...parts) => `<div class="ln">${parts.join("")}</div>`;
const BLANK = ln("");
const HR = ln("  ", sp("d", "─".repeat(56)));
const T = "×";
const fact = (a, b) => `${a} ${T} ${b}`;
const secs = (ms, w = 0) => (ms == null ? "—" : (ms / 1000).toFixed(1).replace(".", ",") + " s").padStart(w);
const pct = (v) => `${Math.round(v)}%`;
const lpad = (s, n) => String(s).padStart(n);
const rpad = (s, n) => String(s).padEnd(n);

const ICONS = {
  ok: '<svg class="ico" viewBox="0 0 16 16" aria-label="certo"><path d="M3 8.5l3.2 3.2L13 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  err: '<svg class="ico" viewBox="0 0 16 16" aria-label="errado"><path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
};
const icon = (name, cls) => `<span class="${cls}">${ICONS[name]}</span>`;

function btn(k, label, act, hint = "", width = 0) {
  const lbl = width ? rpad(label, width) : label;
  return `<button class="key" data-act="${act}"><span class="k"> ${esc(k)} </span> <span class="lbl">${esc(lbl)}</span></button>` +
    (hint ? "  " + sp("d", hint) : "");
}

function signed(value, digits, goodWhenNegative, suffix) {
  if (value === null || value === undefined) return "";
  const txt = Math.abs(value).toFixed(digits).replace(".", ",");
  if (Number(Math.abs(value).toFixed(1)) === 0) return sp("d", "igual");
  const good = goodWhenNegative ? value < 0 : value > 0;
  return sp(good ? "g" : "r", (value > 0 ? "+" : "−") + txt + suffix);
}

function when(iso, withYear = true) {
  const d = new Date(iso);
  const two = (n) => String(n).padStart(2, "0");
  const date = `${two(d.getDate())}/${two(d.getMonth() + 1)}` + (withYear ? `/${d.getFullYear()}` : "");
  return `${date} ${two(d.getHours())}:${two(d.getMinutes())}`;
}

function durationText(ms) {
  const total = Math.round(ms / 1000), m = Math.floor(total / 60), s = total % 60;
  if (m && s) return `${m} min ${s} s`;
  return m ? `${m} min` : `${s} s`;
}

function formatTabelas(list) {
  const t = [...new Set(list)].sort((a, b) => a - b);
  if (t.length === 12) return "todas";
  const parts = [];
  let i = 0;
  while (i < t.length) {
    let j = i;
    while (j + 1 < t.length && t[j + 1] === t[j] + 1) j++;
    if (j - i >= 2) parts.push(`${t[i]}-${t[j]}`);
    else for (let k = i; k <= j; k++) parts.push(String(t[k]));
    i = j + 1;
  }
  return parts.join(",");
}

async function api(path, body) {
  const opts = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  };
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Erro no servidor.");
  return data;
}

function show(lines, title, keyMap = {}, actMap = {}) {
  clearInterval(clockTimer);
  screen.innerHTML = lines.join("");
  titleEl.textContent = "~ — " + title;
  keys = keyMap;
  acts = actMap;
  window.scrollTo(0, 0);
}

screen.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]");
  if (el && acts[el.dataset.act]) acts[el.dataset.act](el.dataset);
});

document.addEventListener("keydown", (e) => {
  if (e.target.matches("input, select, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key.toLowerCase();
  const act = keys[k] || (k === "escape" ? keys.enter : undefined);
  if (act && acts[act]) {
    e.preventDefault();
    acts[act]();
  }
});

const backLines = (extra = []) => [BLANK, HR, ...extra, ln("    ", btn("Enter", "Voltar ao menu", "menu"))];

// ---------- menu inicial ----------

function lastLine(last) {
  if (!last) return "Nenhuma sessão ainda. Escolha 1 para começar.";
  const d = new Date(last.started);
  const days = Math.round((new Date().setHours(0, 0, 0, 0) - new Date(d).setHours(0, 0, 0, 0)) / 864e5);
  const day = days === 0 ? "hoje" : days === 1 ? "ontem" : when(last.started, false).slice(0, 5);
  return `Última sessão: ${day} às ${when(last.started).slice(-5)} · ${last.total} perguntas · ${last.pct}% de acerto`;
}

async function menu() {
  home = await api("/api/home");
  const items = [
    ["1", "Treinar (configurar)", "", "wizard"],
    ["2", "Treinar com a última configuração", home.config_desc, "again"],
    ["3", "Ver histórico", "", "history"],
    ["4", "Estatísticas", "", "stats"],
    ["5", "Pontos fracos", "", "weak"],
    ["6", "Sair", "", "exit"],
  ];
  const lines = [
    BLANK,
    ln("  ", sp("b", "TABUADA"), " ", sp("d", `· treino até 12${T}12`)),
    ln("  ", sp("d", lastLine(home.last))),
    BLANK, ln("  O que você quer fazer?"), BLANK,
    ...items.map(([k, label, hint, act]) => ln("    ", btn(k, label, act, hint, 33))),
    BLANK, HR,
    ln("  ", sp("d", "Aperte o número ou clique na opção")),
  ];
  show(lines, "tabuada", Object.fromEntries(items.map((i) => [i[0], i[3]])), {
    wizard, history, weak, stats: () => stats("dominio"),
    again: () => startTraining(null),
    exit: () => show([BLANK, ln("  Até a próxima!"), BLANK,
      ln("  ", sp("d", "Pode fechar esta aba. Para encerrar o servidor, use Ctrl+C no terminal.")),
      ...backLines()], "tabuada", { enter: "menu" }, { menu }),
  });
}

// ---------- assistente de configuração ----------

function wizard() {
  const c = home.config;
  const lines = [
    BLANK, ln("  ", sp("b", "Configurar treino")), BLANK,
    ln("  Quais tabelas?  ", sp("d", "todas · 6,7,8 · 2-9")),
    ln("  ", `<input class="tin" id="w-tab" value="${esc(formatTabelas(c.tabelas))}" aria-label="Tabelas">`),
    BLANK,
    ln("  Como você quer treinar?  ",
      `<select class="tin" id="w-mode" style="width:auto" aria-label="Modo">
        <option value="n"${c.tempo ? "" : " selected"}>Número de perguntas</option>
        <option value="tempo"${c.tempo ? " selected" : ""}>Contra-relógio</option></select>`),
    BLANK,
    ln("  ", `<span id="w-qlabel">Quantas perguntas?</span> `,
      `<input class="tin" id="w-q" style="width:7ch" inputmode="numeric" value="${c.tempo || c.n || 20}" aria-label="Quantidade">`),
    ln("  Focar nos seus pontos fracos?  ",
      `<select class="tin" id="w-foco" style="width:auto" aria-label="Foco">
        <option value="n"${c.foco ? "" : " selected"}>não</option>
        <option value="s"${c.foco ? " selected" : ""}>sim</option></select>`),
    BLANK,
    `<div id="w-preview"></div>`,
    BLANK, HR,
    ln("    ", btn("Enter", "Começar", "go"), "    ", btn("Esc", "Voltar ao menu", "menu")),
  ];
  show(lines, "tabuada", { enter: "go", escape: "menu" }, { menu, go });
  const $ = (id) => document.getElementById(id);
  const read = () => {
    const tempo = $("w-mode").value === "tempo";
    return { tabelas: $("w-tab").value, n: tempo ? null : $("w-q").value,
      tempo: tempo ? $("w-q").value : null, foco: $("w-foco").value === "s" };
  };
  let valid = true;
  async function refresh() {
    const tempo = $("w-mode").value === "tempo";
    $("w-qlabel").textContent = tempo ? "Quantos segundos?" : "Quantas perguntas?";
    const q = $("w-q").value.trim();
    let error = "";
    if (!/^\d+$/.test(q) || (tempo ? +q < 10 || +q > 3600 : +q < 1 || +q > 200)) {
      error = tempo ? "Digite um número entre 10 e 3600, por exemplo 120." : "Digite um número entre 1 e 200, por exemplo 20.";
    }
    let res = null;
    if (!error) {
      try { res = await api("/api/preview", { config: read() }); } catch (e) { error = e.message; }
    }
    valid = !error;
    $("w-preview").innerHTML = error ? ln("  ", sp("r", error)) : [
      ln("  ", icon("ok", "g"), " ", esc(res.desc.charAt(0).toUpperCase() + res.desc.slice(1))),
      BLANK, ln("  ", sp("d", "No terminal, o mesmo treino é:")), ln("    ", sp("c", res.command)),
    ].join("");
  }
  function go() {
    if (valid) startTraining(read());
  }
  ["w-tab", "w-q"].forEach((id) => $(id).addEventListener("input", refresh));
  ["w-mode", "w-foco"].forEach((id) => $(id).addEventListener("change", () => {
    if (id === "w-mode") $("w-q").value = $("w-mode").value === "tempo" ? 120 : 20;
    refresh();
  }));
  screen.addEventListener("keydown", function onKey(e) {
    if (!document.getElementById("w-tab")) return screen.removeEventListener("keydown", onKey);
    if (e.key === "Enter") { e.preventDefault(); go(); }
    if (e.key === "Escape") { e.preventDefault(); menu(); }
  });
  refresh();
  $("w-tab").focus();
}

// ---------- sessão ----------

async function startTraining(config) {
  const data = await api("/api/start", config ? { config } : {});
  session({ desc: data.desc, state: data.state, log: [], showBar: home.show_shortcuts });
}

function clock(s) {
  s = Math.max(0, Math.floor(s));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function feedbackLines(f) {
  const took = secs(f.ms);
  if (f.skipped) return [ln("        ", sp("d", `Pulou. ${fact(f.a, f.b)} = ${f.right}   ${took}`)),
    ln("        ", sp("d", "Essa conta volta daqui a pouco."))];
  if (f.ok) return [ln("        ", `<span class="b">${fact(f.a, f.b)} =</span> ${f.resp}`),
    ln("        ", icon("ok", "g"), sp("g", " Certo"), f.slow ? ", mas demorou   " + sp("y", took) : "   " + sp("g", took)),
    f.slow ? ln("        ", sp("d", "Essa conta volta mais tarde, para ficar automática.")) : ""];
  return [ln("        ", `<span class="b">${fact(f.a, f.b)} =</span> ${f.resp}`),
    ln("        ", icon("err", "r"), sp("r", ` ${fact(f.a, f.b)} = ${f.right}`), "   ", sp("d", took)),
    ln("        ", sp("d", "Essa conta volta daqui a pouco."))];
}

// Mesma regra de drill.answer_complete: vai sem Enter quando é a certa ou tem o máximo de dígitos.
const maxDigits = (a, b) => String(Math.abs(a)).length + String(Math.abs(b)).length;
const answerComplete = (typed, a, b) =>
  /^\d+$/.test(typed) && (Number(typed) === a * b || typed.length >= maxDigits(a, b));
const INSTANT_KEYS = { q: "quit", p: "skip", a: "toggle" };

function session(ctx, invalid = false) {
  const st = ctx.state;
  const receivedAt = performance.now();
  const [a, b] = st.question;
  const progress = st.tempo ? `${sp("d", "Pergunta")} ${sp("b", st.asked)}`
    : `${sp("d", "Pergunta")} ${sp("b", st.asked)}${sp("d", "/" + st.n)}`;
  const clockLabel = st.tempo ? "restam" : "tempo";
  const lines = [
    BLANK, ln("  ", sp("b", "Treino:"), " ", esc(ctx.desc)),
    ...ctx.log.slice(-12),
    BLANK,
    ln("  ", progress, "      ", icon("ok", "g"), sp("g", " " + st.ok), "   ", icon("err", "r"), sp("r", " " + st.errors),
      "   ", sp("d", "pulos " + st.skipped), "        ", sp("d", clockLabel), ` <span id="clock"></span>`),
    BLANK,
    ln("        ", `<span class="b">${fact(a, b)} =</span> `,
      `<input class="tin answer" id="ans" autocomplete="off" inputmode="numeric" aria-label="Resposta de ${a} vezes ${b}">`),
    invalid ? ln("        ", sp("r", "Digite só o resultado em números, ou uma das teclas de atalho.")) : "",
    BLANK,
    ...(ctx.showBar
      ? [HR, ln("  ", btn("q", "sair e ver relatório", "quit"), "   ", btn("p", "pular", "skip"), "   ", btn("a", "ocultar atalhos", "toggle"))]
      : [ln("  ", `<button class="key" data-act="toggle"><span class="d">[a] atalhos</span></button>`)]),
  ];
  let busy = false;
  const submit = async (value) => {
    if (busy) return;
    const v = value.trim().toLowerCase();
    if (v === "a") return toggle();
    if (!v) return;
    busy = true;
    try {
      const res = await api("/api/answer", { input: v });
      if (res.invalid) return session(ctx, true);
      if (res.feedback) ctx.log.push(BLANK, ...feedbackLines(res.feedback));
      if (res.done) return finish(res.report, ctx);
      ctx.state = res.state;
      session(ctx);
    } finally { busy = false; }
  };
  const toggle = () => {
    ctx.showBar = !ctx.showBar;
    home.show_shortcuts = ctx.showBar;
    api("/api/shortcuts", { show: ctx.showBar });
    const typed = document.getElementById("ans").value;
    session(ctx, invalid);
    const input = document.getElementById("ans");
    input.value = typed.toLowerCase() === "a" ? "" : typed;
  };
  show(lines, "tabuada treinar", {}, {
    quit: () => submit("q"), skip: () => submit("p"), toggle,
  });
  const input = document.getElementById("ans");
  input.focus();
  input.addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key.toLowerCase();
    if (e.key === "Enter") { e.preventDefault(); submit(input.value); }
    else if (INSTANT_KEYS[k]) { e.preventDefault(); k === "a" ? toggle() : submit(k); }
  });
  input.addEventListener("input", () => {
    if (answerComplete(input.value.trim(), a, b)) submit(input.value);
  });
  const tick = () => {
    const el = document.getElementById("clock");
    if (!el) return;
    const elapsed = st.elapsed + (performance.now() - receivedAt) / 1000;
    el.textContent = clock(st.tempo ? st.tempo - elapsed : elapsed);
  };
  tick();
  clockTimer = setInterval(tick, 500);
}

async function finish(rep, ctx) {
  if (!rep) {
    return show([BLANK, ln("  Nenhuma resposta, nada foi salvo."), ...backLines()], "tabuada", { enter: "menu" }, { menu });
  }
  // deixa o último feedback aparecer antes do relatório
  show([BLANK, ...ctx.log.slice(-6)], "tabuada treinar");
  await new Promise((r) => setTimeout(r, 900));
  report(rep, new Set(), rep.id);
}

// ---------- relatório ----------

const GROUPS = [
  ["t", "Tempo", "velocidade, mais demoradas, contas lentas"],
  ["e", "Erros e pulos", ""],
  ["d", "Por tabela", "acerto e tempo de cada tabela"],
  ["c", "Comparação", "sessão anterior, sua média, recordes"],
];

const groupHeader = (name) => ln("  ", sp("c", `── ${name} ` + "─".repeat(Math.max(4, 56 - name.length - 4))));

function summaryLines(rep) {
  const s = rep.summary, rec = rep.recommendation;
  let text = rec.text;
  if (rec.facts.length) text += ", com foco em " + rec.facts.map(([a, b]) => fact(a, b)).join(" e ");
  return [
    BLANK,
    ln("  ", sp("b", "RELATÓRIO"), " ", sp("d", `· ${when(rep.started)} · ${rep.config_desc}${rep.interrupted ? " · interrompida" : ""}`)),
    BLANK,
    ln("    Acertos ", `<span class="g b">${s.ok}</span>`, "    Erros ", `<span class="r b">${s.errors}</span>`,
      "    Pulos ", sp("b", s.skipped), "     ", sp("b", s.pct + "%"), " de acerto"),
    ln("    Duração ", sp("b", durationText(s.duration_ms)),
      s.delta_pct !== null ? "     " + signed(s.delta_pct, 0, false, " pp") + " " + sp("d", "em relação à sessão anterior") : ""),
    BLANK,
    ln("    Próximo passo: ", esc(text)),
    ln("    ", sp("c", rec.command)),
  ];
}

function timeLines(rep) {
  const t = rep.time;
  const out = [BLANK, groupHeader("Tempo"), BLANK];
  if (!t.fastest) return out.concat(ln("    Nenhuma resposta cronometrada."));
  out.push(
    ln("    Média ", sp("b", secs(t.mean)), "    Mediana ", sp("b", secs(t.median))),
    ln("    Mais rápida ", sp("g", secs(t.fastest.ms, 7)), "  ", sp("d", fact(t.fastest.a, t.fastest.b))),
    ln("    Mais lenta  ", sp("y", secs(t.slowest.ms, 7)), "  ", sp("d", fact(t.slowest.a, t.slowest.b))),
    BLANK, ln("    ", sp("c", "Respostas mais demoradas")),
  );
  for (const a of t.top) {
    const slow = t.slow_threshold && a.ms > t.slow_threshold;
    const took = slow ? sp("y", secs(a.ms, 6)) : esc(secs(a.ms, 6));
    if (a.skipped) out.push(ln("    ", esc(rpad(fact(a.a, a.b), 13)), sp("d", rpad("pulou", 11)), took));
    else out.push(ln("    ", esc(rpad(`${fact(a.a, a.b)} = ${a.resp}`, 13)), a.ok ? icon("ok", "g") : icon("err", "r"), " ".repeat(10), took));
  }
  out.push(BLANK, ln("    ", sp("c", "Sabe, mas ainda devagar"), " ",
    sp("d", `(acertou em mais de ${secs(t.slow_threshold)})`)));
  if (t.slow_ok.length) {
    const items = t.slow_ok.slice(0, 6).map((a) => `${esc(fact(a.a, a.b))}  ${sp("y", secs(a.ms))}`);
    for (let i = 0; i < items.length; i += 3) out.push(ln("    ", items.slice(i, i + 3).join("     ")));
  } else out.push(ln("    ", sp("d", `Nenhuma. Todos os acertos saíram em até ${secs(t.slow_threshold)}.`)));
  if (t.delta_mean !== null) {
    out.push(BLANK, ln("    Tempo médio ", signed(t.delta_mean / 1000, 1, true, " s"), " ", sp("d", "em relação à sessão anterior")));
  }
  return out;
}

function errorLines(rep) {
  const out = [BLANK, groupHeader("Erros e pulos"), BLANK];
  if (!rep.errors.length) return out.concat(ln("    ", sp("g", "Nenhum erro nesta sessão.")));
  for (const a of rep.errors) {
    if (a.skipped) out.push(ln("    ", esc(rpad(fact(a.a, a.b), 13)), sp("d", "pulou"), "  ", sp("g", lpad(a.right, 3)), "   ", esc(secs(a.ms, 6))));
    else out.push(ln("    ", esc(fact(a.a, a.b)), " = ", sp("r", lpad(a.resp, 3)), "   certo: ", sp("g", lpad(a.right, 3)), "   ", esc(secs(a.ms, 6))));
  }
  return out;
}

function tableLines(rep) {
  const out = [BLANK, groupHeader("Por tabela"), BLANK, ln("    ", sp("d", rpad("tabela", 22) + "acerto   tempo médio"))];
  for (const r of rep.tables) {
    const filled = Math.round((16 * r.pct) / 100);
    out.push(ln("    ", lpad(r.t, 2), "   ", sp(r.worst ? "y" : "g", "█".repeat(filled)), sp("d", "░".repeat(16 - filled)),
      "   ", lpad(r.pct + "%", 4), "      ", secs(r.mean, 6), r.worst ? "   " + sp("y", "← mais fraca") : ""));
  }
  return out;
}

function compareLines(rep) {
  const c = rep.compare;
  const out = [BLANK, groupHeader("Comparação"), BLANK];
  if (!c.prev) out.push(ln("    ", sp("d", "Primeira sessão. A comparação aparece a partir da próxima.")));
  else {
    for (const [label, ref] of [["Sessão anterior", c.prev], ["Sua média", c.avg]]) {
      out.push(ln("    ", esc(rpad(label, 17)), " acerto ", signed(c.pct - ref.pct, 0, false, " pp"), " ",
        sp("d", `(${Math.round(ref.pct)}% → ${c.pct}%)`), "   tempo médio ",
        ref.mean ? signed((c.mean - ref.mean) / 1000, 1, true, " s") : "-"));
    }
  }
  out.push(BLANK, ln("    Melhor sequência: ", sp("b", c.best_streak), " acertos seguidos ",
    c.new_record ? sp("g", "novo recorde!") : c.prev ? sp("d", `(seu recorde: ${c.record_streak})`) : ""));
  return out;
}

const GROUP_RENDER = { t: timeLines, e: errorLines, d: tableLines, c: compareLines };

function report(rep, opened, savedId) {
  const lines = summaryLines(rep);
  for (const [k] of GROUPS) if (opened.has(k)) lines.push(...GROUP_RENDER[k](rep));
  lines.push(BLANK, HR);
  if (!opened.size) lines.push(ln("  Quer ver mais?"));
  const nErr = rep.errors.length;
  for (const [k, label, hint0] of GROUPS) {
    if (opened.has(k)) { lines.push(ln("    ", btn(k, "Ocultar " + label.charAt(0).toLowerCase() + label.slice(1), "g" + k))); continue; }
    const hint = k === "e" ? (nErr ? `${nErr} ${nErr === 1 ? "conta" : "contas"}, com a resposta certa` : "nenhum nesta sessão") : hint0;
    lines.push(ln("    ", btn(k, label, "g" + k, hint, 16)));
  }
  const all = opened.size === GROUPS.length;
  lines.push(ln("    ", btn("x", all ? "Ocultar tudo" : "Mostrar tudo", "gx")));
  lines.push(ln("    ", btn("Enter", "Sair", "menu")));
  if (savedId) lines.push(BLANK, ln("  ", sp("d", `Sessão salva no histórico (#${savedId}).`)));
  const toggle = (k) => () => {
    const next = new Set(opened);
    if (k === "x") { if (all) next.clear(); else GROUPS.forEach(([g]) => next.add(g)); }
    else if (next.has(k)) next.delete(k); else next.add(k);
    report(rep, next);
  };
  const actMap = { menu };
  const keyMap = { enter: "menu" };
  for (const k of ["t", "e", "d", "c", "x"]) { actMap["g" + k] = toggle(k); keyMap[k] = "g" + k; }
  show(lines, "tabuada relatorio", keyMap, actMap);
}

// ---------- histórico ----------

async function history() {
  const data = await api("/api/history");
  const rows = data.rows;
  const lines = [BLANK, ln("  ", sp("b", "HISTÓRICO")), BLANK];
  if (!rows.length) {
    lines.push(ln("  Nenhuma sessão ainda. Comece pelo menu, opção 1."));
    return show(lines.concat(backLines()), "tabuada historico", { enter: "menu" }, { menu });
  }
  lines.push(ln("  ", sp("d", "  #  Data          Tabelas   Modo            Perg.  Acerto  Tempo médio")));
  const actMap = { menu };
  for (const r of rows) {
    const color = r.pct >= 80 ? "g" : r.pct >= 60 ? "y" : "r";
    actMap["s" + r.id] = async () => {
      const res = await api("/api/report?id=" + r.id);
      report(res.report, new Set());
    };
    lines.push(`<button class="opt row" data-act="s${r.id}"><div class="ln">  ${lpad(r.id, 3)}  ${rpad(when(r.started, false), 12)}  ${esc(rpad(r.tabelas.slice(0, 9), 9))} ${esc(rpad(r.mode, 15))} ${lpad(r.total, 5)}  ${sp(color, lpad(r.pct + "%", 6))}  ${secs(r.mean, 11)}${r.interrupted ? "  " + sp("d", "interrompida") : ""}</div></button>`);
  }
  const parts = [`${rows.length} ${rows.length === 1 ? "sessão" : "sessões"}`];
  if (data.streak > 1) parts.push(`${data.streak} dias seguidos treinando`);
  lines.push(BLANK, ln("  ", sp("d", parts.join(" · "))), BLANK, ln("  ", sp("d", "Clique numa sessão para ver o relatório.")));
  show(lines.concat(backLines()), "tabuada historico", { enter: "menu" }, actMap);
}

// ---------- estatísticas ----------

function sparkline(values) {
  const chars = "▁▂▃▄▅▆▇█";
  if (!values.length) return "";
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  return values.map((v) => chars[Math.round(((v - lo) / span) * 7)]).join("");
}

async function stats(mode) {
  const st = await api("/api/stats?modo=" + mode);
  const lines = [BLANK];
  if (!st.sessions) {
    lines.push(ln("  Nenhuma sessão ainda. Comece pelo menu, opção 1."));
    return show(lines.concat(backLines()), "tabuada stats", { enter: "menu" }, { menu });
  }
  lines.push(ln("  ", sp("b", "ESTATÍSTICAS"), " ", sp("d", `· ${st.sessions} sessões · ${st.answers} respostas · desde ${when(st.since, false).slice(0, 5)}`)), BLANK);
  const legend = mode === "tempo"
    ? [["l1", "até 2 s"], ["l2", "2–4 s"], ["l3", "4–8 s"], ["l4", "mais de 8 s"], ["l0", "nunca vista"]]
    : [["l1", "até 2 s"], ["l2", "2–4 s"], ["l3", "mais de 4 s"], ["l4", "erra"], ["l0", "nunca vista"]];
  lines.push(mode === "tempo" ? ln("  ", sp("c", "Tempo médio por conta"))
    : ln("  ", sp("c", "Domínio por conta"), " ", sp("d", "(como você respondeu nas últimas 3 vezes)")));
  lines.push(ln("  ", legend.map(([c, t]) => `${sp(c + " cell", "██")} ${esc(t)}`).join("  ")), BLANK);
  let head = "     ";
  for (let j = 1; j <= 12; j++) head += lpad(j, 2) + " ";
  lines.push(ln(sp("d", head)));
  st.grid.forEach((row, i) => lines.push(ln(sp("d", lpad(i + 1, 4)), " ", row.map((lv) => sp(`l${lv} cell`, "██")).join(" "))));
  const tp = st.trend_pct, tm = st.trend_mean.filter(Boolean);
  lines.push(BLANK, ln("  ", sp("c", "Evolução"), " ", sp("d", `(últimas ${tp.length} sessões)`)));
  lines.push(ln("    Acerto        ", sp("g", sparkline(tp)), `   ${tp[0]}% → `, sp("b", tp[tp.length - 1] + "%")));
  if (tm.length) lines.push(ln("    Tempo médio   ", sp("y", sparkline(tm)), `   ${secs(tm[0])} → `, sp("b", secs(tm[tm.length - 1]))));
  lines.push(BLANK);
  if (st.best_table) {
    lines.push(ln("  ", sp("c", "Por tabela"), "     ", sp("d", "melhor"), ` ${st.best_table.t} `, sp("g", `(${st.best_table.pct}%)`),
      "   ", sp("d", "pior"), ` ${st.worst_table.t} `, sp("r", `(${st.worst_table.pct}%)`)));
  }
  lines.push(ln("  ", sp("c", "Constância"), `     ${st.streak} ${st.streak === 1 ? "dia seguido" : "dias seguidos"} `, sp("d", `· recorde ${st.streak_record}`)));
  lines.push(ln("  ", sp("c", "Tempo total"), `    ${durationText(st.total_ms)} treinando`));
  const other = mode === "tempo" ? "dominio" : "tempo";
  show(lines.concat(backLines([ln("    ", btn("m", `Mostrar a grade por ${other === "tempo" ? "tempo médio" : "domínio"}`, "mode"))])),
    "tabuada stats", { enter: "menu", m: "mode" }, { menu, mode: () => stats(other) });
}

// ---------- pontos fracos ----------

async function weak() {
  const wk = await api("/api/weak?n=10");
  const lines = [BLANK, ln("  ", sp("b", "PONTOS FRACOS"), " ", sp("d", "· contas que ainda não são automáticas")), BLANK];
  if (!wk.rows.length) {
    lines.push(ln("  Nenhum ponto fraco por enquanto. Treine mais algumas sessões para aparecer aqui."));
    return show(lines.concat(backLines()), "tabuada fracos", { enter: "menu" }, { menu });
  }
  const color = { erra: "r", pensa: "y", hesita: "y" };
  const review = (r) => r.due ? sp("c", "agora") : r.review_in === 0 ? "hoje" : r.review_in === 1 ? "amanhã" : `em ${r.review_in} dias`;
  lines.push(ln("  ", sp("d", "      Conta     Vistas  Erros  Tempo típico  Motivo   Revisão")));
  wk.rows.forEach((r, i) => {
    const reason = r.reasons[0], c = color[reason];
    lines.push(ln("   ", lpad(i + 1, 2), "   ", esc(rpad(fact(r.a, r.b), 9)), " ", lpad(r.seen, 6), "  ",
      r.errors ? sp("r", lpad(r.errors, 5)) : lpad(r.errors, 5), "  ",
      reason !== "erra" ? sp(c, secs(r.ms, 12)) : secs(r.ms, 12), "   ",
      sp(c, rpad(reason, 6)), "   ", review(r)));
  });
  lines.push(BLANK,
    ln("  ", sp("d", `erra = errou   pensa = acertou em mais de ${secs(wk.slow_ms)}   hesita = de ${secs(wk.fast_ms).replace(" s", "")} a ${secs(wk.slow_ms)}`)),
    ln("  ", sp("d", `Revisão: repetição espaçada. Acertar em até ${secs(wk.fast_ms)} adia a próxima revisão;`)),
    ln("  ", sp("d", "errar, pensar ou hesitar traz a conta de volta antes.")));
  const cfg = Object.assign({}, home.config, { foco: true });
  show(lines.concat(backLines([ln("    ", btn("f", "Treinar as contas com revisão vencida", "focus"))])),
    "tabuada fracos", { enter: "menu", f: "focus" }, { menu, focus: () => startTraining(cfg) });
}

menu().catch((e) => { screen.innerHTML = ln("  ", sp("r", e.message)); });
