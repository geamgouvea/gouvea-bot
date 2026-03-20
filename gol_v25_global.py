import requests
import time
import threading
from datetime import datetime, timedelta, timezone
from difflib import get_close_matches

# 🔐 DADOS
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

# 🌍 LIGAS
def nome_liga(liga):
    liga = liga.lower()

    if "brazil" in liga:
        return "🇧🇷 Campeonato Brasileiro – Série A"
    elif "england" in liga:
        return "🏴 Premier League"
    elif "spain" in liga:
        return "🇪🇸 La Liga"
    elif "italy" in liga:
        return "🇮🇹 Serie A"
    elif "germany" in liga:
        return "🇩🇪 Bundesliga"
    elif "france" in liga:
        return "🇫🇷 Ligue 1"
    elif "japan" in liga:
        return "🇯🇵 J-League"
    elif "china" in liga:
        return "🇨🇳 Chinese Super League"
    elif "korea" in liga:
        return "🇰🇷 K League"
    elif "saudi" in liga:
        return "🇸🇦 Saudi League"
    else:
        return f"🌍 {liga}"

# 🔍 BUSCAR TIME
def buscar_time(nome):
    try:
        url = "https://v3.football.api-sports.io/teams"
        res = requests.get(url, headers=HEADERS, params={"search": nome}, timeout=10).json()

        if res["response"]:
            return res["response"][0]["team"]["id"]

        nomes = ["flamengo","palmeiras","corinthians","vasco","gremio"]
        match = get_close_matches(nome.lower(), nomes, n=1, cutoff=0.6)

        if match:
            return buscar_time(match[0])

        return None
    except:
        return None

# 📊 JOGOS
def pegar_jogos(team_id):
    try:
        url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        return res.get("response", [])
    except:
        return []

# 🧠 CALCULAR MERCADOS + EV
def analisar(home, away):
    try:
        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return "Over 1.5", 55, 5, 0.05

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

        if not gols:
            return "Over 1.5", 55, 5, 0.05

        total = len(gols)

        over15 = sum(1 for g in gols if g >= 2) / total
        over25 = sum(1 for g in gols if g >= 3) / total
        over35 = sum(1 for g in gols if g >= 4) / total
        under25 = sum(1 for g in gols if g <= 2) / total
        under35 = sum(1 for g in gols if g <= 3) / total
        btts_rate = btts / total

        # odds simuladas (padrão mercado)
        odds = {
            "Over 1.5": 1.30,
            "Over 2.5": 1.80,
            "Over 3.5": 2.50,
            "Under 2.5": 1.80,
            "Under 3.5": 1.40,
            "Ambas marcam": 1.90
        }

        mercados = {
            "Over 1.5": over15,
            "Over 2.5": over25,
            "Over 3.5": over35,
            "Under 2.5": under25,
            "Under 3.5": under35,
            "Ambas marcam": btts_rate
        }

        melhor = None
        melhor_ev = -999

        for m, prob in mercados.items():
            ev = (prob * odds[m]) - 1

            if ev > melhor_ev:
                melhor_ev = ev
                melhor = m
                melhor_prob = prob

        forca = 9 if melhor_prob >= 0.70 else 8 if melhor_prob >= 0.65 else 7 if melhor_prob >= 0.60 else 6

        return melhor, int(melhor_prob*100), forca, round(melhor_ev, 2)

    except:
        return "Over 1.5", 50, 5, 0.05

# 🧠 OBSERVAÇÃO
def gerar_observacao(entrada, prob, forca):
    if "Over 3.5" in entrada:
        return "🧠 Jogo extremamente aberto"
    elif "Over" in entrada:
        return "🧠 Tendência de gols"
    elif "Under" in entrada:
        return "🧠 Jogo mais fechado"
    elif "Ambas" in entrada:
        return "🧠 Alta chance de ambos marcarem"
    else:
        return "🧠 Jogo equilibrado"

# 📲 TELEGRAM
def enviar(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except:
        pass

# 🤖 AUTOMÁTICO
def modo_automatico():
    while True:
        try:
            enviados = 0
            limite = 5

            data = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            url = f"https://v3.football.api-sports.io/fixtures?date={data}"
            res = requests.get(url, headers=HEADERS).json()

            agora = datetime.now(timezone.utc)

            for j in res.get("response", [])[:50]:

                try:
                    dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))

                    if dt < agora or dt > agora + timedelta(hours=6):
                        continue
                except:
                    continue

                if enviados >= limite:
                    break

                home = j["teams"]["home"]["name"]
                away = j["teams"]["away"]["name"]
                liga = j["league"]["name"]

                entrada, prob, forca, ev = analisar(home, away)

                if forca >= 7 and prob >= 65:
                    obs = gerar_observacao(entrada, prob, forca)

                    msg = f"""🔥 GOUVEA BET AUTO

{home} x {away}

🏆 {nome_liga(liga)}

🎯 Melhor entrada: {entrada}
📊 Prob: {prob}%
💰 EV: {ev}
⭐ Força: {forca}/10

✅ ENTRAR

{obs}"""

                    enviar(msg)
                    enviados += 1
                    time.sleep(10)

            time.sleep(3600)

        except:
            time.sleep(60)

# 🚀 MANUAL
def main():
    enviar("🔥 GOUVEA BET ONLINE")

    last = None

    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            res = requests.get(url, params={"timeout":30,"offset":last}).json()

            for u in res.get("result", []):
                last = u["update_id"] + 1

                if "message" not in u or "text" not in u["message"]:
                    continue

                texto = u["message"]["text"].lower().replace(" vs ", " x ")

                if "x" not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")

                entrada, prob, forca, ev = analisar(home, away)
                obs = gerar_observacao(entrada, prob, forca)

                status = "✅ ENTRAR" if forca >= 8 else "⚠️ MÉDIO" if forca >=6 else "⚠️ OBSERVAR"

                msg = f"""GOUVEA BET

{home} x {away}

🎯 Melhor entrada: {entrada}
📊 Prob: {prob}%
💰 EV: {ev}
⭐ Força: {forca}/10

{status}

{obs}"""

                enviar(msg)

        except:
            pass

        time.sleep(2)

# 🚀 START
if _name_ == "_main_":
    threading.Thread(target=modo_automatico).start()
    main()
