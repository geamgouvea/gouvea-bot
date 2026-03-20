import requests
import time
from datetime import datetime, timedelta, timezone

# 🔐 SEUS DADOS (já coloquei)
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

# 🌍 NOMES BONITOS DE LIGAS
def nome_liga(liga):
    liga_lower = liga.lower()

    if "brazil" in liga_lower:
        if "serie b" in liga_lower:
            return "🇧🇷 Campeonato Brasileiro Série B"
        return "🇧🇷 Campeonato Brasileiro Série A"

    elif "spain" in liga_lower or "la liga" in liga_lower:
        return "🇪🇸 Campeonato Espanhol – La Liga"

    elif "england" in liga_lower or "premier" in liga_lower:
        return "🏴 Campeonato Inglês – Premier League"

    elif "italy" in liga_lower or "serie a" in liga_lower:
        return "🇮🇹 Campeonato Italiano – Serie A"

    elif "germany" in liga_lower or "bundesliga" in liga_lower:
        return "🇩🇪 Campeonato Alemão – Bundesliga"

    elif "france" in liga_lower:
        return "🇫🇷 Campeonato Francês – Ligue 1"

    else:
        return f"🌍 {liga}"

# 🔍 BUSCAR TIME
def buscar_time(nome):
    try:
        url = f"https://v3.football.api-sports.io/teams?search={nome}"
        res = requests.get(url, headers=HEADERS).json()
        return res["response"][0]["team"]["id"]
    except:
        return None

# 📊 ÚLTIMOS JOGOS
def pegar_jogos(team_id):
    try:
        url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
        res = requests.get(url, headers=HEADERS).json()
        return res["response"]
    except:
        return []

# 🔍 BUSCAR PARTIDA
def buscar_jogo(home, away):
    for i in range(0, 7):
        data = (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://v3.football.api-sports.io/fixtures?date={data}"
        res = requests.get(url, headers=HEADERS).json()

        for j in res.get("response", []):
            h = j["teams"]["home"]["name"].lower()
            a = j["teams"]["away"]["name"].lower()

            if home.lower() in h and away.lower() in a:
                liga = j["league"]["name"]
                data_jogo = j["fixture"]["date"]

                dt = datetime.fromisoformat(data_jogo.replace("Z","+00:00"))
                dt -= timedelta(hours=4)

                return liga, dt.strftime("%H:%M"), dt.strftime("%d/%m")

    return None, None, None

# 🧠 ANÁLISE INTELIGENTE
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return "Over 1.5", 55, 0.05, 5

    jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

    gols = 0
    total = 0
    btts = 0
    over25 = 0

    for j in jogos:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            total_gols = g1 + g2

            gols += total_gols
            total += 1

            if g1 > 0 and g2 > 0:
                btts += 1

            if total_gols >= 3:
                over25 += 1
        except:
            continue

    if total == 0:
        return "Over 1.5", 55, 0.05, 5

    media = gols / total
    taxa_btts = btts / total
    taxa_over = over25 / total

    # 🎯 DECISÃO
    if taxa_over >= 0.65 and media >= 2.6:
        return "Over 2.5", int(taxa_over*100), 0.30, 8

    elif taxa_btts >= 0.65:
        return "Ambas marcam", int(taxa_btts*100), 0.25, 7

    elif taxa_over <= 0.40 and media <= 2.2:
        return "Under 2.5", int((1-taxa_over)*100), 0.20, 7

    else:
        return "Over 1.5", int(media*30), 0.10, 6

# 📲 TELEGRAM
def enviar(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

def ler(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    res = requests.get(url, params={"timeout":30,"offset":offset}).json()
    return res.get("result", [])

# 🚀 BOT ONLINE
def main():
    enviar("🔥 GOUVEA BET V25 GLOBAL ONLINE")

    last = None

    while True:
        updates = ler(last)

        for u in updates:
            last = u["update_id"] + 1

            try:
                texto = u["message"]["text"]

                if "x" not in texto.lower():
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")

                liga, hora, dia = buscar_jogo(home.strip(), away.strip())
                entrada, prob, ev, forca = analisar(home.strip(), away.strip())

                if liga:
                    resposta = f"""GOUVEA BET

{home} x {away}

🏆 {nome_liga(liga)}
📅 {dia}
⏰ {hora}

🎯 Melhor entrada: {entrada}

📊 Prob: {prob}%
💰 EV: {ev}

⭐ Força: {forca}/10

{"✅ ENTRAR" if forca >= 8 else "⚠️ MÉDIO" if forca >=6 else "❌ EVITAR"}

🧠 Análise baseada em dados reais"""
                else:
                    resposta = f"""GOUVEA BET

{home} x {away}

❌ Jogo não encontrado

🎯 Entrada: {entrada}

📊 Prob: {prob}%
⭐ Força: {forca}/10

❌ EVITAR"""

                enviar(resposta)

            except Exception as e:
                print("Erro:", e)

        time.sleep(2)

if __name__ == "__main__":
    main()
