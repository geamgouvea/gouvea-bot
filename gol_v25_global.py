import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata
from difflib import SequenceMatcher
import re

print("🚀 BOT INICIANDO...")

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

# ================= NORMALIZAÇÃO =================
def normalizar(texto):
    texto = texto.lower().strip()
    texto = unicodedata.normalize('NFKD', texto)
    return texto.encode('ASCII', 'ignore').decode('ASCII')

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

# ================= REQUEST =================
def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            print("❌ API ERRO:", r.status_code, r.text)
    except Exception as e:
        print("❌ REQUEST ERRO:", e)
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("❌ TELEGRAM ERRO:", e)

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome_n = normalizar(nome)

    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
    if not data:
        return None

    melhor_id = None
    melhor_score = 0

    for t in data.get("response", []):
        nome_api = normalizar(t["team"]["name"])
        score = similar(nome_n, nome_api)

        # 🔥 evita feminino
        if "women" in nome_api or "w" in nome_api:
            continue

        if score > melhor_score:
            melhor_score = score
            melhor_id = t["team"]["id"]

    if melhor_score < 0.55:
        return None

    return melhor_id

# ================= BUSCAR JOGO =================
def buscar_fixture(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        print("❌ TIME NÃO ENCONTRADO")
        return None

    for i in range(10):
        data_str = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_str
        })

        if not data:
            continue

        for jogo in data.get("response", []):
            h = jogo["teams"]["home"]["id"]
            a = jogo["teams"]["away"]["id"]

            if (h == home_id and a == away_id) or (h == away_id and a == home_id):
                return jogo

    return None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ANÁLISE =================
def analisar(home, away):
    print(f"🔎 {home} x {away}")

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

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    dt = datetime.strptime(fixture["fixture"]["date"][:19], "%Y-%m-%dT%H:%M:%S")
    dt_local = dt - timedelta(hours=4)

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}
📅 {dt_local.strftime("%d/%m")}
⏰ {dt_local.strftime("%H:%M")}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

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
            return "❌ Não foi possível analisar o jogo"

        return "🧠 MANUAL\n\n" + res

    except Exception as e:
        print("❌ ERRO MANUAL:", e)
        return "⚠️ Erro"

# ================= AUTO =================
def auto():
    print("🤖 AUTO LIGADO")

    while True:
        try:
            agora = datetime.utcnow()

            data = req("https://v3.football.api-sports.io/fixtures", {
                "date": agora.strftime("%Y-%m-%d")
            })

            if not data:
                continue

            for j in data.get("response", []):
                fid = j["fixture"]["id"]

                if fid in enviados_ids:
                    continue

                dt = datetime.strptime(j["fixture"]["date"][:19], "%Y-%m-%dT%H:%M:%S")

                diff = (dt - agora).total_seconds() / 60

                if JANELA_MIN < diff < JANELA_MAX:
                    res = analisar(
                        j["teams"]["home"]["name"],
                        j["teams"]["away"]["name"]
                    )

                    if res:
                        enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + res)
                        enviados_ids.add(fid)

        except Exception as e:
            print("❌ ERRO AUTO:", e)

        time.sleep(AUTO_INTERVALO)

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ONLINE PRO")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id or 0}
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" in u:
                    texto = u["message"].get("text", "")
                    enviar(manual(texto))

        except Exception as e:
            print("❌ ERRO MAIN:", e)

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
