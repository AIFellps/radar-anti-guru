---
name: perguntar
description: Responde perguntas sobre o nicho usando só o que o Radar Anti-Guru já confirmou, com fonte e nota. Use quando a pessoa digitar /radar:perguntar ou perguntar "o que o radar sabe sobre X", "isso é verdade?", "esse cara é guru?".
user-invocable: true
---

# /radar:perguntar

A base fica na pasta de dados do radar (`~/radar-anti-guru/`, ou a da variável `RADAR_PASTA`): `fichas.json` (cada ficha tem `afirmacao`, `situacao`, `nota`, `autores`, `ultimo_visto`, `fontes`) e `vendedores.json`.

1. Leia `fichas.json` e `vendedores.json` e procure o que responde a pergunta.
2. **Responda sempre com a situação e a data:** "🟢 provável (3 autores, visto em 05/11): ...". Nada de "a comunidade diz" sem fonte. Cite 1 ou 2 fontes com link.
   - ✅ confirmado e 🟢 provável: pode orientar.
   - ⚖️ em disputa: mostre os dois lados.
   - ⚪ fraco: diga que ainda não dá pra confiar.
   - 🚩 barulho: diga que é papo de guru e por quê (as bandeiras das fontes).
3. Separe o que é **dado** (fontes `tipo: dado`, números medidos pelo radar) do que é **conversa**.
4. Se a pergunta é sobre uma pessoa ou um canal, procure o nome em `vendedores.json` e nas fontes (`tipo: vendedor`, `interesse: true`, bandeiras).
5. **Se a base não sabe**, diga isso claramente, sem completar com o que você acha. Depois guarde a pergunta pra próxima ronda: `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" perguntar "<pergunta curta>"`. Se ela quiser a resposta agora, ofereça `/radar:ronda`: a pergunta entra com prioridade.
