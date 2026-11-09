---
name: ronda
description: Faz a ronda do Radar Anti-Guru agora (coleta do YouTube, busca na web, filtro anti-guru) e abre o painel. Use quando a pessoa digitar /radar:ronda, pedir a ronda, o boletim ou "o que tem de novo no nicho".
user-invocable: true
---

# /radar:ronda

Motor: `${CLAUDE_PLUGIN_ROOT}/radar/radar.py` (rode com `python`, ou `python3` no Mac/Linux). Se não houver configuração, mande rodar `/radar:configurar` primeiro.

1. **Coletar** (uns 3 a 5 minutos, só YouTube): `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" coletar`. Se já houver coleta de hoje em `coletas/`, pule. Se falhar inteira, siga assim mesmo: a análise faz a ronda só com a web.
2. **Pegar o pedido:** `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" pedido`. Ele imprime as instruções da análise já com o nicho da pessoa e o caminho do arquivo a gravar. Se a pessoa pedir a revisão da semana, acrescente `--semanal`.
3. **Fazer a análise você mesmo**, seguindo o pedido à risca: ler a coleta e as fichas, fazer as buscas na web (WebSearch/WebFetch), descrever cada fonte **sem dar nota** e gravar o JSON no caminho indicado. A nota é do programa. Nunca dê nota, nunca troque a situação de uma ficha à mão e nunca invente fonte ou link.
4. **Aplicar:** `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" aplicar "<caminho do json que você gravou>"`, e depois `abrir`.
5. **Responder em até 6 linhas:** o boletim do dia, quantas fichas ficaram ✅/🟢, e o papo de guru que apareceu (🚩). Termine dizendo que o painel abriu no navegador.

Se o arquivo de saída de hoje já existir em `mudancas/`, pergunte se ela quer refazer ou só abrir o painel.
