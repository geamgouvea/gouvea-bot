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

AUTO_INTERVALO = 1800  # 30 minutos
DIAS_BUSCA_AUTO = 2
DIAS_BUSCA_MANUAL = 10

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
    except Exception as e:
        print("Erro request:", e)
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print("Erro Telegram:", e)

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome_n = normalizar(nome)
    data = req("https://v3.football.api-sports.io/teams", {"search": nome_n})

    if not data or not data.get("response"):
        return None

    melhor = None
    score = 0

    for t in data["response"]:
        nome_api = normalizar(t["team"]["name"])
        s = similar(nome_n, nome_api)

        if s > score:
            score = s
            melhor = t["team"]["id"]

    return melhor if score > 0.5 else None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away, dias):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(dias):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_busca
        })

        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score = max(
                (similar(home_n, h) + similar(away_n, a)) / 2,
                (similar(home_n, a) + similar(away_n, h)) / 2
            )

            if score > melhor_score:
                melhor_score = score
                melhor = j

    return melhor if melhor_score > 0.6 else None

# ================= ANALISE =================
def analisar(home, away, dias):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

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

    # filtro equilibrado
    if melhor == "Over 1.5" and (prob < 0.72 or media < 2.4):
        return None
    if melhor == "Over 2.5" and prob < 0.70:
        return None
    if melhor == "Under 2.5" and prob < 0.70:
        return None
    if melhor == "Ambas Marcam" and prob < 0.65:
        return None

    fixture = buscar_fixture(home, away, dias)

    liga = "Estimativa"
    data_txt = "--/--"
    hora = "--:--"

    if fixture:
        liga = f"{fixture['league']['name']} ({fixture['league']['country']})"

        dt = datetime.fromisoformat(
            fixture["fixture"]["date"].replace("Z", "+00:00")
        ) - timedelta(hours=4)

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
    while True:
        try:
            enviados = 0

            for i in range(DIAS_BUSCA_AUTO):
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

                    # bloqueio correto
                    if any(x in h.lower() for x in ["u21", "u20", "u23", "women"]) or \
                       any(x in a.lower() for x in ["u21", "u20", "u23", "women"]):
                        continue

                    dt = datetime.fromisoformat(
                        j["fixture"]["date"].replace("Z", "+00:00")
                    ) - timedelta(hours=4)

                    agora = datetime.utcnow() - timedelta(hours=4)
                    diff = (dt - agora).total_seconds() / 60

                    if diff < 20 or diff > 1440:
                        continue

                    res = analisar(h, a, DIAS_BUSCA_AUTO)

                    if not res:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + res)

                    enviados_ids.add(fid)
                    enviados += 1

                    if enviados >= 5:
                        break

                if enviados >= 5:
                    break

            if enviados == 0:
                enviar("🤖 AUTO\n\n⚠️ Nenhum jogo de valor encontrado no momento")

        except Exception as e:
            print("Erro AUTO:", e)

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        texto = texto.replace(" X ", " x ").replace(" X", " x").replace("X ", "x ")
        h, a = texto.split("x")

        res = analisar(h.strip(), a.strip(), DIAS_BUSCA_MANUAL)

        if res:
            return "🧠 MANUAL\n\n" + res
        else:
            return "❌ Nenhuma entrada encontrada"

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

        except Exception as e:
            print("Erro MAIN:", e)

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
