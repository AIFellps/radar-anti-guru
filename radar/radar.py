"""Radar Anti-Guru: a ronda diária do que a comunidade de um nicho anda falando, com o papo de guru separado do que tem prova.

A nota de cada informação é de uma conta fixa (ver README, "Como a nota é feita"), nunca da opinião da IA:
a IA só descreve cada fonte (quem é, se vende algo, se mostra prova) e o programa faz a conta.

Rodar:  python radar.py diario       a ronda inteira: coletar, analisar (Claude Code), aplicar e abrir o painel
        python radar.py coletar      só o YouTube (sem gastar Claude)
        python radar.py pedido       imprime o pedido da análise (o /radar:ronda usa isso dentro do Claude Code)
        python radar.py analisar     só a análise, chamando o Claude Code sozinho (é o que a ronda agendada faz)
        python radar.py aplicar [mudancas.json]   refaz a conta e o painel
        python radar.py abrir        abre o painel no navegador
        python radar.py link <url> [--navegador firefox]   lê um vídeo de qualquer rede pra checar (o /radar:checar usa isso)
        python radar.py veredito <mudancas.json>  o que a conta fixa decidiu sobre as afirmações de um link
        python radar.py checar [--instalar] [--whisper]   confere Python, yt-dlp, transcrição e Claude Code
        python radar.py achar-canal "termo"       acha canais do YouTube pra pôr na configuração
        python radar.py exemplo <nome>            copia uma configuração pronta da pasta exemplos/
        python radar.py validar      confere a configuração
        python radar.py perguntar "pergunta"      guarda uma pergunta pra próxima ronda ir atrás
        python radar.py agendar [--hora 05:00] | desagendar
        python radar.py status
Todos aceitam --pasta <caminho> (padrão: ~/radar-anti-guru, ou a variável RADAR_PASTA)."""
import glob
import html
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ_PLUGIN = AQUI.parent
EXEMPLOS = RAIZ_PLUGIN / "exemplos"


def _pasta_dos_dados():
    if "--pasta" in sys.argv:
        i = sys.argv.index("--pasta")
        p = sys.argv[i + 1]
        del sys.argv[i:i + 2]
        return Path(p).expanduser().resolve()
    return Path(os.environ.get("RADAR_PASTA") or Path.home() / "radar-anti-guru").expanduser().resolve()


PASTA = _pasta_dos_dados()
CONFIG = PASTA / "config.json"
FICHAS = PASTA / "fichas.json"
VENDEDORES = PASTA / "vendedores.json"
PERGUNTAS = PASTA / "perguntas.json"
PAINEL = PASTA / "painel.html"
HOJE = date.today().isoformat()
WINDOWS = platform.system() == "Windows"
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ESTA_SEMANA = "EgIIAw%253D%253D"      # filtro "esta semana" da busca do YouTube
SO_CANAIS = "EgIQAg%253D%253D"        # filtro "canais" da busca do YouTube
POR_BUSCA = 15
LEGENDAS = 8                            # vídeos novos com legenda lida por dia
NOME_TAREFA = "Radar Anti-Guru"
SITUACOES = ["confirmado", "provavel", "em_disputa", "fraco", "desmentido", "barulho", "vencido"]
NOME_SITUACAO = {"confirmado": "✅ confirmado", "provavel": "🟢 provável", "em_disputa": "⚖️ em disputa", "fraco": "⚪ fraco",
                 "desmentido": "❌ desmentido", "barulho": "🚩 barulho", "vencido": "⌛ vencido"}
NOME_BANDEIRA = {"renda": "promessa de renda", "facil": "fácil/automático", "segredo": "segredo/urgência",
                 "sem_concorrencia": "sem concorrência", "prova_fraca": "prova fraca", "vende": "vende curso/afiliado",
                 "clone": "manda copiar", "sem_canal": "sem resultado próprio"}


def _ler(arq, padrao):
    return json.loads(Path(arq).read_text(encoding="utf-8")) if Path(arq).exists() else padrao


def _gravar(arq, dado):
    Path(arq).parent.mkdir(parents=True, exist_ok=True)
    Path(arq).write_text(json.dumps(dado, ensure_ascii=False, indent=1), encoding="utf-8")


def config():
    if not CONFIG.exists():
        raise SystemExit(f"Ainda não tem configuração em {CONFIG}. Rode /radar:configurar no Claude Code "
                         f"(ou: python radar.py exemplo canal-dark).")
    return _ler(CONFIG, {})


# ---------------------------------------------------------------- bandeiras de guru (as mesmas em qualquer nicho)
BANDEIRAS = {
    "renda": r"(r\$|us\$|\$|€)\s?\d[\d.,]*\s?(k|mil)?\s*(/|por|a|per)?\s*(m[eê]s|month|mo\b|dia|day|semana|week|ano|yr|year)|\d+\s?k\s?/\s?(month|mo)|\d+\s?k (a|per) (month|day)|\d+ mil (por|ao) (m[eê]s|dia)|6 d[ií]gitos|7 d[ií]gitos|six figures?|seven figures?|ganhar dinheiro|make money|renda passiva|passive income|liberdade financeira|financial freedom",
    "facil": r"autom[aá]tic|1 clique|one click|sem trabalho|no work|passiv|sem aparecer e|easy money|dinheiro f[aá]cil|sem esfor[cç]o|effortless|do zero em \d+ dias",
    "segredo": r"ningu[eé]m fala|ningu[eé]m te conta|segredo|secret|nobody (is )?talking|what they don.?t|prepare now|antes que|before it.?s too late|urgente|vai acabar|they don.?t want you",
    "sem_concorrencia": r"sem concorr[eê]ncia|no competition|untouched|intocad|inexplorad|nova onda|low competition|zero competition|oceano azul|blue ocean",
    "clone": r"clon(ei|ar|ed|e)\b|copi(ei|ar) (um |o )?(canal|perfil|neg[oó]cio)|copy (this|a) (channel|business)|steal (this|my)",
}
VENDE = r"hotmart|kiwify|eduzz|monetizze|braip|perfectpay|skool\.com|gumroad|whop\.com|stan\.store|teachable|kajabi|udemy|/ref[=/]|\?ref=|affiliate|afiliad|mentoria|meu curso|my course|coaching|done.for.you|link na bio|link in bio|cupom|discount code|vagas limitadas|limited spots" \
        r"|bootcamp|our program|nosso programa|minha turma|apply (down )?below|aplica(r)? (aqui )?embaixo|nossos alunos|our students|meus alunos|my students"


def _bandeiras_do_nicho():
    try:
        extra = _ler(CONFIG, {}).get("bandeiras_extras") or {}
    except Exception:
        extra = {}
    return {**BANDEIRAS, **extra}


def bandeiras(texto):
    t = (texto or "").lower()
    return [b for b, r in _bandeiras_do_nicho().items() if re.search(r, t)]


def vende(texto):
    try:
        extra = _ler(CONFIG, {}).get("vende_extras") or ""
    except Exception:
        extra = ""
    return bool(re.search(VENDE + (f"|{extra}" if extra else ""), (texto or "").lower()))


# ---------------------------------------------------------------- YouTube (yt-dlp, sem chave)
def ytdlp(url, *args, tempo=150):
    for tentativa in range(3):                      # pedido demais em seguida dá 403: espera e tenta de novo
        r = subprocess.run([sys.executable, "-m", "yt_dlp", "-J", "--flat-playlist", "--no-warnings", *args, url],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=tempo, creationflags=SEM_JANELA)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
        erro = (r.stderr or "sem resposta").strip()[-300:]
        if "403" not in erro or tentativa == 2:
            raise RuntimeError(erro)
        time.sleep(8 * (tentativa + 1))


def url_canal(cid):
    cid = cid.strip()
    if cid.startswith("http"):
        return cid.rstrip("/") + ("" if cid.rstrip("/").endswith("/videos") else "/videos")
    return f"https://www.youtube.com/{cid}/videos" if cid.startswith("@") else f"https://www.youtube.com/channel/{cid}/videos"


def video(e, **extra):
    return dict({"id": e["id"], "titulo": e.get("title"), "canal": e.get("channel") or e.get("uploader"), "canal_id": e.get("channel_id"),
                 "views": e.get("view_count"), "duracao": e.get("duration"), "quando": e.get("timestamp"),
                 "bandeiras": bandeiras(e.get("title"))}, **extra)


def buscar(idioma, consulta):
    q = urllib.request.quote(consulta)
    d = ytdlp(f"https://www.youtube.com/results?search_query={q}&sp={ESTA_SEMANA}", "--playlist-end", str(POR_BUSCA),
              "--extractor-args", f"youtube:lang={idioma}")
    return [video(e, busca=consulta, idioma=idioma) for e in d.get("entries") or [] if e and e.get("id")]


def ultimos(cid, n, idioma):
    """A data aproximada ("há 2 dias") só sai com o YouTube em inglês, e aí o título vem traduzido quando o canal tem tradução:
    canal de outra língua ganha uma segunda leitura só pelo título original."""
    d = ytdlp(url_canal(cid), "--playlist-end", str(n), "--extractor-args", "youtubetab:approximate_date")
    entradas = [e for e in d.get("entries") or [] if e and e.get("id")]
    if idioma != "en" and entradas:
        try:
            orig = ytdlp(url_canal(cid), "--playlist-end", str(n), "--extractor-args", f"youtube:lang={idioma}")
            titulos = {e["id"]: e.get("title") for e in orig.get("entries") or [] if e and e.get("id")}
            for e in entradas:
                e["title"] = titulos.get(e["id"]) or e.get("title")
        except RuntimeError:
            pass
    return d, [video(e) for e in entradas]


def medir_canal(nome, cid, grupo, idioma):
    """Mediana dos últimos 30 vídeos (sem os de menos de 3 dias, que ainda estão subindo) e os vídeos recentes acima de 3x."""
    d, vs = ultimos(cid, 30, idioma)
    agora = time.time()
    maduros = [v["views"] for v in vs if v.get("views") is not None and (not v.get("quando") or agora - v["quando"] > 3 * 86400)]
    mediana = statistics.median(maduros) if maduros else None
    recentes = [v for v in vs if v.get("quando") and agora - v["quando"] < 21 * 86400]
    for v in recentes:
        v["vezes"] = round(v["views"] / mediana, 1) if mediana and v.get("views") is not None else None
        v["idade_dias"] = round((agora - v["quando"]) / 86400)
    return {"nome": nome, "canal_id": cid, "grupo": grupo, "inscritos": d.get("channel_follower_count"), "mediana": mediana,
            "recentes": recentes, "outliers": [v for v in recentes if (v.get("vezes") or 0) >= 3]}


def vtt_texto(vtt):
    linhas, ultima = [], None
    for l in vtt.splitlines():
        l = re.sub(r"<[^>]+>", "", l).strip()
        if not l or "-->" in l or l.startswith(("WEBVTT", "Kind:", "Language:")) or l.isdigit() or l == ultima:
            continue
        linhas.append(l)
        ultima = l
    return " ".join(linhas)


def detalhe(vid, idiomas):
    """Descrição (pra achar curso e afiliado) e legenda de um vídeo. Legenda na língua original; o yt-dlp baixa com pausa
    (pedir direto ao YouTube, várias de uma vez, dá 429)."""
    import tempfile
    import yt_dlp
    opc = {"quiet": True, "no_warnings": True, "noprogress": True, "skip_download": True, "ignore_no_formats_error": True}
    with yt_dlp.YoutubeDL(opc) as y:
        info = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    texto = ""
    for fonte in ("subtitles", "automatic_captions"):
        subs = info.get(fonte) or {}
        lang = next((l for l in subs if l.endswith("-orig")), None) or next((l for l in subs if l.split("-")[0] in idiomas), None)
        if not lang:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            try:
                with yt_dlp.YoutubeDL(dict(opc, writesubtitles=fonte == "subtitles", writeautomaticsub=fonte == "automatic_captions",
                                           subtitleslangs=[lang], subtitlesformat="vtt", sleep_interval_subtitles=5,
                                           outtmpl=str(Path(tmp) / "sub.%(ext)s"))) as y:
                    y.download([f"https://www.youtube.com/watch?v={vid}"])
                arq = next(Path(tmp).glob("sub*.vtt"), None)
                texto = vtt_texto(arq.read_text(encoding="utf-8", errors="replace")) if arq else ""
            except Exception:
                texto = ""
        if texto:
            break
    desc = info.get("description") or ""
    return {"descricao": desc[:2500], "vende": vende(desc), "bandeiras_desc": bandeiras(desc[:600]), "legenda": texto[:12000],
            "inscritos": info.get("channel_follower_count"), "data": info.get("upload_date")}


def coletar():
    c = config()
    idiomas = c.get("idiomas") or ["pt", "en"]
    vistos_arq = PASTA / "vistos.json"
    vistos = set(_ler(vistos_arq, []))
    foto = {"data": HOJE, "buscas": [], "educadores": [], "radar": [], "meus": [], "erros": []}

    def tenta(rotulo, fn, *a):
        try:
            return fn(*a)
        except Exception as e:
            foto["erros"].append(f"{rotulo}: {e}"[:300])
            return None

    buscas_cfg = [(b[0], b[1]) if isinstance(b, list) else (b.get("idioma", idiomas[0]), b["busca"]) for b in c.get("buscas_youtube", [])]
    with ThreadPoolExecutor(2) as ex:               # a busca do YouTube é a que mais bloqueia: duas por vez
        buscas = list(ex.map(lambda b: tenta(f"busca {b[1]}", buscar, *b), buscas_cfg))
    with ThreadPoolExecutor(4) as ex:
        edu = list(ex.map(lambda e: (e, tenta(f"educador {e['nome']}", ultimos, e["canal"], 6, e.get("idioma", idiomas[0]))),
                          c.get("educadores", [])))
        radar = list(ex.map(lambda r: tenta(f"radar {r['nome']}", medir_canal, r["nome"], r["canal"], r.get("grupo", ""),
                                            r.get("idioma", idiomas[0])), c.get("radar", [])))
        meus = list(ex.map(lambda r: tenta(f"meu canal {r['nome']}", medir_canal, r["nome"], r["canal"], "meu",
                                           r.get("idioma", idiomas[0])), c.get("meus_canais", [])))
    por_id = {}
    for lista in buscas:
        for v in lista or []:
            por_id.setdefault(v["id"], v)
    foto["buscas"] = list(por_id.values())
    limite = time.time() - 14 * 86400
    for e, r in edu:
        if r:
            foto["educadores"] += [dict(v, educador=e["nome"], vende=bool(e.get("vende"))) for v in r[1]
                                   if not v.get("quando") or v["quando"] > limite]
    foto["radar"] = [r for r in radar if r]
    foto["meus"] = [r for r in meus if r]

    # legenda e descrição dos vídeos novos que mais importam: educadores primeiro, depois os mais vistos da busca
    candidatos = [v for v in foto["educadores"] if v["id"] not in vistos]
    candidatos += sorted([v for v in foto["buscas"] if v["id"] not in vistos], key=lambda v: -(v.get("views") or 0))
    escolhidos = candidatos[:LEGENDAS]
    detalhes = [tenta(f"legenda {v['id']}", detalhe, v["id"], idiomas) for v in escolhidos]   # um por vez: em paralelo o YouTube dá 429
    for v, d in zip(escolhidos, detalhes):
        if d:
            v.update(d)
            v["bandeiras"] = sorted(set(v["bandeiras"]) | set(d["bandeiras_desc"]) | ({"vende"} if d["vende"] else set()))
            vistos.add(v["id"])
    _gravar(PASTA / "coletas" / f"{HOJE}.json", foto)
    vistos_arq.write_text(json.dumps(sorted(vistos)), encoding="utf-8")
    print(f"coleta {HOJE}: {len(foto['buscas'])} vídeos de busca, {len(foto['educadores'])} de educadores, "
          f"{len(foto['radar'])} canais no radar, {sum(1 for v in escolhidos if v.get('legenda'))} legendas, {len(foto['erros'])} erros")
    return foto


# ---------------------------------------------------------------- a análise (Claude Code)
def claude_exe():
    salvo = _ler(CONFIG, {}).get("claude_exe") if CONFIG.exists() else None
    if salvo and Path(salvo).exists():
        return salvo
    achado = shutil.which("claude")
    if achado:
        return achado
    casa = Path.home()
    padroes = [casa / ".local/bin/claude.exe", casa / ".local/bin/claude", casa / ".claude/local/claude",
               Path(os.environ.get("APPDATA", "")) / "npm/claude.cmd"]
    for p in padroes:
        if p.exists():
            return str(p)
    nome = "claude.exe" if WINDOWS else "claude"
    achados = glob.glob(str(casa / ".vscode/extensions/anthropic.claude-code-*/resources/native-binary" / nome))
    achados += glob.glob(str(casa / ".cursor/extensions/anthropic.claude-code-*/resources/native-binary" / nome))
    return max(achados, key=os.path.getmtime) if achados else None


def perguntas_pendentes():
    return [p["texto"] for p in _ler(PERGUNTAS, []) if not p.get("respondida")][-8:]


def semanal_hoje(c):
    return c.get("semanal_no_domingo", True) and date.today().weekday() == 6


def _lista(itens, padrao="(nenhum)"):
    return "\n".join(f"- {i}" for i in itens) or padrao


def pedido(semanal=None, saida=None):
    """O pedido completo da análise, montado do modelo radar/ronda.md com a configuração do usuário."""
    c = config()
    semanal = semanal_hoje(c) if semanal is None else semanal
    coletas = sorted((PASTA / "coletas").glob("*.json"))
    feitas = {p.stem for p in (PASTA / "mudancas").glob("????-??-??.json")} if (PASTA / "mudancas").exists() else set()
    novas = [p for p in coletas if p.stem not in feitas][-3:] or coletas[-1:]
    saida = saida or PASTA / "mudancas" / f"{HOJE}.json"
    oficiais = [f"{o['nome']}: {o['url']}" if isinstance(o, dict) else str(o) for o in c.get("fontes_oficiais", [])]
    trocas = {
        "{{PASTA}}": PASTA.as_posix(),
        "{{NICHO}}": c.get("nicho", "(sem nicho na configuração)"),
        "{{QUEM}}": c.get("quem_sou", "(não informado)"),
        "{{QUER_SABER}}": _lista(c.get("o_que_quero_saber", [])),
        "{{BUSCAS_WEB}}": _lista(c.get("buscas_web", []), "- (nenhuma sugerida: monte as suas a partir do nicho)"),
        "{{OFICIAIS}}": _lista(oficiais, "- (nenhuma informada: ache as fontes oficiais do nicho, se houver)"),
        "{{TEMAS}}": ", ".join(f"`{t}`" for t in c.get("temas") or ["regras", "ferramentas", "estrategia", "mercado", "monetizacao", "outros"]),
        "{{IDIOMA}}": c.get("idioma_resposta", "português do Brasil"),
    }
    texto = (AQUI / "ronda.md").read_text(encoding="utf-8")
    for k, v in trocas.items():
        texto = texto.replace(k, v)
    texto += (f"\n\n# Esta ronda\n- Hoje: {HOJE}. Modo: {'REVISÃO SEMANAL (seção 5)' if semanal else 'ronda diária'}.\n"
              + "- Coletas para ler: " + (", ".join(p.as_posix() for p in novas) or "nenhuma (só a busca na web hoje)") + "\n"
              + f"- Fichas atuais: {FICHAS.as_posix()} (pode não existir ainda). Vendedores conhecidos: {VENDEDORES.as_posix()}.\n"
              + "- Perguntas do usuário ainda sem resposta (prioridade nas buscas): " + ("; ".join(perguntas_pendentes()) or "nenhuma") + "\n"
              + f"- Escreva o resultado em: {Path(saida).as_posix()}\n")
    return texto, Path(saida)


def analisar(semanal=None):
    c = config()
    semanal = semanal_hoje(c) if semanal is None else semanal
    exe = claude_exe()
    if not exe:
        raise RuntimeError("não achei o Claude Code (comando claude). Rode: python radar.py checar")
    (PASTA / "mudancas").mkdir(parents=True, exist_ok=True)
    texto, saida = pedido(semanal)
    modelo = c.get("modelo_semanal", "opus") if semanal else c.get("modelo", "sonnet")
    cmd = [exe, "-p", "--model", modelo, "--output-format", "json",
           "--allowedTools", "Read,Glob,Grep,Write,WebSearch,WebFetch", "--add-dir", str(PASTA)]
    r = subprocess.run(cmd, input=texto, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=40 * 60, cwd=PASTA, creationflags=SEM_JANELA)
    try:
        res = json.loads(r.stdout)
    except Exception:
        raise RuntimeError((r.stderr or r.stdout or "o Claude não respondeu").strip()[-400:])
    if res.get("is_error") or not saida.exists():
        raise RuntimeError(f"a análise não gravou {saida.name}: {str(res.get('result'))[:400]}")
    print(f"análise {HOJE}: ok ({res.get('num_turns')} turnos, modelo {modelo})")
    return saida


# ---------------------------------------------------------------- a conta fixa
PESO = {"oficial": 5, "dado": 4, "imprensa": 3, "criador": 2, "comunidade": 1, "anonimo": 0.5, "vendedor": 0.5}   # calculo: 4, ver nota_da_fonte
PROVA = {"conferivel": 1, "print": 0, "nenhuma": -0.5}


def _dias(d):
    try:
        return (date.today() - date.fromisoformat(str(d)[:10])).days
    except Exception:
        return 0


def _autor(f):
    a = (f.get("autor") or "").strip().lower()
    if a:
        return a
    m = re.match(r"https?://(www\.)?([^/]+)", f.get("url", ""))
    return m.group(2) if m else f.get("url", "?")


def _calcular(conta):
    """Conta aritmética simples, sem eval: números, + - * / ** e log/exp/sqrt."""
    import ast
    import math
    funcoes = {"log": math.log, "ln": math.log, "exp": math.exp, "sqrt": math.sqrt}
    ops = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
           ast.Pow: lambda a, b: a ** b if abs(b) <= 1000 else math.inf}

    def ver(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            return ops[type(n.op)](ver(n.left), ver(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -ver(n.operand) if isinstance(n.op, ast.USub) else ver(n.operand)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in funcoes and not n.keywords:
            return funcoes[n.func.id](*[ver(a) for a in n.args])
        raise ValueError("só números, + - * / ** e log/exp/sqrt")
    return ver(ast.parse(str(conta).replace(",", ".").replace("^", "**"), mode="eval").body)


def conferir_calculo(f):
    """Fonte tipo calculo: o programa refaz a conta. Bate com o afirmado (até 5% de diferença) = a favor; não bate = contra."""
    try:
        r = _calcular(f.get("conta", ""))
        alvo = float(f.get("resultado_afirmado"))
        if r != r or abs(r) == float("inf"):
            raise ValueError("a conta não deu um número")
        bate = abs(r - alvo) <= 0.05 * max(abs(alvo), 1e-9)
        f.update(resultado=round(r, 2), conta_ok=bate, posicao="a_favor" if bate else "contra")
    except Exception as e:
        f.update(resultado=None, conta_ok=None, erro_conta=str(e)[:120])
    return f


def nota_da_fonte(f, vendedores):
    tipo = f.get("tipo", "comunidade")
    if tipo == "calculo":                          # conta refeita pelo programa: vale se roda; as premissas ficam à vista
        conferir_calculo(f)
        return (4.0 if f.get("conta_ok") is not None else 0.0), False
    interessado = f.get("interesse") or _autor(f) in vendedores or tipo == "vendedor" or "vende" in (f.get("bandeiras") or [])
    n = PESO.get(tipo, 1) + PROVA.get(f.get("prova", "nenhuma"), -0.5)
    if interessado and tipo != "oficial":
        n *= 0.3
    n -= len([b for b in f.get("bandeiras") or [] if b != "vende"])
    if _dias(f.get("data")) > 90:
        n /= 2
    return max(0.0, round(n, 2)), bool(interessado)


def avaliar(ficha, vendedores):
    lados = {"a_favor": {}, "contra": {}}
    suspeitas = 0                                  # fontes com bandeira de guru (interesse sozinho não faz barulho: só deixa fraco)
    for f in ficha["fontes"]:
        n, interessado = nota_da_fonte(f, vendedores)
        f["nota"] = n
        suspeitas += bool([b for b in f.get("bandeiras") or [] if b != "vende"])
        lado = lados["contra" if f.get("posicao") == "contra" else "a_favor"]
        a = _autor(f)
        lado[a] = max(lado.get(a, 0), n)          # do mesmo autor, só a melhor conta
    pro, contra = sum(lados["a_favor"].values()), sum(lados["contra"].values())
    pro_sem_conta = sum(f.get("nota", 0) for f in ficha["fontes"] if f.get("tipo") != "calculo" and f.get("posicao") != "contra")
    if any(f.get("tipo") == "calculo" and f.get("conta_ok") for f in ficha["fontes"]) and pro_sem_conta < 3:
        pro = min(pro, 4.9)                        # conta certa sozinha mostra que a matemática fecha, não que as premissas valem: no máximo provável
    oficial = any(f.get("tipo") == "oficial" and f.get("posicao") != "contra" for f in ficha["fontes"])
    oficial_contra = any(f.get("tipo") == "oficial" and f.get("posicao") == "contra" for f in ficha["fontes"])
    ultimo = max((f.get("data") or "" for f in ficha["fontes"]), default="")
    ficha.update(nota=round(pro, 1), contra=round(contra, 1), autores=len(lados["a_favor"]), ultimo_visto=ultimo or ficha.get("ultimo_visto", HOJE))
    if ficha.get("tema") != "regras" and _dias(ficha["ultimo_visto"]) > 60:
        s = "vencido"
    elif (oficial_contra and not oficial) or (contra >= 3 and contra >= 2 * pro):
        s = "desmentido"
    elif contra and contra >= 0.5 * pro:
        s = "em_disputa"
    elif oficial or (pro >= 6 and len(lados["a_favor"]) >= 3):
        s = "confirmado"
    elif pro >= 3:
        s = "provavel"
    elif pro < 1.5 and suspeitas * 2 >= len(ficha["fontes"]):
        s = "barulho"
    else:
        s = "fraco"
    ficha["situacao"] = s
    return ficha


def aplicar(mudancas=None):
    fichas = {f["id"]: f for f in _ler(FICHAS, [])}
    vendedores = _ler(VENDEDORES, {})
    m = _ler(Path(mudancas), {}) if mudancas else {}
    for v in m.get("vendedores", []):
        a = (v.get("autor") or "").strip().lower()
        if a:
            vendedores[a] = {"vende": v.get("vende", ""), "url": v.get("url", ""), "desde": vendedores.get(a, {}).get("desde", HOJE)}
    for apagar in m.get("juntar", []):               # revisão semanal: {"de": id, "em": id}
        de, em = fichas.pop(apagar.get("de"), None), fichas.get(apagar.get("em"))
        if de and em:
            em["fontes"] += de["fontes"]
    for nova in m.get("fichas", []):
        if not nova.get("id"):
            continue
        f = fichas.setdefault(nova["id"], {"id": nova["id"], "fontes": [], "primeiro_visto": HOJE})
        for k in ("tema", "afirmacao", "como_usar"):
            if nova.get(k):
                f[k] = nova[k]
        urls = {x.get("url") for x in f["fontes"]}
        f["fontes"] += [x for x in nova.get("fontes", []) if x.get("url") not in urls]
    for f in fichas.values():
        avaliar(f, vendedores)
    respondidas = set(m.get("pesquisas_respondidas") or [])
    if respondidas:
        perguntas = _ler(PERGUNTAS, [])
        for p in perguntas:
            if p["texto"] in respondidas:
                p["respondida"] = HOJE
        _gravar(PERGUNTAS, perguntas)
    lista = sorted(fichas.values(), key=lambda f: (SITUACOES.index(f["situacao"]), -f["nota"]))
    _gravar(FICHAS, lista)
    _gravar(VENDEDORES, vendedores)
    if m and not m.get("link"):                     # checagem de link não mexe no boletim da ronda
        _gravar(PASTA / "boletins" / f"{HOJE}.json", {k: m.get(k, []) for k in ("boletim", "alertas", "buscas")})
    escrever_painel(lista, vendedores)
    print(f"aplicado: {len(lista)} fichas · " + " · ".join(f"{NOME_SITUACAO[s]} {sum(1 for f in lista if f['situacao'] == s)}" for s in SITUACOES))
    return lista


# ---------------------------------------------------------------- o painel (uma página só, sem nada externo)
def _dm(d):
    return f"{d[8:10]}/{d[5:7]}" if d and len(d) >= 10 else "?"


def _milhar(n):
    return f"{n or 0:,}".replace(",", ".")


def _e(t):
    return html.escape(str(t or ""))


def _link(url, texto):
    url = str(url or "")
    if not url.startswith(("http://", "https://")):
        return _e(texto)
    return f'<a href="{_e(url)}" target="_blank" rel="noopener">{_e(texto)}</a>'


def _ficha_html(f, motivo=False):
    fontes = "".join(
        f'<li><span class="tipo">{_e(x.get("tipo", "?"))}</span> {_link(x.get("url"), x.get("autor") or _autor(x))}'
        f'{" <b class=contra>contra</b>" if x.get("posicao") == "contra" else ""}'
        f' <span class="nota">nota {x.get("nota", 0)}</span>'
        + (f' <span class="band">{_e(", ".join(NOME_BANDEIRA.get(b, b) for b in x.get("bandeiras")))}</span>' if x.get("bandeiras") else "")
        + (f'<div class="resumo">{_e(x.get("resumo"))}</div>' if x.get("resumo") else "")
        + (f'<div class="resumo">conta refeita pelo programa: {_e(x.get("conta"))} = {_e(x.get("resultado"))} '
           f'(o vídeo diz {_e(x.get("resultado_afirmado"))}) {"✔ bate" if x.get("conta_ok") else "✘ não bate"}'
           f'{" · premissas: " + _e(x.get("premissas")) if x.get("premissas") else ""}</div>' if x.get("tipo") == "calculo" else "") + "</li>"
        for x in sorted(f["fontes"], key=lambda x: -x.get("nota", 0))[:6])
    extra = f' · contra {f["contra"]}' if f.get("contra") else ""
    uso = f'<div class="uso">Pra você: {_e(f["como_usar"])}</div>' if f.get("como_usar") else ""
    porque = ""
    if motivo:
        bs = sorted({b for x in f["fontes"] for b in x.get("bandeiras") or []})
        porque = f'<div class="uso">Por quê: {_e(", ".join(NOME_BANDEIRA.get(b, b) for b in bs) or "?")}</div>'
    return (f'<details class="ficha {f["situacao"]}"><summary><span class="sit">{NOME_SITUACAO[f["situacao"]]}</span> '
            f'<b>{_e(f.get("afirmacao", f["id"]))}</b><span class="meta">nota {f["nota"]}{extra} · {f["autores"]} autor(es) · '
            f'visto em {_dm(f["ultimo_visto"])}</span></summary>{uso}{porque}<ul>{fontes}</ul></details>')


CSS = """
:root{--fundo:#0e0f13;--cartao:#171920;--linha:#262935;--texto:#e7e8ee;--fraco:#9097a8;--ouro:#f2c14e;--verde:#4ade80;--azul:#7aa2ff;--vermelho:#f87171}
*{box-sizing:border-box}body{margin:0;background:var(--fundo);color:var(--texto);font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 20px 80px}h1{font-size:26px;margin:0}h1 span{color:var(--ouro)}
.sub{color:var(--fraco);margin:4px 0 24px}h2{font-size:18px;margin:36px 0 12px;border-bottom:1px solid var(--linha);padding-bottom:6px}
h3{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--fraco);margin:22px 0 8px}
.contagem{display:flex;flex-wrap:wrap;gap:8px}.contagem span{background:var(--cartao);border:1px solid var(--linha);border-radius:999px;padding:4px 12px;font-size:13px}
.cartao{background:var(--cartao);border:1px solid var(--linha);border-radius:12px;padding:14px 18px}.cartao li{margin:6px 0}
.alerta{border-color:var(--vermelho)}.alerta b{color:var(--vermelho)}
.ficha{background:var(--cartao);border:1px solid var(--linha);border-left:4px solid var(--linha);border-radius:10px;margin:8px 0;padding:10px 14px}
.ficha summary{cursor:pointer;list-style:none}.ficha summary::-webkit-details-marker{display:none}
.confirmado{border-left-color:var(--verde)}.provavel{border-left-color:#22c55e88}.em_disputa{border-left-color:var(--ouro)}
.barulho,.desmentido{border-left-color:var(--vermelho)}.cartao .meta{margin-bottom:4px}.cartao ul{margin:6px 0 0;padding-left:18px}.fraco,.vencido{opacity:.8}
.sit{font-size:12px;margin-right:6px;white-space:nowrap}.meta{display:block;color:var(--fraco);font-size:12.5px;margin-top:2px}
.uso{margin:10px 0 0;color:var(--ouro);font-size:14px}.ficha ul{margin:10px 0 0;padding-left:18px;font-size:13.5px}
.tipo{font-size:11px;text-transform:uppercase;background:#ffffff10;border-radius:4px;padding:1px 6px;color:var(--fraco)}
.nota{color:var(--fraco);font-size:12px}.band{color:var(--vermelho);font-size:12px}.contra{color:var(--ouro)}
.resumo{color:var(--fraco);font-size:13px}a{color:var(--azul);text-decoration:none}a:hover{text-decoration:underline}
table{width:100%;border-collapse:collapse;font-size:14px}td{padding:6px 8px;border-top:1px solid var(--linha);vertical-align:top}
td.x{color:var(--ouro);font-weight:700;white-space:nowrap}.rodape{color:var(--fraco);font-size:13px;margin-top:40px}
"""


def escrever_painel(lista, vendedores):
    try:
        c = _ler(CONFIG, {})
    except Exception:
        c = {}
    hoje = _ler(PASTA / "boletins" / f"{HOJE}.json", None)
    ultimos_boletins = sorted((PASTA / "boletins").glob("*.json")) if (PASTA / "boletins").exists() else []
    if not hoje and ultimos_boletins:
        hoje = _ler(ultimos_boletins[-1], None)
    data_boletim = ultimos_boletins[-1].stem if ultimos_boletins else HOJE
    contagem = {s: sum(1 for f in lista if f["situacao"] == s) for s in SITUACOES}
    p = [f"<!doctype html><html lang=pt-br><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
         f"<title>Radar Anti-Guru · {_e(c.get('nicho', ''))}</title><style>{CSS}</style><main>",
         f"<h1>Radar <span>Anti-Guru</span></h1><div class=sub>{_e(c.get('nicho', ''))} · atualizado {_dm(HOJE)}</div>",
         "<div class=contagem>" + "".join(f"<span>{NOME_SITUACAO[s]}: {contagem[s]}</span>" for s in SITUACOES) + "</div>"]
    if hoje and hoje.get("alertas"):
        p.append("<h2>⚠️ Pede sua atenção</h2><div class='cartao alerta'><ul>"
                 + "".join(f"<li><b>{_e(a.get('titulo'))}</b> {_e(a.get('texto'))}</li>" for a in hoje["alertas"]) + "</ul></div>")
    if hoje and hoje.get("boletim"):
        p.append(f"<h2>Boletim de {_dm(data_boletim)}</h2><div class=cartao><ul>"
                 + "".join(f"<li>{_e(l)}</li>" for l in hoje["boletim"]) + "</ul></div>")
    por_id = {f["id"]: f for f in lista}
    checados = [l for l in (_ler(a, {}) for a in sorted((PASTA / "links").glob("*.json"), key=os.path.getmtime, reverse=True))
                if l.get("veredito")][:15] if (PASTA / "links").exists() else []
    if checados:
        p.append("<h2>🔗 Links checados</h2><div class=sub>Vídeos que você colou pra checar. A situação de cada afirmação é a de hoje: "
                 "muda se aparecer fonte nova.</div>")
        for l in checados:
            fichas_link = [por_id[i] for i in l["veredito"] if i in por_id]
            p.append(f"<div class=cartao style='margin:8px 0'><b>{_link(l.get('url'), l.get('titulo') or l.get('url'))}</b>"
                     f"<div class=meta>{_e(l.get('plataforma'))} · {_e(l.get('autor'))} · checado em {_dm(l.get('checado_em', ''))}"
                     + (f" · <span class=band>{_e(', '.join(NOME_BANDEIRA.get(b, b) for b in l.get('bandeiras') or []))}</span>" if l.get("bandeiras") else "")
                     + "</div><ul>" + "".join(f"<li>{NOME_SITUACAO[f['situacao']]} · {_e(f.get('afirmacao'))} <span class=nota>nota {f['nota']}"
                                              f"{' · contra ' + str(f['contra']) if f.get('contra') else ''}</span></li>" for f in fichas_link)
                     + "</ul></div>")
    coletas = sorted((PASTA / "coletas").glob("*.json")) if (PASTA / "coletas").exists() else []
    foto = _ler(coletas[-1], {}) if coletas else {}
    outs = [(r["nome"], v) for r in foto.get("radar", []) + foto.get("meus", []) for v in r.get("outliers", [])]
    if outs:
        p.append("<h2>Estourando no radar</h2><div class=sub>Views ÷ mediana do próprio canal, vídeos dos últimos 21 dias. "
                 "Isso é dado medido, não opinião.</div><div class=cartao><table>"
                 + "".join(f"<tr><td class=x>{v['vezes']}x</td><td>{_e(nome)}</td><td>{_link('https://youtu.be/' + v['id'], v['titulo'])}"
                           f"</td><td>{_milhar(v.get('views'))} views</td></tr>"
                           for nome, v in sorted(outs, key=lambda o: -(o[1].get("vezes") or 0))[:12]) + "</table></div>")
    if foto.get("buscas"):
        band = sum(1 for v in foto["buscas"] if v.get("bandeiras"))
        p.append(f"<div class=sub style='margin-top:12px'>Na última coleta ({_dm(foto.get('data', ''))}): {len(foto['buscas'])} vídeos da semana nas buscas, "
                 f"{band} com bandeira de guru no título ou na descrição.</div>")
    temas = {}
    for f in lista:
        if f["situacao"] in ("confirmado", "provavel", "em_disputa"):
            temas.setdefault(f.get("tema", "outros"), []).append(f)
    p.append("<h2>O que dá pra levar a sério</h2><div class=sub>Só ✅ e 🟢 servem pra orientar decisão. ⚖️ é briga aberta. "
             "Clique numa ficha pra ver as fontes e a nota de cada uma.</div>")
    for tema in sorted(temas):
        p.append(f"<h3>{_e(tema)}</h3>" + "".join(_ficha_html(f) for f in temas[tema]))
    if not temas:
        p.append("<div class=cartao>Nada confirmado ainda. As primeiras rondas juntam fonte; em poucos dias a base enche.</div>")
    fracas = [f for f in lista if f["situacao"] == "fraco"]
    if fracas:
        p.append(f"<h2>Ainda fraco ({len(fracas)})</h2><div class=sub>Pouca fonte ou fonte ruim. Fica guardado até alguém confirmar.</div>"
                 + "".join(_ficha_html(f) for f in fracas[:40]))
    desmentidos = [f for f in lista if f["situacao"] == "desmentido"]
    if desmentidos:
        p.append(f"<h2>❌ Desmentido ({len(desmentidos)})</h2><div class=sub>Fonte oficial ou fontes bem mais fortes dizem o contrário.</div>"
                 + "".join(_ficha_html(f, motivo=True) for f in desmentidos))
    barulho = [f for f in lista if f["situacao"] == "barulho"]
    p.append(f"<h2>🚩 Barulho ({len(barulho)})</h2><div class=sub>O que está sendo vendido como verdade e não passou no filtro. "
             "Serve pra reconhecer o papo quando aparecer de novo.</div>"
             + ("".join(_ficha_html(f, motivo=True) for f in barulho) or "<div class=cartao>(nada por enquanto)</div>"))
    p.append("<h2>Vendedores conhecidos</h2><div class=sub>Tudo o que eles disserem entra como fonte interessada (nota × 0,3).</div><div class=cartao><ul>"
             + ("".join(f"<li><b>{_e(a)}</b>: {_e(v.get('vende') or '?')} {_link(v.get('url'), 'link')} (desde {_dm(v.get('desde', ''))})</li>"
                        for a, v in sorted(vendedores.items())) or "<li>(nenhum)</li>") + "</ul></div>")
    p.append("<h2>Como a nota é feita</h2><div class=cartao>A IA não dá nota. Ela só responde, sobre cada fonte: quem é "
             "(oficial, imprensa, criador, comunidade, anônimo, vendedor), se mostra prova e se ganha com aquilo. O programa faz a conta: "
             "<ul><li>peso do tipo: oficial 5 · dado medido 4 · conta refeita pelo programa 4 (se bate, conta a favor; se não bate, contra) · imprensa 3 · criador 2 · comunidade 1 · anônimo e vendedor 0,5</li>"
             "<li>prova: conferível +1 · só print 0 · nenhuma −0,5</li><li>se a fonte ganha com aquilo (curso, afiliado, a própria ferramenta): nota × 0,3</li>"
             "<li>cada bandeira de guru (promessa de renda, “automático”, “ninguém fala disso”, “sem concorrência”, “clonei”): −1</li>"
             "<li>fonte com mais de 90 dias vale metade · do mesmo autor, só a melhor conta</li></ul>"
             "✅ confirmado = fonte oficial ou nota ≥ 6 com 3 autores independentes · 🟢 provável = nota ≥ 3 · "
             "⚖️ em disputa = o lado contra soma metade ou mais · ❌ desmentido = fonte oficial contra, ou o lado contra vale o dobro · 🚩 barulho = nota &lt; 1,5 e metade das fontes com bandeira · "
             "⌛ vencido = 60 dias sem ninguém falar.</div>")
    p.append(f"<div class=rodape>Radar Anti-Guru · dados em {_e(PASTA.as_posix())}</div></main></html>")
    PAINEL.write_text("\n".join(p), encoding="utf-8")


def abrir():
    if not PAINEL.exists():
        aplicar()
    webbrowser.open(PAINEL.as_uri())
    print(PAINEL)


# ---------------------------------------------------------------- checar um link (qualquer rede que o yt-dlp lê)
def _tem(modulo):
    import importlib.util
    return importlib.util.find_spec(modulo) is not None


def _opc_link(navegador, **extra):
    opc = {"quiet": True, "no_warnings": True, "noprogress": True, **extra}
    if navegador:
        opc["cookiesfrombrowser"] = (navegador,)
    return opc


def _legenda_do_link(url, info, navegador, tmp):
    import yt_dlp
    for fonte in ("subtitles", "automatic_captions"):
        subs = {l: v for l, v in (info.get(fonte) or {}).items() if l != "live_chat"}
        lang = (next((l for l in subs if l.endswith("-orig")), None) or next((l for l in subs if l.split("-")[0] in ("pt", "en", "es")), None)
                or next(iter(subs), None))
        if not lang:
            continue
        try:
            with yt_dlp.YoutubeDL(_opc_link(navegador, skip_download=True, writesubtitles=fonte == "subtitles",
                                            writeautomaticsub=fonte == "automatic_captions", subtitleslangs=[lang],
                                            subtitlesformat="vtt/srt/best", outtmpl=str(Path(tmp) / "sub.%(ext)s"))) as y:
                y.download([url])
            arq = next((a for a in Path(tmp).glob("sub*") if a.suffix in (".vtt", ".srt")), None)
            texto = vtt_texto(arq.read_text(encoding="utf-8", errors="replace")) if arq else ""
        except Exception:
            texto = ""
        if texto:
            return texto, lang
    return "", None


def _transcrever(url, navegador, tmp):
    """Sem legenda: baixa o áudio e transcreve aqui mesmo (faster-whisper; modelo 'small', ou o da variável RADAR_WHISPER)."""
    import yt_dlp
    from faster_whisper import WhisperModel
    with yt_dlp.YoutubeDL(_opc_link(navegador, format="bestaudio/best", outtmpl=str(Path(tmp) / "audio.%(ext)s"))) as y:
        y.download([url])
    audio = next(a for a in Path(tmp).glob("audio.*") if a.suffix != ".part")
    nome = os.environ.get("RADAR_WHISPER", "small")
    try:
        modelo = WhisperModel(nome, device="auto", compute_type="int8")
        segs, info = modelo.transcribe(str(audio), vad_filter=True)
        texto = " ".join(s.text.strip() for s in segs)
    except Exception:                               # placa sem as bibliotecas da NVIDIA: vai no processador
        modelo = WhisperModel(nome, device="cpu", compute_type="int8")
        segs, info = modelo.transcribe(str(audio), vad_filter=True)
        texto = " ".join(s.text.strip() for s in segs)
    return texto, info.language


def link(url, navegador=None):
    """Lê um vídeo de qualquer rede (YouTube, TikTok, Instagram, X, Kwai, Facebook...): quem postou, descrição, o que é dito
    (legenda ou transcrição) e as bandeiras de guru pela regra fixa. Grava em links/ e imprime o caminho."""
    import tempfile
    import yt_dlp
    try:
        with yt_dlp.YoutubeDL(_opc_link(navegador, skip_download=True, ignore_no_formats_error=True)) as y:
            info = y.extract_info(url, download=False)
    except Exception as e:
        erro = str(e)
        dica = ("A rede pediu login. Tente de novo com --navegador firefox (ou chrome, edge, brave), "
                "usando um navegador em que você esteja logado nela." if re.search(r"login|cookies|private|sign in|rate.?limit", erro, re.I)
                else "Confira se o link abre no navegador e é de um vídeo público.")
        print(json.dumps({"erro": erro[-400:], "dica": dica}, ensure_ascii=False, indent=1))
        return None
    if info.get("_type") == "playlist" and info.get("entries"):      # post com vários vídeos: o primeiro
        info = next((e for e in info["entries"] if e), info)
    descricao = info.get("description") or ""
    with tempfile.TemporaryDirectory() as tmp:
        texto, idioma = _legenda_do_link(url, info, navegador, tmp)
        origem = "legenda" if texto else "nenhum"
        falta = None
        if not texto:
            if _tem("faster_whisper"):
                try:
                    texto, idioma = _transcrever(url, navegador, tmp)
                    origem = "transcricao"
                except Exception as e:
                    falta = f"não consegui transcrever: {str(e)[-200:]}"
            else:
                falta = "o vídeo não tem legenda e a transcrição não está instalada (rode: python radar.py checar --whisper)"
    data = info.get("upload_date") or ""
    dados = {
        "url": info.get("webpage_url") or url, "id": str(info.get("id") or ""), "plataforma": info.get("extractor_key") or info.get("extractor"),
        "titulo": info.get("title") or info.get("fulltitle"), "autor": info.get("uploader") or info.get("channel") or info.get("creator"),
        "autor_url": info.get("uploader_url") or info.get("channel_url"), "seguidores": info.get("channel_follower_count"),
        "views": info.get("view_count"), "curtidas": info.get("like_count"), "comentarios": info.get("comment_count"),
        "data": f"{data[:4]}-{data[4:6]}-{data[6:8]}" if len(data) == 8 else "", "duracao": info.get("duration"),
        "descricao": descricao[:3000], "texto": texto[:25000], "texto_origem": origem, "idioma": idioma, "falta": falta,
        "bandeiras": bandeiras(f"{info.get('title') or ''} {descricao[:600]} {texto[:1500]}"),
        "vende": vende(f"{descricao} {texto}"), "checado_em": HOJE,
    }
    if dados["vende"]:
        dados["bandeiras"] = sorted(set(dados["bandeiras"]) | {"vende"})
    nome = re.sub(r"[^\w-]+", "_", f"{dados['plataforma']}-{dados['id']}".lower())[:80]
    arq = PASTA / "links" / f"{nome}.json"
    antigo = _ler(arq, {})
    if antigo.get("veredito"):
        dados["veredito"] = antigo["veredito"]
    _gravar(arq, dados)
    resumo = {k: v for k, v in dados.items() if k not in ("descricao", "texto")}
    resumo.update(arquivo=str(arq), palavras_no_texto=len(texto.split()),
                  mudancas=str(PASTA / "mudancas" / f"{HOJE}-link-{nome}.json"))
    print(json.dumps(resumo, ensure_ascii=False, indent=1))
    return arq


def veredito(mudancas):
    """Depois do aplicar: o que a conta fixa decidiu sobre cada afirmação do vídeo."""
    m = _ler(Path(mudancas), {})
    fichas = {f["id"]: f for f in _ler(FICHAS, [])}
    vendedores = _ler(VENDEDORES, {})
    url = (m.get("link") or {}).get("url")
    ids = [f["id"] for f in m.get("fichas", []) if f.get("id") in fichas]
    saida = {"url": url, "afirmacoes": []}
    for i in ids:
        f = fichas[i]
        do_video = next((x for x in f["fontes"] if url and x.get("url") == url), None)
        saida["afirmacoes"].append({"id": i, "afirmacao": f.get("afirmacao"), "situacao": NOME_SITUACAO[f["situacao"]], "nota": f["nota"],
                                    "contra": f.get("contra"), "autores": f["autores"],
                                    "nota_do_video": do_video.get("nota") if do_video else None,
                                    "melhores_fontes": [{"autor": x.get("autor"), "tipo": x.get("tipo"), "posicao": x.get("posicao"),
                                                         "nota": x.get("nota"), "url": x.get("url")}
                                                        for x in sorted(f["fontes"], key=lambda x: -x.get("nota", 0))[:3]]})
    autor = ((m.get("link") or {}).get("autor") or "").strip().lower()
    saida["autor_vendedor"] = vendedores.get(autor)
    arq = (m.get("link") or {}).get("arquivo")
    if arq and Path(arq).exists():
        l = _ler(arq, {})
        l["veredito"] = ids
        _gravar(arq, l)
        escrever_painel(sorted(fichas.values(), key=lambda f: (SITUACOES.index(f["situacao"]), -f["nota"])), vendedores)
    print(json.dumps(saida, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- instalação e configuração
def checar(instalar=False, whisper=False):
    ok = {"python": sys.version.split()[0], "python_ok": sys.version_info >= (3, 9), "pasta": str(PASTA)}
    if whisper and not _tem("faster_whisper"):
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "faster-whisper"], capture_output=True, text=True)
        ok["whisper_instalacao"] = (r.stdout + r.stderr).strip()[-300:]
    ok["transcricao"] = _tem("faster_whisper")
    try:
        import yt_dlp  # noqa: F401
        ok["yt_dlp"] = True
    except ImportError:
        ok["yt_dlp"] = False
        if instalar:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--upgrade", "yt-dlp"], capture_output=True, text=True)
            ok["yt_dlp"] = r.returncode == 0
            ok["yt_dlp_instalacao"] = (r.stdout + r.stderr).strip()[-300:]
    ok["claude"] = claude_exe()
    ok["config"] = CONFIG.exists()
    if ok["claude"] and CONFIG.exists():
        c = _ler(CONFIG, {})
        if c.get("claude_exe") != ok["claude"]:
            c["claude_exe"] = ok["claude"]
            _gravar(CONFIG, c)
    print(json.dumps(ok, ensure_ascii=False, indent=1))
    return ok


def achar_canal(termo):
    d = ytdlp(f"https://www.youtube.com/results?search_query={urllib.request.quote(termo)}&sp={SO_CANAIS}", "--playlist-end", "8")
    achados = []
    for e in d.get("entries") or []:
        if not e:
            continue
        cid = e.get("channel_id") or e.get("id")
        achados.append({"nome": e.get("channel") or e.get("title"), "canal": cid, "url": e.get("url") or e.get("channel_url"),
                        "inscritos": e.get("channel_follower_count")})
    print(json.dumps(achados, ensure_ascii=False, indent=1))


def exemplo(nome):
    arq = EXEMPLOS / f"{nome}.json"
    if not arq.exists():
        raise SystemExit("exemplos: " + ", ".join(p.stem for p in EXEMPLOS.glob("*.json")))
    if CONFIG.exists():
        raise SystemExit(f"já existe {CONFIG}; apague antes se quiser trocar")
    PASTA.mkdir(parents=True, exist_ok=True)
    shutil.copy(arq, CONFIG)
    print(f"configuração {nome} copiada para {CONFIG}")


def validar():
    c = config()
    problemas = []
    for k in ("nicho", "buscas_youtube"):
        if not c.get(k):
            problemas.append(f"falta '{k}'")
    for grupo in ("educadores", "radar", "meus_canais"):
        for i, x in enumerate(c.get(grupo, [])):
            if not isinstance(x, dict) or not x.get("nome") or not x.get("canal"):
                problemas.append(f"{grupo}[{i}] precisa de 'nome' e 'canal' (@handle ou id UC...)")
    for nome, r in (c.get("bandeiras_extras") or {}).items():
        try:
            re.compile(r)
        except re.error as e:
            problemas.append(f"bandeira extra '{nome}' com regex inválida: {e}")
    print("configuração ok" if not problemas else "\n".join(problemas))
    return not problemas


def perguntar(texto):
    perguntas = _ler(PERGUNTAS, [])
    if texto not in [p["texto"] for p in perguntas]:
        perguntas.append({"texto": texto, "quando": HOJE})
        _gravar(PERGUNTAS, perguntas)
    print(f"guardada: a próxima ronda vai atrás de “{texto}”")


def _motor():
    """A ronda agendada roda de uma cópia do motor dentro da pasta de dados: o plugin muda de lugar quando atualiza."""
    destino = PASTA / "motor"
    destino.mkdir(parents=True, exist_ok=True)
    for arq in ("radar.py", "ronda.md"):
        shutil.copy(AQUI / arq, destino / arq)
    return destino / "radar.py"


def agendar(hora="05:00"):
    motor = _motor()
    checar()
    if WINDOWS:
        pyw = Path(sys.executable).with_name("pythonw.exe")
        py = pyw if pyw.exists() else Path(sys.executable)
        args = f'"{motor}" diario --pasta "{PASTA}"'
        ps = (f"$a=New-ScheduledTaskAction -Execute '{py}' -Argument '{args}';"
              f"$t=New-ScheduledTaskTrigger -Daily -At '{hora}';"
              "$s=New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 2) "
              "-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
              f"Register-ScheduledTask -TaskName '{NOME_TAREFA}' -Action $a -Trigger $t -Settings $s -Force | Out-Null")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"não consegui criar a tarefa: {r.stderr.strip()[-400:]}")
        print(f"agendado: todo dia às {hora} (tarefa “{NOME_TAREFA}” no Agendador do Windows). Se o PC estiver desligado, roda quando ligar.")
    else:
        h, m = hora.split(":")
        linha = f'{int(m)} {int(h)} * * * "{sys.executable}" "{motor}" diario --pasta "{PASTA}"  # {NOME_TAREFA}'
        atual = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        novo = "\n".join(l for l in atual.splitlines() if NOME_TAREFA not in l) + f"\n{linha}\n"
        subprocess.run(["crontab", "-"], input=novo.lstrip(), text=True, check=True)
        print(f"agendado no crontab: todo dia às {hora}. O computador precisa estar ligado nesse horário.")


def desagendar():
    if WINDOWS:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Unregister-ScheduledTask -TaskName '{NOME_TAREFA}' -Confirm:$false"], capture_output=True)
    else:
        atual = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        subprocess.run(["crontab", "-"], input="\n".join(l for l in atual.splitlines() if NOME_TAREFA not in l) + "\n", text=True)
    print("ronda diária desligada")


def status():
    lista = _ler(FICHAS, [])
    coletas = sorted((PASTA / "coletas").glob("*.json")) if (PASTA / "coletas").exists() else []
    logs = sorted((PASTA / "logs").glob("*.log")) if (PASTA / "logs").exists() else []
    print(json.dumps({"pasta": str(PASTA), "config": CONFIG.exists(), "fichas": len(lista),
                      "situacoes": {s: sum(1 for f in lista if f["situacao"] == s) for s in SITUACOES},
                      "ultima_coleta": coletas[-1].stem if coletas else None, "perguntas_pendentes": perguntas_pendentes(),
                      "ultimo_log": logs[-1].read_text(encoding="utf-8", errors="replace")[-800:] if logs else None},
                     ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- a ronda inteira
def diario(abrir_no_fim=False):
    (PASTA / "logs").mkdir(parents=True, exist_ok=True)
    trava = PASTA / ".rodando"
    if trava.exists() and time.time() - trava.stat().st_mtime < 3 * 3600:
        print("já tem uma ronda rodando")
        return
    trava.write_text(str(os.getpid()))
    try:
        try:
            coletar()
        except Exception as e:
            print(f"coleta falhou: {e}")
        try:
            aplicar(analisar())
        except Exception as e:
            print(f"análise falhou (a coleta ficou salva; a próxima ronda lê as duas): {e}")
            aplicar()
    finally:
        trava.unlink(missing_ok=True)
    if abrir_no_fim:
        abrir()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    arg = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    if sys.stdout is None or (cmd == "diario" and "--agora" not in sys.argv):
        # a tarefa agendada roda sem janela: tudo vai pro registro do dia
        (PASTA / "logs").mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(PASTA / "logs" / f"{HOJE}.log", "a", encoding="utf-8", buffering=1)
        print(f"--- {datetime.now():%H:%M} ronda {cmd}")
    elif hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if cmd == "coletar":
        coletar()
    elif cmd == "pedido":
        texto, saida = pedido("--semanal" in sys.argv or None)
        (PASTA / "mudancas").mkdir(parents=True, exist_ok=True)
        print(texto)
    elif cmd == "analisar":
        print(analisar("--semanal" in sys.argv or None))
    elif cmd == "aplicar":
        aplicar(arg)
    elif cmd == "abrir":
        abrir()
    elif cmd == "checar":
        checar("--instalar" in sys.argv, "--whisper" in sys.argv)
    elif cmd == "link":
        link(arg or "", sys.argv[sys.argv.index("--navegador") + 1] if "--navegador" in sys.argv else None)
    elif cmd == "veredito":
        veredito(arg or "")
    elif cmd == "achar-canal":
        achar_canal(arg or "")
    elif cmd == "exemplo":
        exemplo(arg or "")
    elif cmd == "validar":
        validar()
    elif cmd == "perguntar":
        perguntar(" ".join(sys.argv[2:]))
    elif cmd == "agendar":
        agendar(sys.argv[sys.argv.index("--hora") + 1] if "--hora" in sys.argv else "05:00")
    elif cmd == "desagendar":
        desagendar()
    elif cmd == "status":
        status()
    elif cmd == "diario":
        diario(abrir_no_fim="--agora" in sys.argv)
    else:
        print(__doc__)
