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
def normalizar(texto):
    texto = texto.lower().strip()
    texto = unicodedata.normalize('NFKD', texto)
    return texto.encode('ASCII', 'ignore').decode('ASCII')

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

def parse_data(data_str):
    try:
        return datetime.fromisoformat(data_str.replace("Z", "+00:00"))
    except:
        return None

# ================= BUSCAR JOGO (CORRIGIDO DEFINITIVO) =================
def buscar_fixture(home, away):

    def buscar_time(nome):
        data = req("https://v3.football.api-sports.io/teams", {"search": nome})
        if data and data.get("response"):
            return data["response"][0]["team"]["id"]
        return None

    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": home_id,
        "next": 10
    })

    if not data:
        return None

    for j in data.get("response", []):
        h = j["teams"]["home"]["id"]
        a = j["teams"]["away"]["id"]

        if (h == home_id and a == away_id) or (h == away_id and a == home_id):
            return j

    return None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= DECISÃO =================
def escolher_entrada(media, probs):

    if media >= 3.0 and probs["Over 2.5"] >= 0.65:
        return "Over 2.5", probs["Over 2.5"]

    if probs["Ambas Marcam"] >= 0.65:
        return "Ambas Marcam", probs["Ambas Marcam"]

    if media <= 2.1 and probs["Under 2.5"] >= 0.70:
        return "Under 2.5", probs["Under 2.5"]

    if probs["Over 1.5"] >= 0.75:
        return "Over 1.5", probs["Over 1.5"]

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

    if len(gols) < 6:
        return None

    total = len(gols)
    media = sum(gols) / total

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts / total
    }

    melhor, prob = escolher_entrada(media, probs)

    dt = parse_data(fixture["fixture"]["date"])
    if not dt:
        return None

    dt_local = dt - timedelta(hours=4)

    if prob >= 0.80:
        nivel = "🔥 FORTE"
    elif prob >= 0.70:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return {
        "msg": f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}
📅 {dt_local.strftime("%d/%m")}
⏰ {dt_local.strftime("%H:%M")}

📊 Probabilidades:
* Over 1.5: {int(probs["Over 1.5"]*100)}%
* Over 2.5: {int(probs["Over 2.5"]*100)}%
* Under 2.5: {int(probs["Under 2.5"]*100)}%
* Ambas: {int(probs["Ambas Marcam"]*100)}%

🎯 Melhor entrada: {melhor}
📈 {int(prob*100)}%

{nivel}""",
        "prob": prob,
        "fixture_id": fixture["fixture"]["id"]
    }

# ================= MULTIPLA =================
def montar_multipla(candidatos):

    bons = [c for c in candidatos if c["prob"] >= 0.70]

    if len(bons) < 5:
        return None

    bons.sort(key=lambda x: x["prob"], reverse=True)
    selecionados = bons[:6]

    msg = "💰 MÚLTIPLA PROFISSIONAL\n\n"

    for c in selecionados:
        linha = c["msg"].split("\n")[2]
        entrada = c["msg"].split("Melhor entrada: ")[1].split("\n")[0]
        msg += f"{linha} → {entrada}\n"

    msg += "\n💵 Entrada sugerida: R$5 a R$10"

    return msg

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.utcnow()
            candidatos = []

            data = req("https://v3.football.api-sports.io/fixtures", {"next": 50})

            if not data:
                time.sleep(AUTO_INTERVALO)
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

                res = analisar(
                    j["teams"]["home"]["name"],
                    j["teams"]["away"]["name"]
                )

                if not res:
                    continue

                if res["prob"] >= 0.70:
                    candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            enviados = 0

            for c in candidatos[:5]:
                enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + c["msg"])
                enviados_ids.add(c["fixture_id"])
                enviados += 1

            multi = montar_multipla(candidatos)
            if multi:
                enviar(multi)

        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        texto = texto.lower()

        partes = re.split(r"x|vs|versus", texto)

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        h = partes[0].strip()
        a = partes[1].strip()

        res = analisar(h, a)

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
