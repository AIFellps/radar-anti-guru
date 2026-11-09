---
name: agendar
description: Liga ou desliga a ronda automática diária do Radar Anti-Guru (Agendador do Windows ou crontab no Mac/Linux). Use quando a pessoa digitar /radar:agendar ou pedir pro radar rodar sozinho todo dia.
user-invocable: true
---

# /radar:agendar

Motor: `${CLAUDE_PLUGIN_ROOT}/radar/radar.py` (rode com `python`, ou `python3` no Mac/Linux).

1. Confira se há configuração e se o Claude Code foi achado: `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" checar`. Se `claude` vier vazio, explique que a ronda automática chama o Claude Code sozinha e precisa do comando `claude` instalado (https://docs.claude.com/claude-code). Sem ele, só a ronda manual (`/radar:ronda`) funciona.
2. Pergunte o horário (padrão 05:00, quando o PC costuma estar parado) e avise antes de criar:
   - A ronda usa o plano do Claude Code da pessoa: Sonnet nos dias comuns e Opus na revisão de domingo (dá pra trocar em `modelo` e `modelo_semanal` no `config.json`). Cada ronda gasta mais ou menos o mesmo que uma conversa média de pesquisa.
   - No Windows, se o PC estiver desligado no horário, ela roda quando ligar. No Mac/Linux (crontab), o computador precisa estar ligado.
3. Com o ok: `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" agendar --hora HH:MM`.
4. Pra desligar: `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" desagendar`.
5. Pra saber como foi a última ronda automática: `status` (mostra o fim do registro do dia).

Diga em 2 linhas o que ficou ligado. O painel atualizado fica em `painel.html`, na pasta de dados, e abre com `abrir`.
