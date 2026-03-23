import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata
from difflib import SequenceMatcher
import re

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

DIAS_MANUAL = 10
DIAS_AUTO = 5
AUTO_INTERVALO = 1200  # 20 min

last_update_id = None
enviados = set()

# ================= BASE =================
def normalizar(txt):
    txt = txt.lower().strip()
    txt = unicodedata.normalize('NFKD', txt)
    return txt.encode('ASCII', 'ignore').decode('ASCII')

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("Erro API:", e)
    return None

def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("Erro Telegram:", e)

# ================= INPUT =================
def extrair(texto):
    partes = re.split(r"\s*[xX]\s*", texto)
    if len(partes) == 2:
        return partes[0].strip(), partes[1].strip()
    return None, None

# ================= BUSCA =================
def buscar_time(nome):
    nome_n = normalizar(nome)
    data = req("https://v3.football.api-sports.io/teams", {"search": nome_n})

    if not data or not data.get("response"):
        return None

    melhor = None
    score = 0

    for t in data["response"]:
        nome_api = normalizar(t["team"]["name"])
        s = similar(nome_n, nome_api)

        if s > score:
            score = s
            melhor = t["team"]["id"]

    return melhor if score > 0.4 else None

def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

def buscar_jogo(home, away, dias):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(dias):
        data_str = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_str
        })

        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            s1 = (similar(home_n, h) + similar(away_n, a)) / 2
            s2 = (similar(home_n, a) + similar(away_n, h)) / 2

            s = max(s1, s2)

            if s > melhor_score:
                melhor_score = s
                melhor = j

    return melhor if melhor_score > 0.35 else None

# ================= ANALISE =================
def analisar(home, away, dias):
    jogo = buscar_jogo(home, away, dias)

    if jogo:
        dt = datetime.fromisoformat(
            jogo["fixture"]["date"].replace("Z", "+00:00")
        ) - timedelta(hours=4)

        agora = datetime.utcnow() - timedelta(hours=4)

        if dt <= agora:
            return "❌ Jogo já iniciado"

        home_id = jogo["teams"]["home"]["id"]
        away_id = jogo["teams"]["away"]["id"]

        nome_home = jogo["teams"]["home"]["name"]
        nome_away = jogo["teams"]["away"]["name"]
        liga = jogo["league"]["name"]
        data_txt = dt.strftime("%d/%m")
        hora_txt = dt.strftime("%H:%M")

    else:
        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return "❌ Times não encontrados"

        nome_home = home
        nome_away = away
        liga = "Estimativa"
        data_txt = "--/--"
        hora_txt = "--:--"

    jogos = historico(home_id) + historico(away_id)

    if len(jogos) < 5:
        return "❌ Poucos dados"

    gols = []
    btts = 0

    for j in jogos:
        g1 = j["goals"]["home"]
        g2 = j["goals"]["away"]

        if g1 is None or g2 is None:
            continue

        gols.append(g1 + g2)

        if g1 > 0 and g2 > 0:
            btts += 1

    if not gols:
        return "❌ Sem dados"

    media = sum(gols) / len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / len(gols),
        "Over 2.5": sum(g >= 3 for g in gols) / len(gols),
        "Under 2.5": sum(g <= 2 for g in gols) / len(gols),
        "Ambas Marcam": btts / len(gols)
    }

    melhor = max(probs, key=probs.get)
    prob = int(probs[melhor] * 100)

    return f"""🔎 ANÁLISE

⚽ {nome_home} x {nome_away}
🏆 {liga}
📅 {data_txt}
⏰ {hora_txt}

🎯 {melhor}
📊 {prob}%
📈 Média gols: {round(media,2)}"""

# ================= AUTO =================
def auto():
    while True:
        try:
            enviados_loop = 0

            for i in range(DIAS_AUTO):
                data_str = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {
                    "date": data_str
                })

                if not data:
                    continue

                for j in data.get("response", []):
                    fid = j["fixture"]["id"]

                    if fid in enviados:
                        continue

                    h = j["teams"]["home"]["name"]
                    a = j["teams"]["away"]["name"]

                    if any(x in h.lower() for x in ["u21","u20","women"]) or \
                       any(x in a.lower() for x in ["u21","u20","women"]):
                        continue

                    dt = datetime.fromisoformat(
                        j["fixture"]["date"].replace("Z", "+00:00")
                    ) - timedelta(hours=4)

                    agora = datetime.utcnow() - timedelta(hours=4)
                    diff = (dt - agora).total_seconds() / 60

                    if diff < 10 or diff > 360:
                        continue

                    res = analisar(h, a, DIAS_AUTO)

                    if "❌" in res:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + res)

                    enviados.add(fid)
                    enviados_loop += 1

                    if enviados_loop >= 5:
                        break

                if enviados_loop >= 5:
                    break

        except Exception as e:
            print("Erro AUTO:", e)

        time.sleep(AUTO_INTERVALO)

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ONLINE")

    while True:
        try:
            params = {}
            if last_update_id:
                params["offset"] = last_update_id

            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params=params
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "")

                h, a = extrair(texto)

                if not h or not a:
                    enviar("⚠️ Use: time x time")
                    continue

                res = analisar(h, a, DIAS_MANUAL)
                enviar("🧠 MANUAL\n\n" + res)

        except Exception as e:
            print("Erro MAIN:", e)

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
