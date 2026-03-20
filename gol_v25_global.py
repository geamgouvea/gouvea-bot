import requests
import time
import threading
from datetime import datetime, timedelta, timezone
from difflib import get_close_matches

# 🔐 COLE SEUS DADOS AQUI (RÁPIDO)
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

# 🌍 LIGAS FORMATADAS
def nome_liga(liga):
    liga_lower = liga.lower()

    if "brazil" in liga_lower:
        if "serie b" in liga_lower:
            return "🇧🇷 Campeonato Brasileiro Série B"
        return "🇧🇷 Campeonato Brasileiro Série A"

    elif "england" in liga_lower:
        return "🏴 Premier League"

    elif "spain" in liga_lower:
        return "🇪🇸 La Liga"

    elif "italy" in liga_lower:
        return "🇮🇹 Serie A"

    elif "germany" in liga_lower:
        return "🇩🇪 Bundesliga"

    elif "france" in liga_lower:
        return "🇫🇷 Ligue 1"

    # 🌏 MADRUGADA
    elif "china" in liga_lower:
        return "🇨🇳 Chinese Super League"

    elif "japan" in liga_lower:
        return "🇯🇵 J-League"

    elif "korea" in liga_lower:
        return "🇰🇷 K League"

    elif "saudi" in liga_lower:
        return "🇸🇦 Saudi Pro League"

    elif "australia" in liga_lower:
        return "🇦🇺 A-League"

    else:
        return f"🌍 {liga}"

# 🔍 BUSCA INTELIGENTE DE TIME
def buscar_time(nome):
    try:
        url = "https://v3.football.api-sports.io/teams"
        res = requests.get(url, headers=HEADERS, params={"search": nome}).json()

        if res["response"]:
            return res["response"][0]["team"]["id"]

        # fallback inteligente
        url_all = "https://v3.football.api-sports.io/teams?league=71&season=2023"
        res_all = requests.get(url_all, headers=HEADERS).json()

        nomes = [t["team"]["name"] for t in res_all["response"]]

        match = get_close_matches(nome, nomes, n=1, cutoff=0.6)

        if match:
            for t in res_all["response"]:
                if t["team"]["name"] == match[0]:
                    return t["team"]["id"]

        return None

    except:
        return None

# 📊 JOGOS
def pegar_jogos(team_id):
    try:
        url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
        res = requests.get(url, headers=HEADERS).json()
        return res["response"]
    except:
        return []

# 🔍 BUSCAR PARTIDA
def buscar_jogo(home, away):
    for i in range(0, 5):
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

# 🧠 ANÁLISE PROFISSIONAL
def analisar(home, away):
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

    if len(gols) == 0:
        return "Over 1.5", 55, 0.05, 5

    total_jogos = len(gols)

    media = sum(gols) / total_jogos
    over15 = sum(1 for g in gols if g >= 2) / total_jogos
    over25 = sum(1 for g in gols if g >= 3) / total_jogos
    over35 = sum(1 for g in gols if g >= 4) / total_jogos
    under25 = sum(1 for g in gols if g <= 2) / total_jogos
    under35 = sum(1 for g in gols if g <= 3) / total_jogos
    btts_rate = btts / total_jogos

    if over15 >= 0.80:
        return "Over 1.5", int(over15*100), 0.25, 8
    elif over25 >= 0.65:
        return "Over 2.5", int(over25*100), 0.30, 8
    elif over35 >= 0.60:
        return "Over 3.5", int(over35*100), 0.35, 9
    elif btts_rate >= 0.65:
        return "Ambas marcam", int(btts_rate*100), 0.25, 7
    elif under25 >= 0.65:
        return "Under 2.5", int(under25*100), 0.25, 8
    elif under35 >= 0.70:
        return "Under 3.5", int(under35*100), 0.20, 7
    else:
        return "Jogo indefinido", int(media*30), 0.05, 5

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

# 🔥 MODO AUTOMÁTICO (20 JOGOS)
def modo_automatico():
    while True:
        try:
            enviados = 0
            limite = 20

            data = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            url = f"https://v3.football.api-sports.io/fixtures?date={data}"
            res = requests.get(url, headers=HEADERS).json()

            for j in res.get("response", []):
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
⭐ Força: {forca}/10

{"🔥 FORTE" if forca >= 9 else "✅ BOM" if forca >=7 else "⚠️ MÉDIO"}"""

                    enviar(msg)
                    enviados += 1

            time.sleep(1800)

        except Exception as e:
            print("Erro auto:", e)
            time.sleep(60)

# 🚀 BOT PRINCIPAL
def main():
    enviar("🔥 GOUVEA BET PRO ONLINE")

    last = None

    while True:
        updates = ler(last)

        for u in updates:
            last = u["update_id"] + 1

            try:
                texto = u["message"]["text"].lower().replace(" vs ", " x ").replace(" X ", " x ")

                if "x" not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")

                liga, hora, dia = buscar_jogo(home.strip(), away.strip())
                entrada, prob, ev, forca = analisar(home.strip(), away.strip())

                resposta = f"""GOUVEA BET

{home} x {away}

🏆 {nome_liga(liga) if liga else "🌍 Desconhecida"}
📅 {dia if dia else "--"}
⏰ {hora if hora else "--"}

🎯 Melhor entrada: {entrada}

📊 Prob: {prob}%
💰 EV: {ev}

⭐ Força: {forca}/10

{"🔥 FORTE" if forca >= 9 else "✅ BOM" if forca >=7 else "⚠️ MÉDIO" if forca >=6 else "❌ EVITAR"}

🧠 Análise baseada em dados reais"""

                enviar(resposta)

            except Exception as e:
                print("Erro:", e)

        time.sleep(2)

if _name_ == "_main_":
    threading.Thread(target=modo_automatico).start()
    main()
