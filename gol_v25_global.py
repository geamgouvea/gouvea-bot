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

# ================= NORMALIZAR =================
def normalizar(texto):
    texto = texto.lower().strip()
    texto = unicodedata.normalize('NFKD', texto)
    texto = texto.encode('ASCII', 'ignore').decode('ASCII')

    # Correções inteligentes
    texto = texto.replace("munique", "munich")
    texto = texto.replace("bayern de munique", "bayern munich")
    texto = texto.replace("inter de milao", "inter")
    texto = texto.replace("roma", "as roma")
    texto = texto.replace("juventus", "juve")

    return texto

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

# ================= BUSCAR JOGO (CORRIGIDO) =================
def buscar_fixture(home, away):

    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    # 🔥 BUSCA 30 DIAS
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

            # 🔥 BOOST forte se bater palavra chave
            if home_n.split()[0] in h:
                score += 0.2
            if away_n.split()[0] in a:
                score += 0.2

            # 🔥 boost extra se contém parte do nome
            if home_n in h or h in home_n:
                score += 0.2
            if away_n in a or a in away_n:
                score += 0.2

            if score > melhor_score:
                melhor_score = score
                melhor = j

    # 🔥 LIMIAR REDUZIDO
    if melhor_score < 0.35:
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

        total = g1 + g2
        gols.append(total)

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

# ================= MANUAL =================
def manual(texto):
    try:
        texto = normalizar(texto)

        if " x " in texto:
            partes = texto.split(" x ")
        else:
            return "⚠️ Use: time x time"

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        return "🧠 MANUAL\n\n" + analisar(partes[0], partes[1])["msg"]

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
    main()
