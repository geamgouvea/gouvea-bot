import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

AUTO_INTERVALO = 1200
DIAS_BUSCA = 7

enviados_ids = set()
last_update_id = None

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
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

# ================= BUSCAR TIME =================
def buscar_time(nome):
    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]
    return None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home_id, away_id):
    agora = datetime.now().astimezone()

    for i in range(DIAS_BUSCA):
        data_busca = (agora + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_busca
        })

        if not data:
            continue

        for j in data.get("response", []):
            h = j["teams"]["home"]["id"]
            a = j["teams"]["away"]["id"]

            if (home_id == h and away_id == a) or (home_id == a and away_id == h):

                dt = datetime.fromisoformat(
                    j["fixture"]["date"].replace("Z", "+00:00")
                ).astimezone()

                minutos = (dt - agora).total_seconds() / 60

                if 10 <= minutos <= 180:
                    return j

        time.sleep(0.3)

    return None

# ================= ANALISE =================
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return "❌ Times não encontrados"

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

    if not gols:
        return "❌ Sem dados suficientes"

    total_jogos = len(gols)
    media = sum(gols) / total_jogos

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total_jogos,
        "Over 2.5": sum(g >= 3 for g in gols) / total_jogos,
        "Under 2.5": sum(g <= 2 for g in gols) / total_jogos,
        "Ambas Marcam": btts / total_jogos
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    if melhor == "Over 1.5" and (prob < 0.80 or media < 2.8):
        if probs["Over 2.5"] > 0.72:
            melhor = "Over 2.5"
        else:
            melhor = "Ambas Marcam"
        prob = probs[melhor]

    fixture = buscar_fixture(home_id, away_id)

    liga = "Estimativa"
    data_txt = "--/--"
    hora = "--:--"

    if fixture:
        liga = fixture["league"]["name"]

        dt = datetime.fromisoformat(
            fixture["fixture"]["date"].replace("Z", "+00:00")
        ).astimezone()

        data_txt = dt.strftime("%d/%m")
        hora = dt.strftime("%H:%M")

    return f"""🔎 ANÁLISE

⚽ {home} x {away}
🏆 {liga}
📅 {data_txt}
⏰ {hora}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

# ================= AUTO =================
def auto():
    global enviados_ids

    while True:
        try:
            enviados = 0
            agora = datetime.now().astimezone()

            for i in range(DIAS_BUSCA):
                data_busca = (agora + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {
                    "date": data_busca
                })

                if not data:
                    continue

                for j in data.get("response", []):
                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    dt = datetime.fromisoformat(
                        j["fixture"]["date"].replace("Z", "+00:00")
                    ).astimezone()

                    minutos = (dt - agora).total_seconds() / 60

                    if not (10 <= minutos <= 180):
                        continue

                    nome_check = (
                        j["teams"]["home"]["name"] +
                        j["teams"]["away"]["name"]
                    ).lower()

                    if any(x in nome_check for x in ["u21", "u23", "women", "femin"]):
                        continue

                    res = analisar(
                        j["teams"]["home"]["name"],
                        j["teams"]["away"]["name"]
                    )

                    if "❌" in res:
                        continue

                    try:
                        prob = int(res.split("📊 ")[1].split("%")[0])
                        media = float(res.split("Média gols: ")[1])
                    except:
                        continue

                    if prob < 70 or media < 2.0:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL ELITE\n\n" + res)

                    enviados_ids.add(fid)
                    enviados += 1

                    if enviados >= 5:
                        break

                if enviados >= 5:
                    break

                time.sleep(0.3)

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
                params={"offset": last_update_id},
                timeout=10
            )

            if r.status_code != 200:
                time.sleep(3)
                continue

            data = r.json()

            for u in data.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "").strip()

                if " x " not in texto.lower():
                    continue

                try:
                    h, a = texto.split(" x ", 1)
                    enviar("🧠 MANUAL\n\n" + analisar(h.strip(), a.strip()))
                except:
                    enviar("⚠️ Use: time x time")

        except:
            pass

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
