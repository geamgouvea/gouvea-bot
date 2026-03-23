import requests
import time
import threading
import re
from datetime import datetime, timedelta
import unicodedata
from difflib import SequenceMatcher

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

DIAS_BUSCA = 7
AUTO_INTERVALO = 1200  # 20 min

enviados_ids = set()
last_update_id = 0

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

# ================= SIMILARIDADE =================
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

# ================= EXTRAIR TIMES =================
def extrair_times(texto):
    partes = re.split(r"\s*x\s*", texto.lower())
    if len(partes) == 2:
        return partes[0].strip(), partes[1].strip()
    return None, None

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome_norm = normalizar(nome)
    data = req("https://v3.football.api-sports.io/teams", {"search": nome_norm})

    if not data or not data.get("response"):
        return None

    melhor_id = None
    melhor_score = 0

    for t in data["response"]:
        nome_api = normalizar(t["team"]["name"])
        score = similar(nome_norm, nome_api)

        if score > melhor_score:
            melhor_score = score
            melhor_id = t["team"]["id"]

    return melhor_id if melhor_score > 0.5 else None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(DIAS_BUSCA):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_busca
        })

        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score = (similar(home_n, h) + similar(away_n, a)) / 2
            score_inv = (similar(home_n, a) + similar(away_n, h)) / 2

            score_final = max(score, score_inv)

            if score_final > melhor_score:
                melhor_score = score_final
                melhor = j

    return melhor if melhor_score > 0.5 else None

# ================= ANALISAR =================
def analisar(home, away):
    fixture = buscar_fixture(home, away)

    if not fixture:
        return "❌ Jogo não encontrado"

    dt = datetime.fromisoformat(
        fixture["fixture"]["date"].replace("Z", "+00:00")
    ) - timedelta(hours=4)

    agora = datetime.utcnow() - timedelta(hours=4)

    if dt <= agora:
        return "❌ Jogo já iniciado"

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
        return "❌ Poucos dados"

    media = sum(gols) / len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / len(gols),
        "Over 2.5": sum(g >= 3 for g in gols) / len(gols),
        "Under 2.5": sum(g <= 2 for g in gols) / len(gols),
        "Ambas Marcam": btts / len(gols)
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    # filtro profissional
    if melhor == "Over 1.5" and (prob < 0.8 or media < 2.8):
        return None
    if melhor == "Over 2.5" and (prob < 0.72 or media < 2.4):
        return None
    if melhor == "Under 2.5" and (prob < 0.72 or media > 2.2):
        return None
    if melhor == "Ambas Marcam" and prob < 0.7:
        return None

    return f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {fixture["league"]["name"]}
📅 {dt.strftime("%d/%m")}
⏰ {dt.strftime("%H:%M")}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

# ================= AUTO =================
def auto():
    while True:
        try:
            enviados = 0

            for i in range(DIAS_BUSCA):
                data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {
                    "date": data_busca
                })

                if not data:
                    continue

                for j in data.get("response", []):
                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    h = j["teams"]["home"]["name"]
                    a = j["teams"]["away"]["name"]

                    # bloquear categorias ruins
                    if any(x in h.lower() for x in ["u21","u20","women"]) or \
                       any(x in a.lower() for x in ["u21","u20","women"]):
                        continue

                    dt = datetime.fromisoformat(
                        j["fixture"]["date"].replace("Z", "+00:00")
                    ) - timedelta(hours=4)

                    agora = datetime.utcnow() - timedelta(hours=4)
                    diff = (dt - agora).total_seconds() / 60

                    if diff < 20 or diff > 240:
                        continue

                    res = analisar(h, a)

                    if not res or "❌" in res:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL ELITE\n\n" + res)

                    enviados_ids.add(fid)
                    enviados += 1

                    if enviados >= 5:
                        break

                if enviados >= 5:
                    break

        except:
            pass

        time.sleep(AUTO_INTERVALO)

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

                h, a = extrair_times(texto)

                if not h or not a:
                    enviar("⚠️ Use: time x time")
                    continue

                res = analisar(h, a)

                if not res:
                    enviar("❌ Sem valor")
                else:
                    enviar("🧠 MANUAL\n\n" + res)

        except:
            pass

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
