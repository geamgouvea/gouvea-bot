import requests
import time
import threading
from datetime import datetime, timedelta, timezone
import unicodedata
from difflib import SequenceMatcher
import re

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

def parse_data(data_str):
    try:
        return datetime.fromisoformat(data_str.replace("Z", "+00:00"))
    except:
        return None

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

# ================= BUSCAR JOGO (VERSÃO FUNCIONAL) =================
def buscar_fixture(home, away):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(20):  # 🔥 MAIS DIAS (resolve seu problema)
        data_busca = (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):

            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score1 = (similar(home_n, h) + similar(away_n, a)) / 2
            score2 = (similar(home_n, a) + similar(away_n, h)) / 2

            final = max(score1, score2)

            # 🔥 bônus forte (resolve "Bayern", "Inter", etc)
            if home_n.split()[0] in h:
                final += 0.15
            if away_n.split()[0] in a:
                final += 0.15

            if final > melhor_score:
                melhor_score = final
                melhor = j

    if melhor_score < 0.40:  # 🔥 MUITO MAIS FLEXÍVEL
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

    if probs["Under 2.5"] >= 0.70:
        return "Under 2.5", probs["Under 2.5"]

    if probs["Over 1.5"] >= 0.70:
        return "Over 1.5", probs["Over 1.5"]

    melhor = max(probs, key=probs.get)
    return melhor, probs[melhor]

# ================= ANALISE =================
def analisar(home, away):

    fixture = buscar_fixture(home, away)

    if not fixture:
        return f"""❌ Não foi possível analisar

🔍 {home} x {away}"""

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
        return f"""❌ Dados insuficientes

🔍 {home} x {away}"""

    total = len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts / total
    }

    melhor, prob = escolher_entrada(probs)

    dt = parse_data(fixture["fixture"]["date"])

    data_str = dt.strftime("%d/%m") if dt else "-"
    hora_str = dt.strftime("%H:%M") if dt else "-"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}
📅 {data_str}
⏰ {hora_str}

📊 Probabilidades:
* Over 1.5: {int(probs["Over 1.5"]*100)}%
* Over 2.5: {int(probs["Over 2.5"]*100)}%
* Under 2.5: {int(probs["Under 2.5"]*100)}%
* Ambas: {int(probs["Ambas Marcam"]*100)}%

🎯 Melhor entrada: {melhor}
📈 {int(prob*100)}%
"""

# ================= MANUAL =================
def manual(texto):
    try:
        partes = re.split(r"x|vs|versus", texto.lower())

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        return "🧠 MANUAL\n\n" + analisar(partes[0].strip(), partes[1].strip())

    except:
        return "⚠️ Erro no comando"

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.now(timezone.utc)

            for i in range(2):
                data_busca = (agora + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
                if not data:
                    continue

                for j in data.get("response", []):

                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    dt = parse_data(j["fixture"]["date"])
                    if not dt:
                        continue

                    diff = (dt - agora).total_seconds() / 60

                    if diff < JANELA_MIN or diff > JANELA_MAX:
                        continue

                    msg = analisar(
                        j["teams"]["home"]["name"],
                        j["teams"]["away"]["name"]
                    )

                    if "❌" not in msg:
                        enviar("🤖 AUTO\n\n" + msg)
                        enviados_ids.add(fid)

        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MAIN =================
def main():
    global last_update_id

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
                enviar(manual(texto))

        except:
            pass

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
