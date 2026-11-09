---
name: checar
description: Checa se as informações de um vídeo são verdade (YouTube, TikTok, Instagram, X, Kwai, Facebook e o que mais o yt-dlp abrir) com o filtro anti-guru do Radar. Use quando a pessoa digitar /radar:checar <link>, colar um link de vídeo perguntando se é verdade, se é golpe ou se o autor é guru.
user-invocable: true
argument-hint: <link do vídeo>
---

# /radar:checar <link>

Motor: `${CLAUDE_PLUGIN_ROOT}/radar/radar.py` (rode com `python`, ou `python3` no Mac/Linux). Funciona mesmo sem `/radar:configurar`. Se não vier link, peça um.

## 1. Ler o vídeo
`python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" link "<link>"`

O comando imprime um resumo (plataforma, autor, seguidores, bandeiras de guru marcadas pela regra fixa) e o caminho de dois arquivos: `arquivo` (o vídeo lido, com a descrição e o `texto` falado) e `mudancas` (onde você vai gravar a análise).
- `erro` com dica de login (comum no Instagram): pergunte em qual navegador a pessoa está logada naquela rede e repita com `--navegador firefox` (ou `chrome`, `edge`, `brave`). Esses são os cookies do próprio computador dela e não saem dali. O Chrome no Windows às vezes não deixa ler: nesse caso, sugira o Firefox.
- `falta` dizendo que a transcrição não está instalada: explique que o vídeo não tem legenda e que, pra ouvir o que é dito, o Radar precisa instalar a transcrição (faster-whisper, uns 500 MB contando o modelo). Com o ok, rode `checar --whisper` e repita o `link`. Sem o ok, siga só com título e descrição e avise que a checagem ficou parcial.
- Primeira transcrição: o modelo baixa sozinho, e um vídeo de 10 minutos pode levar alguns minutos no processador. Avise antes.

## 2. Separar as afirmações
Leia o `arquivo` inteiro, principalmente `texto` e `descricao`. Tire de 3 a 6 **afirmações conferíveis**: números, regras, promessas de resultado, "a plataforma X faz Y", "o método dá Z". Ignore opinião e frase motivacional. Inclua sempre a promessa principal do vídeo, se houver.

Pra cada uma, procure primeiro em `fichas.json`, na pasta de dados (o caminho está no `arquivo`, duas pastas acima de `links/`). Se a ficha já existir, use o mesmo `id`.

## 3. Conferir na web
Faça de 4 a 12 buscas (WebSearch; WebFetch pra abrir a fonte oficial). Pra cada afirmação, procure a fonte oficial (órgão, regra da plataforma, documentação), imprensa séria e relatos independentes, **a favor e contra**. Confira também o autor: se vende curso, mentoria, sinal ou afiliado (link na bio, descrição, site), e se tem resultado próprio conferível.

## 4. Descrever as fontes, sem dar nota
Siga as regras das seções 3 e 4 de `${CLAUDE_PLUGIN_ROOT}/radar/ronda.md` (tipo, prova, interesse, bandeiras, posição). **O próprio vídeo entra como fonte `a_favor` de cada afirmação dele**, com o tipo e as bandeiras que ele merece. A regra fixa já marcou algumas bandeiras: confira e acrescente as que a fala mostra (print de faturamento, "link na bio", "vagas limitadas"). Fonte que desmente vai como `posicao: contra`. **Afirmação que é conta** (juros, renda, views × RPM): mande a fonte `tipo: calculo` descrita no `ronda.md`, e o programa refaz a conta. Nunca deixe uma conta só com o vídeo como fonte. A nota e o veredito são do programa: nunca escreva veredito por conta própria e nunca invente fonte.

## 5. Gravar e aplicar
Grave no caminho `mudancas` o mesmo formato da seção 6 do `ronda.md` (`fichas`, `vendedores`, `buscas`), mais:
```json
"link": {"url": "<url do resumo>", "autor": "<autor do resumo>", "arquivo": "<arquivo do resumo>"}
```
Depois rode:
- `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" aplicar "<mudancas>"`
- `python "${CLAUDE_PLUGIN_ROOT}/radar/radar.py" veredito "<mudancas>"`

## 6. Responder (curto)
Use só o que o `veredito` imprimiu:
- Primeira linha: o vídeo em uma frase e quem é o autor (e, se for o caso, o que ele vende).
- Uma linha por afirmação: a situação (✅ 🟢 ⚖️ ⚪ ❌ 🚩), a afirmação curta e a melhor fonte, com link.
- Uma linha final de conclusão, contando quantas afirmações foram ❌/🚩 e quantas ✅/🟢. Termine com: "Nota da conta fixa, não da opinião da IA. Detalhes no painel (`abrir`)."

Se a transcrição faltou ou a busca não achou nada sobre uma afirmação, diga isso: ⚪ fraco quer dizer "não deu pra confirmar", não "é mentira".
