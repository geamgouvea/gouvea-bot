import requests
import time
from datetime import datetime, timedelta, timezone

TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

ultimo_envio = {}
ultimo_auto = 0
last_update_id = None

# 🧠 APELIDOS / CORREÇÃO
apelidos = {
    "borussia": "Borussia Dortmund",
    "borússia": "Borussia Dortmund",
    "bayern": "Bayern Munich",
    "inter": "Inter Milan",
    "man city": "Manchester City",
    "manchester city": "Manchester City",
    "man united": "Manchester United",
    "psg": "Paris Saint Germain",
    "real": "Real Madrid",
    "barça": "Barcelona",
    "barcelona": "Barcelona",
    "juve": "Juventus",
    "milan": "AC Milan",
    "napoli": "Napoli",
    "flamengo": "Flamengo",
    "palmeiras": "Palmeiras"
}

def corrigir_nome(nome):
    nome = nome.lower().strip()

    for apelido, oficial in apelidos.items():
        if apelido in nome:
            return oficial

    return nome.title()

# 🌍 LIGA TOP
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

    return None

# 🔍 TIME
def buscar_time(nome):
    try:
        nome = corrigir_nome(nome)

        url = "https://v3.football.api-sports.io/teams"
        res = requests.get(url, headers=HEADERS, params={"search": nome})
        data = res.json()

        if data["response"]:
            return data["response"][0]["team"]["id"]

        nome = nome.replace("ã","a").replace("ç","c")

        res = requests.get(url, headers=HEADERS, params={"search": nome})
        data = res.json()

        if data["response"]:
            return data["response"][0]["team"]["id"]

        return None
    except:
        return None

# 📊 JOGOS
def pegar_jogos(team_id):
    try:
        url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
        res = requests.get(url, headers=HEADERS)
        return res.json().get("response", [])
    except:
        return []

# 🧠 ANÁLISE
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

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
        return None

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
        return None

    forca = 9 if melhor_prob >= 0.75 else 8 if melhor_prob >= 0.65 else 7

    return melhor, int(melhor_prob*100), forca, round(melhor_ev, 2)

# 📲 ENVIAR
def enviar(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg})

# ⚽ AUTO
def buscar_jogos():
    jogos = []
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    url = f"https://v3.football.api-sports.io/fixtures?date={hoje}"
    res = requests.get(url, headers=HEADERS).json()

    agora = datetime.now(timezone.utc)
    hora_local = (agora - timedelta(hours=4)).hour

    if hora_local < 10 or hora_local > 22:
        return []

    for j in res.get("response", [])[:40]:

        if j["fixture"]["status"]["short"] != "NS":
            continue

        liga = nome_liga(j["league"]["name"], j["league"]["country"])
        if not liga:
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))

        if (dt - agora).total_seconds() > 7200:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        dt -= timedelta(hours=4)

        jogos.append((home, away, liga, dt.strftime("%d/%m"), dt.strftime("%H:%M")))

    return jogos

# 🤖 BOT
def main():
    global ultimo_auto, last_update_id

    while True:
        try:
            # 🔥 AUTOMÁTICO
            if time.time() - ultimo_auto > 1800:

                jogos = buscar_jogos()
                enviados = 0

                for home, away, liga, data_jogo, hora_jogo in jogos:

                    chave = f"{home}-{away}-{data_jogo}"
                    if chave in ultimo_envio:
                        continue

                    resultado = analisar(home, away)
                    if not resultado:
                        continue

                    entrada, prob, forca, ev = resultado

                    if prob < 70 or ev < 0.10 or forca < 8:
                        continue

                    msg = f"""GOUVEA BET

{home} x {away}

🏆 {liga}
📅 {data_jogo}
⏰ {hora_jogo}

🎯 Melhor entrada: {entrada}

📊 Prob: {prob}%
💰 EV: {ev}

⭐ Força: {forca}/10

✅ ENTRAR

🧠 Análise baseada em dados reais"""

                    enviar(msg)

                    ultimo_envio[chave] = True
                    enviados += 1

                    if enviados >= 3:
                        break

                ultimo_auto = time.time()

            # 🔍 MANUAL
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                               params={"timeout":30,"offset":last_update_id}).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()

                if "x" not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")
                home = corrigir_nome(home)
                away = corrigir_nome(away)

                resultado = analisar(home, away)

                if not resultado:
                    enviar("❌ Não foi possível analisar esse jogo")
                    continue

                entrada, prob, forca, ev = resultado

                status = "✅ ENTRAR" if forca >= 8 and ev > 0 else "⚠️ MÉDIO" if forca == 7 else "❌ EVITAR"

                msg = f"""GOUVEA BET

{home} x {away}

🎯 Melhor entrada: {entrada}

📊 Prob: {prob}%
💰 EV: {ev}

⭐ Força: {forca}/10

{status}"""

                enviar(msg)

        except Exception as e:
            print("ERRO:", e)

        time.sleep(2)

if __name__ == "__main__":
    main()
