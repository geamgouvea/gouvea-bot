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
JANELA_MIN = 10
JANELA_MAX = 720

enviados_ids = set()
last_update_id = None

# ================= UTIL =================
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
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)

    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
    if not data or not data.get("response"):
        return None

    melhor = None
    melhor_score = 0

    for t in data["response"]:
        nome_api = normalizar(t["team"]["name"])
        score = similar(nome, nome_api)

        if score > melhor_score:
            melhor_score = score
            melhor = t["team"]["id"]

    return melhor

# ================= BUSCAR JOGO =================
def buscar_jogo(home, away):

    home_id = buscar_time(home)
    away_id = buscar_time(away)

    melhor = None
    melhor_score = 0

    for i in range(-3, 16):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        res = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not res:
            continue

        for j in res["response"]:
            h_id = j["teams"]["home"]["id"]
            a_id = j["teams"]["away"]["id"]

            if home_id and away_id:
                if (h_id == home_id and a_id == away_id) or (h_id == away_id and a_id == home_id):
                    return j

            score = 0
            if home_id and (h_id == home_id or a_id == home_id):
                score += 0.5
            if away_id and (h_id == away_id or a_id == away_id):
                score += 0.5

            if score > melhor_score:
                melhor_score = score
                melhor = j

    return melhor

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ANALISE =================
def analisar(home, away):

    fixture = buscar_jogo(home, away)

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

    if len(gols) < 4:
        return None

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

    dt = datetime.fromisoformat(fixture["fixture"]["date"].replace("Z", "+00:00"))
    dt = dt - timedelta(hours=4)

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return {
        "msg": f"""⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🎯 {melhor}
📊 {int(prob*100)}%""",
        "prob": prob,
        "full": f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}
📅 {dt.strftime("%d/%m")}
⏰ {dt.strftime("%H:%M")}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""
    }

# ================= MANUAL =================
def manual(texto):
    try:
        partes = re.split(r"x|vs|versus", texto.lower())

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        h = partes[0].strip()
        a = partes[1].strip()

        res = analisar(h, a)

        if not res:
            return "⚠️ Não encontrei dados suficientes, mas tente outro nome"

        return "🧠 MANUAL\n\n" + res["full"]

    except:
        return "⚠️ Erro na leitura"

# ================= AUTO + MÚLTIPLA =================
def auto():
    while True:
        try:
            agora = datetime.utcnow()
            candidatos = []

            for i in range(2):
                data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

                res = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
                if not res:
                    continue

                for j in res["response"]:
                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z", "+00:00")).replace(tzinfo=None)

                    diff = (dt - agora).total_seconds() / 60

                    if diff < JANELA_MIN or diff > JANELA_MAX:
                        continue

                    analise = analisar(
                        j["teams"]["home"]["name"],
                        j["teams"]["away"]["name"]
                    )

                    if not analise:
                        continue

                    if analise["prob"] >= 0.70:
                        candidatos.append(analise)
                        enviados_ids.add(fid)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            # ================= ENVIO NORMAL =================
            for c in candidatos[:3]:
                enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + c["full"])

            # ================= MÚLTIPLA =================
            if len(candidatos) >= 7:
                multi_msg = "🎰 MÚLTIPLA (7 jogos)\n\n"

                for c in candidatos[:7]:
                    multi_msg += c["msg"] + "\n\n"

                enviar(multi_msg)

            else:
                enviar("⚠️ Múltipla insuficiente hoje")

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

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
