import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata
from difflib import SequenceMatcher

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

AUTO_INTERVALO = 1800

enviados_ids = set()
last_update_id = None

# ================= UTILS =================
def normalizar(texto):
    texto = texto.lower().strip()
    texto = unicodedata.normalize('NFKD', texto)
    return texto.encode('ASCII', 'ignore').decode('ASCII')

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        else:
            print("ERRO API:", r.status_code, r.text)
    except Exception as e:
        print("ERRO REQUEST:", e)
    return None

def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= BUSCAR JOGO (FIX REAL) =================
def buscar_fixture(home, away):

    home_n = normalizar(home)
    away_n = normalizar(away)

    def buscar_time(nome):
        data = req("https://v3.football.api-sports.io/teams", {
            "search": nome
        })
        if data and data.get("response"):
            return data["response"][0]["team"]["id"]
        return None

    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": home_id,
        "next": 20
    })

    if not data:
        return None

    melhor = None
    melhor_score = 0

    for j in data.get("response", []):

        h = normalizar(j["teams"]["home"]["name"])
        a = normalizar(j["teams"]["away"]["name"])

        score = max(
            (similar(home_n, h) + similar(away_n, a)) / 2,
            (similar(home_n, a) + similar(away_n, h)) / 2
        )

        if home_n.split()[0] in h:
            score += 0.3
        if away_n.split()[0] in a:
            score += 0.3

        if score > melhor_score:
            melhor_score = score
            melhor = j

    if melhor_score < 0.3:
        return None

    return melhor

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= DECISÃO =================
def escolher_entrada(probs):

    if probs["Over 2.5"] >= 0.65:
        return "Over 2.5", probs["Over 2.5"]

    if probs["Ambas Marcam"] >= 0.60:
        return "Ambas Marcam", probs["Ambas Marcam"]

    if probs["Over 1.5"] >= 0.75:
        return "Over 1.5", probs["Over 1.5"]

    melhor = max(probs, key=probs.get)
    return melhor, probs[melhor]

# ================= ANALISE =================
def analisar(home, away):

    fixture = buscar_fixture(home, away)

    if not fixture:
        return {
            "msg": f"❌ Jogo não encontrado\n\n🔍 {home} x {away}",
            "prob": 0,
            "fixture_id": None
        }

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
        return {"msg": "⚠️ Dados insuficientes", "prob": 0, "fixture_id": None}

    total = len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Ambas Marcam": btts / total
    }

    melhor, prob = escolher_entrada(probs)

    dt = fixture["fixture"]["date"]

    msg = f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}

🎯 Entrada: {melhor}
📊 Probabilidade: {int(prob*100)}%
"""

    return {
        "msg": msg,
        "prob": prob,
        "fixture_id": fixture["fixture"]["id"]
    }

# ================= MULTIPLA =================
def montar_multipla(candidatos):

    bons = [c for c in candidatos if c["prob"] >= 0.60]

    if len(bons) < 5:
        return None

    bons.sort(key=lambda x: x["prob"], reverse=True)

    selecionados = bons[:5]

    msg = "💰 MÚLTIPLA DO DIA\n\n"

    for c in selecionados:
        linha = c["msg"].split("\n")[2]
        msg += f"{linha}\n"

    msg += "\n💵 Entrada sugerida: R$5 a R$10"

    return msg

# ================= AUTO =================
def auto():
    while True:
        try:
            candidatos = []

            data = req("https://v3.football.api-sports.io/fixtures", {
                "next": 30
            })

            if not data:
                time.sleep(AUTO_INTERVALO)
                continue

            for j in data.get("response", []):

                fid = j["fixture"]["id"]

                if fid in enviados_ids:
                    continue

                res = analisar(
                    j["teams"]["home"]["name"],
                    j["teams"]["away"]["name"]
                )

                if res["prob"] > 0:
                    candidatos.append(res)
                    enviados_ids.add(fid)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            for c in candidatos[:5]:
                enviar("🤖 AUTO\n\n" + c["msg"])

            multi = montar_multipla(candidatos)
            if multi:
                enviar(multi)

        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        texto = normalizar(texto)

        if " x " in texto:
            home, away = texto.split(" x ")
        else:
            return "⚠️ Use: time x time"

        return "🧠 MANUAL\n\n" + analisar(home, away)["msg"]

    except:
        return "⚠️ Erro"

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT FINAL ONLINE")

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
                enviar(manual(texto))

        except:
            pass

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
