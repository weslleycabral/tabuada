# tabuada

Treino de tabuada até 12×12 no terminal, com relatório de cada sessão e histórico de evolução. Também abre no navegador com a mesma interface.

- Mede o tempo de cada resposta, para mostrar as contas que você acerta mas ainda demora.
- Contas erradas voltam 3 a 5 perguntas depois.
- Com `--foco`, as contas que você mais erra ou demora aparecem mais.
- Funciona em macOS, Linux e Windows. Precisa só do Python 3.8+, sem dependências.

## Instalação

```sh
pipx install git+https://github.com/weslleycabral/tabuada
```

Sem pipx: `pip install --user git+https://github.com/weslleycabral/tabuada`

Para rodar sem instalar, a partir do código:

```sh
git clone https://github.com/weslleycabral/tabuada
cd tabuada
python3 -m tabuada
```

## Uso

### Menu interativo

```sh
tabuada
```

O menu guia a configuração passo a passo. No fim, ele mostra o comando equivalente para você pular o menu da próxima vez.

### Comandos

```sh
tabuada treinar                        # repete a última configuração
tabuada treinar -n 30 --tabelas 7,8    # 30 perguntas das tabelas 7 e 8
tabuada treinar --tabelas 2-9 --foco   # mais perguntas nos seus pontos fracos
tabuada treinar --tempo 120            # contra-relógio de 2 minutos
tabuada relatorio                      # relatório da última sessão
tabuada relatorio --sessao 11 --tempo  # grupo de tempo da sessão 11
tabuada historico                      # sessões anteriores
tabuada stats                          # grade 12×12 e evolução
tabuada fracos                         # contas com mais erros ou mais lentas
tabuada reset                          # apaga o histórico
```

Cada comando tem a própria ajuda: `tabuada treinar --help`.

### Durante a sessão

| Tecla | Ação |
|---|---|
| `q` | sai e mostra o relatório |
| `p` | pula a pergunta |
| `a` | mostra ou oculta a barra de atalhos |
| Ctrl+C | igual a `q` |

### Relatório

No fim da sessão aparece só o resumo e a recomendação do próximo treino. O resto abre por tecla:

- `t`: tempo (média, mediana, respostas mais demoradas, contas lentas)
- `e`: erros e pulos, com a resposta certa
- `d`: acerto e tempo por tabela
- `c`: comparação com a sessão anterior, com sua média e com seus recordes
- `x`: abre todos os grupos

## Navegador

```sh
tabuada --web
```

Abre as mesmas telas no navegador. O servidor roda só no seu computador (`127.0.0.1`). A fonte e os ícones vêm dentro do pacote, então a aparência é a mesma em qualquer sistema. O histórico é o mesmo do terminal.

## Terminal

No terminal, a fonte é a que você configurou nele. As cores funcionam em terminais modernos, inclusive no Windows 10+.

- `--ascii` troca os símbolos (✓ ✗ █ ─) por caracteres simples, para terminais antigos. Ele é ativado sozinho quando o terminal não aceita UTF-8.
- `--sem-cor` desliga as cores. A variável `NO_COLOR` faz o mesmo.

## Dados

O histórico e as preferências ficam em `~/.tabuada/`. Para usar outra pasta, defina `TABUADA_HOME`.

## Desenvolvimento

```sh
python3 -m unittest discover -s tests
```

Para usar o comando `tabuada` direto do código, sem instalar:

```sh
ln -s "$PWD/bin/tabuada" ~/.local/bin/tabuada
```

## Licença

MIT. A fonte JetBrains Mono (`tabuada/web/fonts/`) é distribuída sob a SIL Open Font License, em `tabuada/web/fonts/OFL.txt`.
