import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata
import re

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

AUTO_INTERVALO = 1800
JANELA_MIN = 10
JANELA_MAX = 720

enviados_ids = set()
last_update_id = None

# ================= UTILS =================
def normalizar(txt):
    txt = txt.lower().strip()
    txt = unicodedata.normalize('NFKD', txt)
    return txt.encode('ASCII', 'ignore').decode('ASCII')

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

def parse_data(dt):
    try:
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except:
        return None

# ================= BUSCAR FIXTURE (10 DIAS) =================
def buscar_fixture(home, away):

    def buscar_id(nome):
        data = req("https://v3.football.api-sports.io/teams", {"search": nome})
        if not data or not data.get("response"):
            return None
        return data["response"][0]["team"]["id"]

    home_id = buscar_id(home)
    away_id = buscar_id(away)

    if not home_id or not away_id:
        return None

    melhor = None
    melhor_score = 0

    for i in range(10):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_busca
        })

        if not data or not data.get("response"):
            continue

        for j in data["response"]:
            h = j["teams"]["home"]["id"]
            a = j["teams"]["away"]["id"]

            # match exato
            if (h == home_id and a == away_id) or (h == away_id and a == home_id):
                return j

            # fallback inteligente
            nome_h = normalizar(j["teams"]["home"]["name"])
            nome_a = normalizar(j["teams"]["away"]["name"])

            home_n = normalizar(home)
            away_n = normalizar(away)

            score = 0

            if home_n in nome_h or home_n in nome_a:
                score += 0.5
            if away_n in nome_h or away_n in nome_a:
                score += 0.5

            if score > melhor_score:
                melhor_score = score
                melhor = j

    if melhor_score >= 0.5:
        return melhor

    return None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data["response"] if data and data.get("response") else []

# ================= DECISÃO =================
def escolher(probs):

    if probs["Over 2.5"] >= 0.65:
        return "Over 2.5", probs["Over 2.5"]

    if probs["Ambas"] >= 0.65:
        return "Ambas Marcam", probs["Ambas"]

    if probs["Under 2.5"] >= 0.75:
        return "Under 2.5", probs["Under 2.5"]

    if probs["Over 2.5"] >= 0.55:
        return "Over 2.5", probs["Over 2.5"]

    if probs["Ambas"] >= 0.55:
        return "Ambas Marcam", probs["Ambas"]

    return "Over 1.5", probs["Over 1.5"]

# ================= ANALISE =================
def analisar(home, away):

    fixture = buscar_fixture(home, away)
    if not fixture:
        return None

    h_id = fixture["teams"]["home"]["id"]
    a_id = fixture["teams"]["away"]["id"]

    jogos = historico(h_id) + historico(a_id)

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

    if len(gols) < 6:
        return None

    total = len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas": btts / total
    }

    entrada, prob = escolher(probs)

    dt = parse_data(fixture["fixture"]["date"])
    if not dt:
        return None

    dt = dt - timedelta(hours=4)

    if prob >= 0.80:
        nivel = "🔥 FORTE"
    elif prob >= 0.70:
        nivel = "⚖️ MÉDIA"
    elif prob >= 0.60:
        nivel = "⚠️ RISCO"
    else:
        nivel = "❌ DESCARTAR"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return {
        "msg": f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}
📅 {dt.strftime("%d/%m")}
⏰ {dt.strftime("%H:%M")}

📊 Probabilidades:
* Over 1.5: {int(probs["Over 1.5"]*100)}%
* Over 2.5: {int(probs["Over 2.5"]*100)}%
* Under 2.5: {int(probs["Under 2.5"]*100)}%
* Ambas: {int(probs["Ambas"]*100)}%

🎯 Melhor entrada: {entrada}
📈 {int(prob*100)}%

{nivel}""",
        "prob": prob,
        "fixture_id": fixture["fixture"]["id"]
    }

# ================= MULTIPLA =================
def multipla(lista):
    bons = [x for x in lista if x["prob"] >= 0.70]

    if len(bons) < 5:
        return None

    bons.sort(key=lambda x: x["prob"], reverse=True)
    escolhidos = bons[:6]

    msg = "💰 MÚLTIPLA PROFISSIONAL\n\n"

    for c in escolhidos:
        try:
            jogo = c["msg"].split("\n")[2]
            entrada = c["msg"].split("Melhor entrada: ")[1].split("\n")[0]
        except:
            continue

        msg += f"{jogo} → {entrada}\n"

    msg += "\n💵 Entrada sugerida: R$5 a R$10"

    return msg

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.utcnow()
            candidatos = []

            data = req("https://v3.football.api-sports.io/fixtures", {"next": 50})

            if not data or not data.get("response"):
                time.sleep(AUTO_INTERVALO)
                continue

            for j in data["response"]:
                fid = j["fixture"]["id"]

                if fid in enviados_ids:
                    continue

                dt = parse_data(j["fixture"]["date"])
                if not dt:
                    continue

                diff = (dt - agora).total_seconds() / 60

                if diff < JANELA_MIN or diff > JANELA_MAX:
                    continue

                res = analisar(
                    j["teams"]["home"]["name"],
                    j["teams"]["away"]["name"]
                )

                if res and res["prob"] >= 0.70:
                    candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            for c in candidatos[:5]:
                enviar("🤖 AUTO\n\n" + c["msg"])
                enviados_ids.add(c["fixture_id"])

            multi = multipla(candidatos)
            if multi:
                enviar(multi)

        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(txt):
    partes = re.split(r"x|vs|versus", txt.lower())

    if len(partes) != 2:
        return "⚠️ Use: time x time"

    res = analisar(partes[0].strip(), partes[1].strip())

    if not res:
        return "❌ Não foi possível analisar o jogo"

    return "🧠 MANUAL\n\n" + res["msg"]

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

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
