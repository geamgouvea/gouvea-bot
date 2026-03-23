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
JANELA_MIN = 20
JANELA_MAX = 720

enviados_ids = set()
last_update_id = None

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

# ================= SIMILAR =================
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

# ================= REQUEST =================
def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(30):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
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

    return melhor if melhor_score >= 0.65 else None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= DECISÃO INTELIGENTE =================
def escolher_mercado(media, probs):

    over15 = probs["Over 1.5"]
    over25 = probs["Over 2.5"]
    under25 = probs["Under 2.5"]
    btts = probs["Ambas Marcam"]

    # 🔥 PRIORIDADE REAL (equilíbrio)
    if media >= 2.8 and over25 >= 0.65:
        return "Over 2.5", over25

    if btts >= 0.70:
        return "Ambas Marcam", btts

    if media <= 2.2 and under25 >= 0.65:
        return "Under 2.5", under25

    if over15 >= 0.75:
        return "Over 1.5", over15

    # fallback inteligente
    melhor = max(probs, key=probs.get)
    return melhor, probs[melhor]

# ================= ANALISE =================
def analisar(home, away):

    fixture = buscar_fixture(home, away)
    if not fixture:
        return None

    home_id = fixture["teams"]["home"]["id"]
    away_id = fixture["teams"]["away"]["id"]

    jogos = historico(home_id) + historico(away_id)

    gols = []
    btts_count = 0

    for j in jogos:
        g1 = j["goals"]["home"]
        g2 = j["goals"]["away"]

        if g1 is None or g2 is None:
            continue

        gols.append(g1 + g2)

        if g1 > 0 and g2 > 0:
            btts_count += 1

    if not gols:
        return None

    total = len(gols)
    media = sum(gols) / total

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts_count / total
    }

    melhor, prob = escolher_mercado(media, probs)

    dt = datetime.fromisoformat(
        fixture["fixture"]["date"].replace("Z", "+00:00")
    ) - timedelta(hours=4)

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    if prob >= 0.80:
        nivel = "🔥 FORTE"
    elif prob >= 0.70:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    return {
        "msg": f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}
📅 {dt.strftime("%d/%m")}
⏰ {dt.strftime("%H:%M")}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}

{nivel}""",
        "prob": prob,
        "fixture_id": fixture["fixture"]["id"],
        "hora": dt
    }

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.utcnow() - timedelta(hours=4)
            candidatos = []

            for i in range(2):
                data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
                if not data:
                    continue

                for j in data.get("response", []):

                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    liga_nome = j["league"]["name"].lower()

                    if any(x in liga_nome for x in ["women", "u20", "u21"]):
                        continue

                    dt = datetime.fromisoformat(
                        j["fixture"]["date"].replace("Z", "+00:00")
                    ) - timedelta(hours=4)

                    diff = (dt - agora).total_seconds() / 60

                    if diff < JANELA_MIN or diff > JANELA_MAX:
                        continue

                    res = analisar(
                        j["teams"]["home"]["name"],
                        j["teams"]["away"]["name"]
                    )

                    if not res:
                        continue

                    candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            enviados = 0

            for c in candidatos:
                if enviados >= 5:
                    break

                enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + c["msg"])
                enviados_ids.add(c["fixture_id"])
                enviados += 1

        except:
            pass

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        h, a = texto.split("x")
        res = analisar(h.strip(), a.strip())

        if not res:
            return "❌ Não foi possível analisar o jogo"

        return "🧠 MANUAL\n\n" + res["msg"]

    except:
        return "⚠️ Use: time x time"

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

                if "x" in texto.lower():
                    enviar(manual(texto))
                else:
                    enviar("⚠️ Use: time x time")

        except:
            pass

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
