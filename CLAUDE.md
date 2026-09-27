# tabuada

CLI em Python para treinar tabuada até 12×12, com relatório por sessão, histórico e modo web (`--web`). Repo público: https://github.com/weslleycabral/tabuada. Público-alvo: usuários experientes e não experientes em CLI, em macOS, Linux e Windows.

## Regras do projeto

- **Só biblioteca padrão.** Nada de dependências externas (nem colorama, rich etc.). Python ≥ 3.8; o Mac do dono usa 3.9, então sem `X | None`, `match` etc.
- **Tudo tem dois caminhos:** menu interativo (`tabuada` sem argumentos) e flags. Funcionalidade nova entra nos dois, e o menu/assistente mostra o comando equivalente para ensinar as flags.
- **Texto da interface em português do Brasil**, números com vírgula decimal (`5,8 s`).
- **Resposta sem Enter:** na sessão, a resposta vai sozinha quando é a certa ou já tem o máximo de dígitos da conta (`drill.answer_complete`: dígitos de a + dígitos de b); Enter manda respostas mais curtas. `q`, `p` e `a` agem na hora. No terminal isso usa leitura tecla a tecla (`term.keys`/`read_key`: termios ou msvcrt); sem TTY, cai no `input()` com Enter.
- **O tempo de cada resposta é sempre gravado**, em qualquer modo e sem limite. O tempo gasto apertando `a` (mostrar/ocultar atalhos) não conta.
- **Relatório progressivo:** ao fim da sessão aparece só o resumo e a recomendação; os grupos (`t` tempo, `e` erros, `d` por tabela, `c` comparação, `x` tudo) abrem por tecla. Não voltar a despejar tudo de uma vez.
- **A UI do mockup é a referência visual** (paleta em `term.PALETTE` e `web/app.css`). No terminal a fonte é a do usuário; o modo web traz a fonte JetBrains Mono e ícones SVG no pacote, sem requisições externas.
- **Tela fixa, sem rolar histórico:** no terminal, cada tela (menu, assistente, pergunta, relatório) limpa e substitui a anterior. O menu roda na tela alternativa (`term.screen()`, como vim/less) e restaura o terminal ao sair; a sessão também, e pelas flags o relatório final é impresso depois, no terminal normal, para ficar visível. Sem ANSI, cai no modo rolando.
- **Compatibilidade de terminal:** só símbolos de caixa/bloco e `✓ ✗`; nada de emoji. Todo símbolo novo precisa de equivalente em `term._ASCII`. Cores respeitam `--sem-cor`, `NO_COLOR` e saída não-TTY.

## Arquitetura

Lógica separada de entrada/saída, para o terminal e a web usarem as mesmas regras:

| Arquivo | Papel |
|---|---|
| `tabuada/drill.py` | Regras sem I/O: `Config`, `parse_tabelas`, sorteio (`Drill`), reforço de erros (volta em 3–5 perguntas), pesos do `--foco`, `parse_answer` |
| `tabuada/report.py` | Cálculos puros que devolvem dicts serializáveis: relatório da sessão (`build`), histórico, `stats`, `weak_facts`, `day_streaks` |
| `tabuada/render.py` | Transforma esses dicts em linhas de terminal |
| `tabuada/term.py` | Cores ANSI (truecolor ou 16 cores), ativação de VT no Windows via `ctypes`, fallback ASCII (`_AsciiWriter`) |
| `tabuada/session.py` | Loop da sessão no terminal (barra de atalhos abaixo da pergunta via escapes de cursor) e relatório interativo |
| `tabuada/menu.py` | Menu inicial, assistente de configuração, tela de histórico |
| `tabuada/cli.py` | `argparse` em português; entry point `tabuada.cli:main` |
| `tabuada/storage.py` | `~/.tabuada/history.json` e `config.json` (ou `TABUADA_HOME`), escrita atômica, arquivo corrompido é renomeado |
| `tabuada/webserver.py` + `tabuada/web/` | `http.server` só em `127.0.0.1`, porta livre, checagem de `Host` (anti DNS rebinding); SPA em JS puro que desenha as mesmas telas a partir do JSON de `report.py` |

Uma conta `a×b` e `b×a` é o mesmo fato nas estatísticas (`drill.fact_key`). "Por tabela" no relatório agrupa pelo primeiro fator (a tabela escolhida).

Ao mudar um texto ou formato de tela, mude nos dois lados: `render.py` (terminal) e `web/app.js` (web).

## Comandos

```sh
python3 -m tabuada                       # roda do código
bin/tabuada                              # mesmo, via script (há um link em ~/.local/bin/tabuada)
python3 -m unittest discover -s tests    # testes
TABUADA_HOME=/tmp/x python3 -m tabuada   # testar sem mexer no histórico real
```

Para testar a sessão com TTY de verdade (cursor, cores), usar `pty.fork()` em Python; `script` não funciona no sandbox.

## Commits

Todo commit segue o padrão de mercado **Conventional Commits** (https://www.conventionalcommits.org):

- Título `tipo(escopo opcional): resumo`, no imperativo, em português, até ~72 caracteres, sem ponto final. Tipos: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `style`, `build`, `ci`.
- Corpo obrigatório, separado por linha em branco, com o detalhe do que foi alterado e por quê: uma linha por mudança relevante, citando os arquivos/módulos afetados e o efeito para o usuário.
- Mudança incompatível: `!` após o tipo e rodapé `BREAKING CHANGE: ...`.
- Um assunto por commit; mudanças não relacionadas vão em commits separados.

## Pontos conhecidos

- O `pip` 21.2 que vem com o Python da Apple instala o pacote como "UNKNOWN". Com `pipx` ou `pip` atualizado funciona; o README recomenda `pipx`.
- Não foi testado em Windows real, só em macOS.
- A fonte em `web/fonts/` é JetBrains Mono 2.304 (OFL, `OFL.txt` junto).
