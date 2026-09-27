# tabuada

CLI para treinar tabuada até 12×12, com relatório por sessão e histórico de evolução.

> Em desenvolvimento.

## Requisitos

- Python 3.9+ (sem dependências externas)

## Uso

Modo interativo (menus guiados):

```sh
tabuada
```

Modo flags:

```sh
tabuada treinar -n 20 --tabelas 6,7,8
tabuada treinar --tempo 120 --foco
tabuada relatorio
tabuada historico
tabuada stats
tabuada fracos
tabuada reset
```

Os dados ficam em `~/.tabuada/`.

## Licença

MIT
