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

# ================= NORMALIZAR =================
def normalizar(txt):
    txt = txt.lower().strip()
    txt = unicodedata.normalize('NFKD', txt)
    return txt.encode('ASCII', 'ignore').decode('ASCII')

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
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome_n = normalizar(nome)

    data = req("https://v3.football.api-sports.io/teams", {"search": nome_n})

    if not data or not data.get("response"):
        return None

    melhor = None
    melhor_score = 0

    for t in data["response"]:
        nome_api = normalizar(t["team"]["name"])
        score = similar(nome_n, nome_api)

        if nome_n in nome_api or nome_api in nome_n:
            score += 0.2

        if score > melhor_score:
            melhor_score = score
            melhor = t["team"]["id"]

    return melhor if melhor_score > 0.40 else None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home_id, away_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": home_id,
        "next": 20
    })

    if not data:
        return None

    for j in data.get("response", []):
        h = j["teams"]["home"]["id"]
        a = j["teams"]["away"]["id"]

        if (h == home_id and a == away_id) or (h == away_id and a == home_id):

            liga = normalizar(j["league"]["name"])

            if any(x in liga for x in ["women", "u20", "u21", "u23"]):
                continue

            return j

    return None

# ================= CLASSIFICAÇÃO =================
def classificar(melhor, prob, media):

    if melhor == "Over 1.5":
        if prob >= 0.78 and media >= 2.7:
            return "🔥 FORTE"
        elif prob >= 0.72 and media >= 2.4:
            return "⚖️ MÉDIA"
        else:
            return "⚠️ RISCO"

    if melhor == "Over 2.5":
        if prob >= 0.72 and media >= 2.9:
            return "🔥 FORTE"
        elif prob >= 0.68 and media >= 2.6:
            return "⚖️ MÉDIA"
        else:
            return "⚠️ RISCO"

    if melhor == "Under 2.5":
        if prob >= 0.78 and media <= 2.0:
            return "🔥 FORTE"
        elif prob >= 0.72 and media <= 2.3:
            return "⚖️ MÉDIA"
        else:
            return "⚠️ RISCO"

    if melhor == "Ambas Marcam":
        if prob >= 0.72 and media >= 2.7:
            return "🔥 FORTE"
        elif prob >= 0.68 and media >= 2.5:
            return "⚖️ MÉDIA"
        else:
            return "⚠️ RISCO"

    return "⚠️ RISCO"

# ================= ANALISE =================
def analisar(home, away, modo="manual"):
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

        gols.append(g1 + g2)

        if g1 > 0 and g2 > 0:
            btts += 1

    if not gols:
        return "❌ Sem dados"

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

    nivel = classificar(melhor, prob, media)

    fixture = buscar_fixture(home_id, away_id)

    if fixture:
        liga = f"{fixture['league']['name']} ({fixture['league']['country']})"

        dt = datetime.fromisoformat(
            fixture["fixture"]["date"].replace("Z", "+00:00")
        ) - timedelta(hours=4)

        data_txt = dt.strftime("%d/%m")
        hora = dt.strftime("%H:%M")

        confronto = f"{fixture['teams']['home']['name']} x {fixture['teams']['away']['name']}"
    else:
        liga = "Estimado"
        data_txt = "--/--"
        hora = "--:--"
        confronto = f"{home} x {away}"

    return f"""🔎 ANÁLISE

⚽ {confronto}
🏆 {liga}
📅 {data_txt}
⏰ {hora}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}

{nivel}"""

# ================= AUTO =================
def auto():
    while True:
        try:
            enviados = 0

            data = req("https://v3.football.api-sports.io/fixtures", {
                "next": 50
            })

            if data:
                for j in data.get("response", []):

                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    liga = normalizar(j["league"]["name"])

                    if any(x in liga for x in ["women","u20","u21","u23"]):
                        continue

                    h = j["teams"]["home"]["name"]
                    a = j["teams"]["away"]["name"]

                    res = analisar(h, a, modo="auto")

                    if "⚠️ RISCO" in res:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + res)

                    enviados_ids.add(fid)
                    enviados += 1

                    if enviados >= 5:
                        break

        except:
            pass

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        texto = texto.lower().replace(" vs ", " x ")

        if " x " not in texto:
            return "⚠️ Use: time x time"

        h, a = texto.split(" x ")

        return "🧠 MANUAL\n\n" + analisar(h.strip(), a.strip())

    except:
        return "⚠️ Erro. Use: time x time"

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
    threading.Thread(target=auto, daemon=True).start()
    main()
