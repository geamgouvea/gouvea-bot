import requests
import time
import threading
from datetime import datetime, timedelta, timezone
from difflib import get_close_matches

# 🔐 SEUS DADOS (COLOCA OS SEUS AQUI)
TTOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"


HEADERS = {"x-apisports-key": API_KEY}

# 🌍 LIGAS FORMATADAS
def nome_liga(liga):
    liga = liga.lower()

    if "brazil" in liga:
        if "serie b" in liga:
            return "🇧🇷 Campeonato Brasileiro Série B"
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
    elif "china" in liga:
        return "🇨🇳 Chinese Super League"
    elif "japan" in liga:
        return "🇯🇵 J-League"
    elif "korea" in liga:
        return "🇰🇷 K League"
    elif "saudi" in liga:
        return "🇸🇦 Saudi Pro League"
    elif "australia" in liga:
        return "🇦🇺 A-League"
    else:
        return f"🌍 {liga}"

# 🔍 BUSCAR TIME INTELIGENTE
def buscar_time(nome):
    try:
        url = "https://v3.football.api-sports.io/teams"
        res = requests.get(url, headers=HEADERS, params={"search": nome}, timeout=10).json()

        if res["response"]:
            return res["response"][0]["team"]["id"]

        # fallback simples
        nomes = ["flamengo", "palmeiras", "corinthians", "barcelona", "real madrid"]
        match = get_close_matches(nome.lower(), nomes, n=1, cutoff=0.6)

        if match:
            return buscar_time(match[0])

        return None

    except Exception as e:
        print("Erro buscar_time:", e)
        return None

# 📊 PEGAR JOGOS
def pegar_jogos(team_id):
    try:
        url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        return res.get("response", [])
    except Exception as e:
        print("Erro pegar_jogos:", e)
        return []

# 🔍 BUSCAR PARTIDA
def buscar_jogo(home, away):
    try:
        for i in range(0, 3):
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

    except Exception as e:
        print("Erro buscar_jogo:", e)
        return None, None, None

# 🧠 ANÁLISE
def analisar(home, away):
    try:
        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return "Over 1.5", 55, 0.05, 5

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
            return "Over 1.5", 55, 0.05, 5

        total_jogos = len(gols)

        over15 = sum(1 for g in gols if g >= 2) / total_jogos
        over25 = sum(1 for g in gols if g >= 3) / total_jogos
        btts_rate = btts / total_jogos

        if over15 >= 0.80:
            return "Over 1.5", int(over15*100), 0.25, 8
        elif over25 >= 0.65:
            return "Over 2.5", int(over25*100), 0.30, 8
        elif btts_rate >= 0.65:
            return "Ambas marcam", int(btts_rate*100), 0.25, 7
        else:
            return "Over 1.5", int(over15*100), 0.10, 6

    except Exception as e:
        print("Erro analisar:", e)
        return "Over 1.5", 50, 0.05, 5

# 📲 TELEGRAM
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print("Erro Telegram:", e)

def ler(offset=None):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
        res = requests.get(url, params={"timeout":30,"offset":offset}, timeout=35).json()
        return res.get("result", [])
    except Exception as e:
        print("Erro ler:", e)
        return []

# 🔥 MODO AUTOMÁTICO
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
                hora = j["fixture"]["date"]

                entrada, prob, ev, forca = analisar(home, away)

                if forca >= 6 and prob >= 65:
                    dt = datetime.fromisoformat(hora.replace("Z","+00:00"))
                    dt -= timedelta(hours=4)

                    msg = f"""🔥 GOUVEA BET AUTO

{home} x {away}

🏆 {nome_liga(liga)}
📅 {dt.strftime("%d/%m")}
⏰ {dt.strftime("%H:%M")}

🎯 Entrada: {entrada}
📊 Prob: {prob}%
💰 EV: {ev}
⭐ Força: {forca}/10"""

                    enviar(msg)
                    enviados += 1

            time.sleep(3600)

        except Exception as e:
            print("Erro automático:", e)
            time.sleep(60)

# 🚀 BOT PRINCIPAL
def main():
    enviar("🔥 GOUVEA BET ONLINE")

    last = None

    while True:
        try:
            updates = ler(last)

            for u in updates:
                last = u["update_id"] + 1

                texto = u["message"]["text"].lower().replace(" vs ", " x ")

                if "x" not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")

                liga, hora, dia = buscar_jogo(home.strip(), away.strip())
                entrada, prob, ev, forca = analisar(home.strip(), away.strip())

                resposta = f"""GOUVEA BET

{home} x {away}

🏆 {nome_liga(liga) if liga else "🌍"}
📅 {dia if dia else "--"}
⏰ {hora if hora else "--"}

🎯 {entrada}
📊 Prob: {prob}%
⭐ Força: {forca}/10"""

                enviar(resposta)

        except Exception as e:
            print("Erro main:", e)

        time.sleep(2)

# 🚀 INICIAR
if _name_ == "_main_":
    try:
        threading.Thread(target=modo_automatico).start()
        main()
    except Exception as e:
        print("ERRO GERAL:", e)
        time.sleep(10)
