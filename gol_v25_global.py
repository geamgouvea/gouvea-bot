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

DIAS_BUSCA_AUTO = 5
DIAS_BUSCA_MANUAL = 10
AUTO_INTERVALO = 1200

enviados_ids = set()
last_update_id = 0

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

# ================= SIMILARIDADE =================
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

# ================= REQUEST =================
def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("Erro API:", e)
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("Erro Telegram:", e)

# ================= EXTRAIR TIMES =================
def extrair_times(texto):
    partes = re.split(r"\s*[xX]\s*", texto)
    if len(partes) == 2:
        return partes[0].strip(), partes[1].strip()
    return None, None

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome_norm = normalizar(nome)
    data = req("https://v3.football.api-sports.io/teams", {"search": nome_norm})

    if not data or not data.get("response"):
        return None

    melhor = None
    score = 0

    for t in data["response"]:
        nome_api = normalizar(t["team"]["name"])
        s = similar(nome_norm, nome_api)

        if s > score:
            score = s
            melhor = t["team"]["id"]

    return melhor if score > 0.4 else None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away, dias):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(dias):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_busca
        })

        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score = (similar(home_n, h) + similar(away_n, a)) / 2
            score_inv = (similar(home_n, a) + similar(away_n, h)) / 2

            final = max(score, score_inv)

            if final > melhor_score:
                melhor_score = final
                melhor = j

    return melhor if melhor_score > 0.35 else None

# ================= ANALISE =================
def analisar(home, away, dias):
    fixture = buscar_fixture(home, away, dias)

    # ================= SE NÃO ACHAR JOGO =================
    if not fixture:
        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return "❌ Times não encontrados"

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

        media = sum(gols) / len(gols)

        probs = {
            "Over 1.5": sum(g >= 2 for g in gols) / len(gols),
            "Over 2.5": sum(g >= 3 for g in gols) / len(gols),
            "Under 2.5": sum(g <= 2 for g in gols) / len(gols),
            "Ambas Marcam": btts / len(gols)
        }

        melhor = max(probs, key=probs.get)
        prob = probs[melhor]

        return f"""🔎 ANÁLISE (SEM JOGO CONFIRMADO)

⚽ {home} x {away}
🏆 Estimativa
📅 --/--
⏰ --:--

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

    # ================= SE ACHAR JOGO =================
    dt = datetime.fromisoformat(
        fixture["fixture"]["date"].replace("Z", "+00:00")
    ) - timedelta(hours=4)

    agora = datetime.utcnow() - timedelta(hours=4)

    if dt <= agora:
        return "❌ Jogo já iniciado"

    home_id = fixture["teams"]["home"]["id"]
    away_id = fixture["teams"]["away"]["id"]

    jogos = historico(home_id) + historico(away_id)

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

    if len(gols) < 5:
        return "❌ Poucos dados"

    media = sum(gols) / len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / len(gols),
        "Over 2.5": sum(g >= 3 for g in gols) / len(gols),
        "Under 2.5": sum(g <= 2 for g in gols) / len(gols),
        "Ambas Marcam": btts / len(gols)
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    return f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {fixture["league"]["name"]}
📅 {dt.strftime("%d/%m")}
⏰ {dt.strftime("%H:%M")}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

# ================= AUTO =================
def auto():
    while True:
        try:
            enviados = 0

            for i in range(DIAS_BUSCA_AUTO):
                data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {
                    "date": data_busca
                })

                if not data:
                    continue

                for j in data.get("response", []):
                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
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

                    res = analisar(h, a, DIAS_BUSCA_AUTO)

                    if "❌" in res:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + res)

                    enviados_ids.add(fid)
                    enviados += 1

                    if enviados >= 5:
                        break

                if enviados >= 5:
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
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id}
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "")

                h, a = extrair_times(texto)

                if not h or not a:
                    enviar("⚠️ Use: time x time")
                    continue

                res = analisar(h, a, DIAS_BUSCA_MANUAL)
                enviar("🧠 MANUAL\n\n" + res)

        except Exception as e:
            print("Erro MAIN:", e)

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
