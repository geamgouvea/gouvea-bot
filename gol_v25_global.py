import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata
from difflib import SequenceMatcher
import re

# ========= CONFIG =========
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

AUTO_INTERVALO = 1800

# ========= UTILS =========
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# ========= TELEGRAM =========
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": msg
            }
        )
    except:
        pass

# ========= BUSCAR JOGO =========
def buscar_jogo(home, away):

    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(10):  # 10 dias (equilibrado)
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})

        if not data or "response" not in data:
            continue

        for j in data["response"]:

            # apenas jogos não iniciados
            if j["fixture"]["status"]["short"] != "NS":
                continue

            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score = max(
                (similar(home_n, h) + similar(away_n, a)) / 2,
                (similar(home_n, a) + similar(away_n, h)) / 2
            )

            # boost inteligente
            if home_n.split()[0] in h or away_n.split()[0] in a:
                score += 0.15

            if score > melhor_score:
                melhor_score = score
                melhor = j

    # corte mínimo (EVITA jogo errado)
    if melhor_score < 0.50:
        return None

    return melhor

# ========= HISTÓRICO =========
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })

    if not data or "response" not in data:
        return []

    return data["response"]

# ========= ANALISAR =========
def analisar(home, away):

    fixture = buscar_jogo(home, away)

    if not fixture:
        return fallback(home, away)

    home_id = fixture["teams"]["home"]["id"]
    away_id = fixture["teams"]["away"]["id"]

    # evitar duplicação
    ids = set()
    jogos = []

    for j in historico(home_id) + historico(away_id):
        fid = j["fixture"]["id"]
        if fid not in ids:
            ids.add(fid)
            jogos.append(j)

    gols = []
    btts = 0

    for j in jogos:
        g1 = j["goals"]["home"]
        g2 = j["goals"]["away"]

        if g1 is None or g2 is None:
            continue

        total = g1 + g2
        gols.append(total)

        if g1 > 0 and g2 > 0:
            btts += 1

    if len(gols) < 5:
        return fallback(home, away)

    total = len(gols)
    media = sum(gols) / total

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts / total
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    if prob >= 0.75:
        nivel = "🔥 FORTE"
    elif prob >= 0.65:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    liga = fixture["league"]["name"]

    return f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}

📊 Probabilidades:
* Over 1.5: {int(probs["Over 1.5"]*100)}%
* Over 2.5: {int(probs["Over 2.5"]*100)}%
* Under 2.5: {int(probs["Under 2.5"]*100)}%
* Ambas: {int(probs["Ambas Marcam"]*100)}%

🎯 Melhor entrada: {melhor}
📈 {int(prob*100)}%

{nivel}
"""

# ========= FALLBACK =========
def fallback(home, away):
    return f"""🔎 ANÁLISE (Estimativa)

⚽ {home} x {away}

📊 Over 1.5: 65%
📊 Over 2.5: 50%
📊 Under 2.5: 50%
📊 Ambas: 55%

⚠️ Dados limitados"""

# ========= MANUAL =========
def manual(texto):

    partes = re.split(r"x|vs|versus", texto.lower())

    if len(partes) != 2:
        return "⚠️ Use: time x time"

    home = partes[0].strip()
    away = partes[1].strip()

    return analisar(home, away)

# ========= AUTO =========
def auto():
    while True:
        try:
            hoje = datetime.utcnow().strftime("%Y-%m-%d")
            data = req("https://v3.football.api-sports.io/fixtures", {"date": hoje})

            if not data or "response" not in data:
                enviar("⚠️ API sem resposta")
                time.sleep(AUTO_INTERVALO)
                continue

            enviados = 0

            for j in data["response"]:

                if j["fixture"]["status"]["short"] != "NS":
                    continue

                res = analisar(
                    j["teams"]["home"]["name"],
                    j["teams"]["away"]["name"]
                )

                enviar("🤖 AUTO\n\n" + res)
                enviados += 1

                if enviados >= 5:
                    break

            if enviados == 0:
                enviar("⚠️ Nenhum jogo encontrado")

        except Exception as e:
            enviar(f"Erro AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ========= MAIN =========
def main():
    last_update_id = None

    enviar("🤖 BOT ONLINE")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id or 0}
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "")

                resposta = manual(texto)
                enviar(resposta)

        except:
            pass

        time.sleep(2)

# ========= START =========
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
