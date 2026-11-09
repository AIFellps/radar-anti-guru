---
name: configurar
description: Configura o Radar Anti-Guru para o nicho da pessoa (perguntas, canais do YouTube, buscas, fontes oficiais). Use quando a pessoa digitar /radar:configurar, instalar o radar pela primeira vez ou quiser trocar de nicho.
user-invocable: true
---

# /radar:configurar

Você vai montar a configuração do Radar Anti-Guru conversando com a pessoa. Ela não precisa editar nenhum arquivo.

O motor fica em `${CLAUDE_PLUGIN_ROOT}/radar/radar.py`. Rode-o com `python` (no Mac/Linux, `python3` se `python` não existir). Os dados ficam em `~/radar-anti-guru/`, a menos que a variável `RADAR_PASTA` diga outra pasta.

## 1. Conferir o computador
Rode `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" checar`.
- `python_ok` false → peça pra instalar o Python 3.9+ (python.org; no Windows, marcar "Add to PATH") e pare aqui.
- `yt_dlp` false → diga que vai instalar o yt-dlp (o leitor do YouTube) e rode `checar --instalar`.
- `config` true → já existe configuração. Pergunte se ela quer trocar de nicho (aí apague só o `config.json` depois do ok) ou só ajustar (aí leia e edite).

## 2. Conversar (curto, uma pergunta por vez)
1. **Qual é o nicho?** Peça uma frase ("finanças pra iniciante", "canal dark no YouTube", "marketing de afiliado", "academia pra iniciantes").
2. **Quem é você nesse nicho e o que quer saber?** Ofereça 3 ou 4 sugestões prontas, adaptadas ao nicho: regras, ferramentas, o que funciona, golpes.
3. **Tem canal ou perfil no YouTube?** Se tiver, ele entra em `meus_canais` (o radar mede os números dele também). Pode pular.
4. **Quem você acompanha?** Canais de referência. Se ela não souber, proponha você mesmo.

Exemplos prontos em `${CLAUDE_PLUGIN_ROOT}/exemplos/` (`canal-dark.json`, `financas.json`). Use como molde de formato. Se o nicho for um deles, ofereça começar por ele.

## 3. Montar a lista de canais
Use `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" achar-canal "nome ou assunto"` pra achar o id de cada canal: confira nome e inscritos, e nunca invente id. Monte três grupos:
- `educadores` (3 a 5): quem ensina sobre o nicho. `vende: true` se a pessoa vende curso, mentoria ou afiliado sobre o próprio assunto (isso deixa a nota dela mais baixa).
- `radar` (5 a 15): canais do nicho que você quer medir. O radar mostra qual vídeo estourou acima da mediana do próprio canal. Misture tamanhos (pequeno estourando é o sinal mais útil). Use `grupo` pra rotular (ex.: `financas-pt`).
- `meus_canais`: os da pessoa, se houver.
Cada canal leva `idioma` (`pt`, `en`...).

## 4. Buscas e fontes
- `buscas_youtube`: 6 a 12 pares `["idioma", "busca"]`, do jeito que alguém do nicho procuraria. Inclua 1 ou 2 com cara de guru ("renda passiva", "ganhar dinheiro com X"): é assim que o radar pega o papo ruim pra mostrar como barulho.
- `buscas_web`: 4 a 8 buscas pro Google (Reddit com `site:reddit.com r/...`, X com `site:x.com`, notícias, órgão oficial).
- `fontes_oficiais`: quem fala com autoridade no nicho: órgão regulador, documentação da plataforma, política oficial. Só ponha URL que você conferiu.
- `temas`: 5 a 7 temas curtos em minúsculas pra agrupar as fichas, sempre com `regras` se o nicho tiver regras (fichas de regras não vencem).
- `bandeiras_extras` (opcional): golpes típicos do nicho que a lista padrão não pega, como `{"nome": "regex em minúsculas"}`. Exemplo de finanças: `"garantido": "lucro garantido|sem risco|\\d+\\s?% ao m[eê]s"`.

## 5. Gravar e testar
Grave `config.json` na pasta de dados (veja o caminho em `checar`), com estes campos: `nicho`, `quem_sou`, `o_que_quero_saber` (lista), `idiomas`, `temas`, `buscas_youtube`, `buscas_web`, `fontes_oficiais`, `educadores`, `radar`, `meus_canais`, `bandeiras_extras`, `modelo` ("sonnet"), `modelo_semanal` ("opus"), `semanal_no_domingo` (true).

Rode `validar` e corrija o que ele apontar. Depois rode `coletar` (uns 3 a 5 minutos, sem gastar Claude) e conte quantos vídeos vieram e se houve erro. Canal com erro: confira o id com `achar-canal`.

Termine dizendo em 3 linhas o que ficou configurado. Ofereça a primeira ronda agora (`/radar:ronda`) e a ronda automática todo dia (`/radar:agendar`).
