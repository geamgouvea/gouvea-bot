import requests
import time
import threading
from datetime import datetime, timedelta, timezone
from difflib import get_close_matches

# 🔐 SEUS DADOS
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

# 🌍 FORMATAR LIGA
def nome_liga(liga):
    liga = liga.lower()

    if "brazil" in liga:
        return "🇧🇷 Campeonato Brasileiro Série A"
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

        nomes = ["flamengo", "palmeiras", "corinthians", "vasco", "gremio"]
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

# 🔍 BUSCAR PARTIDA
def buscar_jogo(home, away):
    try:
        for i in range(3):
            data = (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d")
            url = f"https://v3.football.api-sports.io/fixtures?date={data}"
            res = requests.get(url, headers=HEADERS, timeout=10).json()

            for j in res.get("response", []):
                h = j["teams"]["home"]["name"].lower()
                a = j["teams"]["away"]["name"].lower()

                if home.lower() in h and away.lower() in a:
                    liga = j["league"]["name"]
                    dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
                    dt -= timedelta(hours=4)

                    return liga, dt.strftime("%H:%M"), dt.strftime("%d/%m")

        return None, None, None
    except:
        return None, None, None

# 🧠 ANÁLISE
def analisar(home, away):
    try:
        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return "Over 1.5", 55, 5

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
            return "Over 1.5", 55, 5

        total = len(gols)

        over15 = sum(1 for g in gols if g >= 2) / total
        over25 = sum(1 for g in gols if g >= 3) / total
        btts_rate = btts / total

        if over15 >= 0.75:
            return "Over 1.5", int(over15*100), 8
        elif over25 >= 0.65:
            return "Over 2.5", int(over25*100), 8
        elif btts_rate >= 0.65:
            return "Ambas marcam", int(btts_rate*100), 7
        else:
            return "Over 1.5", int(over15*100), 6

    except:
        return "Over 1.5", 50, 5

# 📲 TELEGRAM
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

def ler(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        res = requests.get(url, params={"timeout":30,"offset":offset}, timeout=35).json()
        return res.get("result", [])
    except:
        return []

# 🤖 AUTO
def modo_automatico():
    while True:
        try:
            enviados = 0
            limite = 20

            data = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            url = f"https://v3.football.api-sports.io/fixtures?date={data}"
            res = requests.get(url, headers=HEADERS, timeout=10).json()

            for j in res.get("response", [])[:50]:
                if enviados >= limite:
                    break

                home = j["teams"]["home"]["name"]
                away = j["teams"]["away"]["name"]
                liga = j["league"]["name"]

                entrada, prob, forca = analisar(home, away)

                if forca >= 6 and prob >= 65:
                    msg = f"""🔥 GOUVEA BET AUTO

{home} x {away}

🏆 {nome_liga(liga)}

🎯 {entrada}
📊 Prob: {prob}%
⭐ Força: {forca}/10"""

                    enviar(msg)
                    enviados += 1

            time.sleep(3600)

        except:
            time.sleep(60)

# 🚀 BOT
def main():
    enviar("🔥 GOUVEA BET ONLINE")

    last = None

    while True:
        try:
            updates = ler(last)

            for u in updates:
                last = u["update_id"] + 1

                # 🔒 proteção total
                if "message" not in u or "text" not in u["message"]:
                    continue

                texto = u["message"]["text"].lower().replace(" vs ", " x ")

                if "x" not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                partes = texto.split(" x ")

                if len(partes) != 2:
                    enviar("Formato correto: Time A x Time B")
                    continue

                home, away = partes

                liga, hora, dia = buscar_jogo(home.strip(), away.strip())
                entrada, prob, forca = analisar(home.strip(), away.strip())

                resposta = f"""GOUVEA BET

{home} x {away}

🏆 {nome_liga(liga) if liga else "🌍"}
📅 {dia if dia else "--"}
⏰ {hora if hora else "--"}

🎯 {entrada}
📊 Prob: {prob}%
⭐ Força: {forca}/10"""

                enviar(resposta)

        except:
            pass

        time.sleep(2)

# 🚀 START
if __name__ == "__main__":
    threading.Thread(target=modo_automatico).start()
    main()
