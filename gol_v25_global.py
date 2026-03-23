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

enviados_ids = set()
last_update_id = None

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

# ================= ALIASES =================
ALIASES = {
    "bayern": "bayern munich",
    "bayer": "bayer leverkusen",
    "inter": "inter milan",
    "milan": "ac milan",
    "psg": "paris saint germain",
    "real": "real madrid",
    "city": "manchester city",
    "united": "manchester united"
}

def corrigir_nome(nome):
    n = normalizar(nome)
    for k in ALIASES:
        if k in n:
            return ALIASES[k]
    return nome

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

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = corrigir_nome(nome)
    nome_norm = normalizar(nome)

    data = req("https://v3.football.api-sports.io/teams", {"search": nome_norm})

    if not data or not data.get("response"):
        return None

    melhor = None
    score = 0

    for t in data["response"]:
        nome_api = normalizar(t["team"]["name"])
        s = similar(nome_norm, nome_api)

        if s > score:
            score = s
            melhor = t["team"]["id"]

    return melhor if score > 0.4 else None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away):
    home = corrigir_nome(home)
    away = corrigir_nome(away)

    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(15):  # sem limite curto
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_busca
        })

        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            s1 = (similar(home_n, h) + similar(away_n, a)) / 2
            s2 = (similar(home_n, a) + similar(away_n, h)) / 2

            score = max(s1, s2)

            if score > melhor_score:
                melhor_score = score
                melhor = j

    return melhor if melhor_score > 0.5 else None

# ================= ANALISE =================
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return "❌ Não foi possível analisar o jogo"

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
        return "❌ Sem dados suficientes"

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

    # classificação
    if prob >= 0.80:
        nivel = "🔥 FORTE"
    elif prob >= 0.70:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    fixture = buscar_fixture(home, away)

    liga = "Estimativa"
    data_txt = "--/--"
    hora = "--:--"

    if fixture:
        liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

        dt = datetime.fromisoformat(
            fixture["fixture"]["date"].replace("Z", "+00:00")
        ) - timedelta(hours=4)

        data_txt = dt.strftime("%d/%m")
        hora = dt.strftime("%H:%M")

    return f"""🔎 ANÁLISE

⚽ {home.title()} x {away.title()}
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

            for i in range(2):
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

                    # filtro leve (sem travar)
                    if any(x in h.lower() for x in ["u21","u20","women"]) or \
                       any(x in a.lower() for x in ["u21","u20","women"]):
                        continue

                    dt = datetime.fromisoformat(
                        j["fixture"]["date"].replace("Z", "+00:00")
                    ) - timedelta(hours=4)

                    agora = datetime.utcnow() - timedelta(hours=4)
                    diff = (dt - agora).total_seconds() / 60

                    if diff < 30 or diff > 180:
                        continue

                    res = analisar(h, a)

                    if "❌" in res:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + res)

                    enviados_ids.add(fid)
                    enviados += 1

                    if enviados >= 5:
                        break

                if enviados >= 5:
                    break

        except:
            pass

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        h, a = texto.split("x")
        return "🧠 MANUAL\n\n" + analisar(h.strip(), a.strip())
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
                params={"offset": last_update_id}
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
    threading.Thread(target=auto).start()
    main()
