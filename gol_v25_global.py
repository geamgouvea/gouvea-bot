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

AUTO_INTERVALO = 1800

# ================= UTILS =================
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
    except:
        pass
    return None

def enviar(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

# ================= BUSCA INTELIGENTE =================
def buscar_jogo(home, away):

    home = normalizar(home)
    away = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(3):  # hoje + 2 dias
        data = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        res = req("https://v3.football.api-sports.io/fixtures", {"date": data})
        if not res:
            continue

        for j in res["response"]:
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score = (
                similar(home, h) +
                similar(away, a)
            ) / 2

            # bônus por palavra chave
            if home.split()[0] in h:
                score += 0.1
            if away.split()[0] in a:
                score += 0.1

            if score > melhor_score:
                melhor_score = score
                melhor = j

    return melhor  # SEM BLOQUEIO

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data["response"] if data else []

# ================= ANÁLISE =================
def analisar(home, away):

    jogo = buscar_jogo(home, away)

    if not jogo:
        return "❌ Nenhum jogo parecido encontrado"

    home_id = jogo["teams"]["home"]["id"]
    away_id = jogo["teams"]["away"]["id"]

    jogos = historico(home_id) + historico(away_id)

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

    if len(gols) < 4:
        return "⚠️ Poucos dados, análise fraca"

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

    if prob >= 0.80:
        nivel = "🔥 FORTE"
    elif prob >= 0.65:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ ARRISCADO"

    return f"""🔎 ANÁLISE

⚽ {jogo["teams"]["home"]["name"]} x {jogo["teams"]["away"]["name"]}
🏆 {jogo["league"]["name"]}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média: {round(media,2)}

{nivel}"""

# ================= MANUAL =================
def manual(texto):

    partes = re.split(r"x|vs|versus", texto.lower())

    if len(partes) != 2:
        return "⚠️ Use: time x time"

    home = partes[0].strip()
    away = partes[1].strip()

    return analisar(home, away)

# ================= MULTIPLA =================
def gerar_multipla():

    jogos = []

    res = req("https://v3.football.api-sports.io/fixtures", {
        "date": datetime.utcnow().strftime("%Y-%m-%d")
    })

    if not res:
        return "❌ Erro ao buscar jogos"

    for j in res["response"][:30]:

        analise = analisar(
            j["teams"]["home"]["name"],
            j["teams"]["away"]["name"]
        )

        if "ANÁLISE" in analise:
            jogos.append(analise)

        if len(jogos) >= 7:
            break

    if len(jogos) < 7:
        return "⚠️ Poucos jogos para múltipla"

    return "🎰 MÚLTIPLA (7 jogos)\n\n" + "\n\n".join(jogos[:7])

# ================= AUTO =================
def auto():
    while True:
        try:
            msg = gerar_multipla()
            enviar(msg)
        except Exception as e:
            enviar(f"Erro: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MAIN =================
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

                if texto.lower() == "multipla":
                    enviar(gerar_multipla())
                else:
                    enviar(manual(texto))

        except:
            pass

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
