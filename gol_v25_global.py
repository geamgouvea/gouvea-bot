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
JANELA_MIN = 5
JANELA_MAX = 720

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
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= BUSCAR JOGO =================
def buscar_fixture(home, away):
    home_n = normalizar(home)
    away_n = normalizar(away)

    palavras_home = home_n.split()
    palavras_away = away_n.split()

    melhor = None
    melhor_score = 0

    for i in range(30):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})

        if not data:
            continue

        for j in data.get("response", []):

            status = j["fixture"]["status"]["short"]
            if status in ["FT", "CANC"]:
                continue

            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score1 = (similar(home_n, h) + similar(away_n, a)) / 2
            score2 = (similar(home_n, a) + similar(away_n, h)) / 2
            score = max(score1, score2)

            for p in palavras_home:
                if p in h or p in a:
                    score += 0.15

            for p in palavras_away:
                if p in h or p in a:
                    score += 0.15

            if palavras_home and palavras_home[0] in h:
                score += 0.2
            if palavras_away and palavras_away[0] in a:
                score += 0.2

            if score > melhor_score:
                melhor_score = score
                melhor = j

    if melhor_score < 0.30:
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

    if probs["Ambas Marcam"] >= 0.62:
        return "Ambas Marcam", probs["Ambas Marcam"]

    if probs["Under 2.5"] >= 0.78:
        return "Under 2.5", probs["Under 2.5"]

    if probs["Over 2.5"] >= 0.55:
        return "Over 2.5", probs["Over 2.5"]

    if probs["Ambas Marcam"] >= 0.55:
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
            "entrada": "-",
            "nivel": "erro",
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
        return {"msg": "⚠️ Dados insuficientes", "prob": 0, "entrada": "-", "nivel": "erro", "fixture_id": None}

    total = len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts / total
    }

    melhor, prob = escolher_entrada(probs)

    if prob >= 0.80:
        nivel = "🔥 FORTE"
    elif prob >= 0.68:
        nivel = "⚖️ MÉDIA"
    elif prob >= 0.58:
        nivel = "⚠️ RISCO"
    else:
        nivel = "❌ DESCARTAR"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    msg = f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}

📊 Probabilidades:
* Over 1.5: {int(probs["Over 1.5"]*100)}%
* Over 2.5: {int(probs["Over 2.5"]*100)}%
* Under 2.5: {int(probs["Under 2.5"]*100)}%
* Ambas: {int(probs["Ambas Marcam"]*100)}%

🎯 Melhor entrada: {melhor}
📈 {int(prob*100)}%

{nivel}"""

    return {
        "msg": msg,
        "prob": prob,
        "entrada": melhor,
        "nivel": nivel,
        "fixture_id": fixture["fixture"]["id"]
    }

# ================= MULTIPLA =================
def montar_multipla(candidatos):

    bons = [c for c in candidatos if c["nivel"] in ["🔥 FORTE", "⚖️ MÉDIA"]]

    if len(bons) < 5:
        return None

    bons.sort(key=lambda x: x["prob"], reverse=True)

    selecionados = bons[:5]

    msg = "💰 MÚLTIPLA PROFISSIONAL\n\n"

    for c in selecionados:
        linha = c["msg"].split("\n")[2]
        msg += f"{linha} → {c['entrada']}\n"

    msg += "\n💵 Entrada sugerida: R$5 a R$10"

    return msg

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.now()
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

                    dt = j["fixture"]["date"]
                    dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))

                    diff = (dt - agora).total_seconds() / 60

                    if diff < JANELA_MIN or diff > JANELA_MAX:
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

        if " x " not in texto:
            return "⚠️ Use: time x time"

        home, away = texto.split(" x ")

        return "🧠 MANUAL\n\n" + analisar(home, away)["msg"]

    except:
        return "⚠️ Erro no comando"

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT PROFISSIONAL ONLINE")

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
