import requests
import time
import difflib
from datetime import datetime, timedelta, timezone

TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5

HEADERS = {"x-apisports-key": API_KEY}

ultimo_envio = {}
ultimo_auto = 0
last_update_id = None

# 🔥 REQUEST SEGURO
def safe_request(url, params=None):
    try:
        return requests.get(url, headers=HEADERS, params=params, timeout=10)
    except:
        return None

# 🧠 APELIDOS
apelidos = {
    "sevilha": "Sevilla",
    "valencia": "Valencia CF",
    "atlético mineiro": "Atletico Mineiro",
    "atletico mineiro": "Atletico Mineiro",
    "man city": "Manchester City",
    "man united": "Manchester United",
    "inter": "Inter Milan",
    "milan": "AC Milan",
    "psg": "Paris Saint Germain",
    "real": "Real Madrid",
    "barça": "Barcelona",
    "juve": "Juventus",
}

def corrigir_nome(nome):
    nome = nome.lower().strip()
    for apelido, oficial in apelidos.items():
        if apelido in nome:
            return oficial
    return nome.title()

# 🔍 BUSCA INTELIGENTE
def buscar_time(nome):
    try:
        nome_corrigido = corrigir_nome(nome)
        res = safe_request("https://v3.football.api-sports.io/teams", {"search": nome_corrigido})
        if not res:
            return None, []

        data = res.json()

        if not data["response"]:
            return None, []

        melhor_id = None
        melhor_score = 0
        sugestoes = []

        for t in data["response"]:
            nome_api = t["team"]["name"]
            score = difflib.SequenceMatcher(None, nome_corrigido.lower(), nome_api.lower()).ratio()

            sugestoes.append(nome_api)

            if score > melhor_score:
                melhor_score = score
                melhor_id = t["team"]["id"]

        if melhor_score < 0.5:
            return None, sugestoes[:3]

        return melhor_id, []

    except:
        return None, []

# 📊 JOGOS
def pegar_jogos(team_id):
    try:
        res = safe_request(f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10")
        if not res:
            return []
        return res.json().get("response", [])
    except:
        return []

# 🧠 INTERPRETAÇÃO
def interpretar_entrada(entrada):
    if entrada == "Over 1.5":
        return "Alta tendência de gols"
    elif entrada == "Over 2.5":
        return "Jogo propenso a gols"
    elif entrada == "Ambas marcam":
        return "Ambas equipes ofensivas"
    elif entrada == "Under 3.5":
        return "Jogo mais controlado"
    return "Análise padrão"

def definir_status(forca, ev):
    if forca >= 8 and ev > 0:
        return "✅ ENTRAR"
    elif forca == 7:
        return "⚠️ OBSERVAR"
    else:
        return "❌ EVITAR"

# 🧠 ANÁLISE
def analisar(home, away):
    home_id, sug_home = buscar_time(home)
    away_id, sug_away = buscar_time(away)

    if not home_id or not away_id:
        return None, sug_home, sug_away

    jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

    gols = []
    btts = 0

    for j in jogos:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]
            total = g1 + g2
            gols.append(total)
            if g1 > 0 and g2 > 0:
                btts += 1
        except:
            continue

    if len(gols) < 8:
        return None, [], []

    total = len(gols)

    stats = {
        "Over 1.5": sum(1 for g in gols if g >= 2) / total,
        "Over 2.5": sum(1 for g in gols if g >= 3) / total,
        "Ambas marcam": btts / total,
        "Under 3.5": sum(1 for g in gols if g <= 3) / total
    }

    odds = {
        "Over 1.5": 1.30,
        "Over 2.5": 1.80,
        "Ambas marcam": 1.90,
        "Under 3.5": 1.40
    }

    melhor = None
    melhor_score = -999

    for m, prob in stats.items():
        ev = (prob * odds[m]) - 1
        score = ev + prob

        if score > melhor_score:
            melhor_score = score
            melhor = m
            melhor_prob = prob
            melhor_ev = ev

    if not melhor:
        return None, [], []

    forca = 9 if melhor_prob >= 0.75 else 8 if melhor_prob >= 0.65 else 7

    return (melhor, int(melhor_prob*100), forca, round(melhor_ev, 2)), [], []

# 📲 ENVIAR
def enviar(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except:
        pass

# 🏆 LIGA
def nome_liga(liga, pais=""):
    liga = liga.lower()
    pais = pais.lower()

    if "brazil" in pais:
        if "serie a" in liga:
            return "🇧🇷 Campeonato Brasileiro – Série A"
        elif "serie b" in liga:
            return "🇧🇷 Campeonato Brasileiro – Série B"

    if "england" in pais:
        return "🏴 Premier League"
    if "spain" in pais:
        return "🇪🇸 La Liga"
    if "germany" in pais:
        return "🇩🇪 Bundesliga"
    if "italy" in pais:
        return "🇮🇹 Serie A"
    if "france" in pais:
        return "🇫🇷 Ligue 1"

    return "🌍 Liga não encontrada"

# ⏰ FILTRO HORÁRIO
def filtrar_por_periodo(hora, periodo):
    h = int(hora.split(":")[0])

    if periodo == "madrugada":
        return 0 <= h < 8
    elif periodo == "manha":
        return 8 <= h < 12
    elif periodo == "tarde":
        return 12 <= h < 18
    elif periodo == "noite":
        return 18 <= h <= 23

    return True

# ⚽ BUSCAR JOGOS
def buscar_jogos():
    jogos = []
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    res = safe_request(f"https://v3.football.api-sports.io/fixtures?date={hoje}")
    if not res:
        return []

    data = res.json()
    agora = datetime.now(timezone.utc)

    for j in data.get("response", [])[:50]:

        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))

        if (dt - agora).total_seconds() > 7200:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        dt -= timedelta(hours=4)

        jogos.append((home, away, j["league"]["name"], j["league"]["country"],
                      dt.strftime("%d/%m"), dt.strftime("%H:%M")))

    return jogos

# 🔥 MULTIPLA
def gerar_multipla(qtd=3, periodo=None):
    jogos = buscar_jogos()
    selecionados = []

    for home, away, liga, pais, data_jogo, hora in jogos:

        if periodo and not filtrar_por_periodo(hora, periodo):
            continue

        resultado, _, _ = analisar(home, away)
        if not resultado:
            continue

        entrada, prob, forca, ev = resultado

        if prob < 65:
            continue

        selecionados.append((home, away, entrada, prob, hora))

    selecionados.sort(key=lambda x: x[3], reverse=True)

    multipla = selecionados[:qtd]

    if not multipla:
        return "❌ Nenhuma múltipla encontrada"

    msg = "🔥 GOUVEA BET – MÚLTIPLA\n\n"
    soma = 0

    for i, (home, away, entrada, prob, hora) in enumerate(multipla, 1):
        msg += f"{i}️⃣ {home} x {away}\n⏰ {hora}\n🎯 {entrada} ({prob}%)\n\n"
        soma += prob

    msg += f"📊 Confiança média: {int(soma/len(multipla))}%"

    return msg

# 🤖 BOT
def main():
    global last_update_id

    while True:
        try:
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                               params={"timeout":30,"offset":last_update_id}).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()

                # MULTIPLA
                if texto.startswith("multipla"):
                    partes = texto.split()

                    try:
                        qtd = int(partes[1])
                    except:
                        qtd = 3

                    periodo = partes[2] if len(partes) > 2 else None

                    if periodo == "manhã":
                        periodo = "manha"

                    enviar(gerar_multipla(qtd, periodo))
                    continue

                # INDIVIDUAL
                if "x" not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")

                resultado, sug_home, sug_away = analisar(home, away)

                if not resultado:
                    enviar("❌ Não encontrei esse jogo")
                    continue

                entrada, prob, forca, ev = resultado

                status = definir_status(forca, ev)
                analise_txt = interpretar_entrada(entrada)

                msg = f"""GOUVEA BET

{corrigir_nome(home)} x {corrigir_nome(away)}

🎯 Melhor entrada: {entrada}

📊 Prob: {prob}%
💰 EV: {ev}

⭐ Força: {forca}/10

{status}

🧠 {analise_txt}"""

                enviar(msg)

        except Exception as e:
            print("ERRO:", e)

        time.sleep(3)

if __name__ == "__main__":
    main()
