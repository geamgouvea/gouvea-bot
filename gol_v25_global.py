import requests
import time
from datetime import datetime, timedelta, timezone

# 🔐 DADOS
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

# 🌍 LIGA BONITA
def nome_liga(liga):
    if not liga:
        return "🌍 Liga não encontrada"

    liga = liga.lower()

    if "brazil" in liga or "serie a" in liga:
        return "🇧🇷 Campeonato Brasileiro – Série A"
    elif "serie b" in liga:
        return "🇧🇷 Campeonato Brasileiro – Série B"
    elif "england" in liga or "premier" in liga:
        return "🏴 Campeonato Inglês – Premier League"
    elif "spain" in liga or "la liga" in liga:
        return "🇪🇸 Campeonato Espanhol – La Liga"
    elif "italy" in liga:
        return "🇮🇹 Campeonato Italiano – Serie A"
    elif "germany" in liga:
        return "🇩🇪 Campeonato Alemão – Bundesliga"
    elif "france" in liga:
        return "🇫🇷 Campeonato Francês – Ligue 1"
    elif "japan" in liga:
        return "🇯🇵 J-League"
    elif "china" in liga:
        return "🇨🇳 Super League"
    elif "korea" in liga:
        return "🇰🇷 K League"
    elif "saudi" in liga:
        return "🇸🇦 Saudi League"

    return f"🌍 {liga}"

# 🔍 BUSCAR TIME
def buscar_time(nome):
    try:
        url = "https://v3.football.api-sports.io/teams"
        res = requests.get(url, headers=HEADERS, params={"search": nome}, timeout=10)

        if res.status_code != 200:
            return None

        data = res.json()
        if data["response"]:
            return data["response"][0]["team"]["id"]

        return None
    except:
        return None

# 📊 PEGAR JOGOS
def pegar_jogos(team_id):
    try:
        url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
        res = requests.get(url, headers=HEADERS, timeout=10)

        if res.status_code != 200:
            return []

        return res.json().get("response", [])
    except:
        return []

# 🔍 BUSCAR LIGA, DATA E HORA
def buscar_info_jogo(home, away):
    try:
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

                    return liga, dt.strftime("%d/%m"), dt.strftime("%H:%M")

        return None, None, None
    except:
        return None, None, None

# 🧠 ANÁLISE INTELIGENTE
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
        melhor_score = -999

        for m, prob in mercados.items():
            odd = odds[m]
            ev = (prob * odd) - 1

            if prob < 0.60:
                continue

            if "Under 3.5" in m and prob > 0.80:
                continue

            penalidade = 0
            if odd < 1.50:
                penalidade = 0.15

            bonus = 0
            if m in ["Over 2.5", "Ambas marcam"]:
                bonus = 0.07

            score = ev + bonus - penalidade

            if score > melhor_score:
                melhor_score = score
                melhor = m
                melhor_prob = prob
                melhor_ev = ev

        forca = 9 if melhor_prob >= 0.70 else 8 if melhor_prob >= 0.65 else 7

        return melhor, int(melhor_prob*100), forca, round(melhor_ev, 2)

    except Exception as e:
        print("ERRO:", e)
        return "Over 1.5", 50, 5, 0.05

# 📲 ENVIAR
def enviar(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# 🤖 BOT
def main():
    enviar("🔥 GOUVEA BET ONLINE")

    last_update_id = None
    ultimo_texto = None

    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
            res = requests.get(url, params={"timeout":30,"offset":last_update_id}).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u or "text" not in u["message"]:
                    continue

                texto = u["message"]["text"].lower().strip()

                if texto == ultimo_texto:
                    continue

                ultimo_texto = texto

                texto = texto.replace(" vs ", " x ")

                if "x" not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")

                liga, data_jogo, hora_jogo = buscar_info_jogo(home.strip(), away.strip())
                entrada, prob, forca, ev = analisar(home.strip(), away.strip())

                msg = f"""GOUVEA BET

{home.title()} x {away.title()}

🏆 {nome_liga(liga)}
📅 {data_jogo if data_jogo else "--/--"}
⏰ {hora_jogo if hora_jogo else "--:--"}

🎯 Melhor entrada: {entrada}

📊 Prob: {prob}%
💰 EV: {ev}

⭐ Força: {forca}/10

{"✅ ENTRAR" if forca >= 8 else "⚠️ MÉDIO"}

🧠 Análise baseada em dados reais"""

                enviar(msg)

        except Exception as e:
            print("ERRO:", e)

        time.sleep(2)

# 🚀 START
if __name__ == "__main__":
    main()
