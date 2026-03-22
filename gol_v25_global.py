import requests
import time
import threading
from datetime import datetime
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd

HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    nome = nome.encode('ASCII', 'ignore').decode('ASCII')
    return nome

# ================= REQUEST =================
def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)

    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    nome_curto = nome.split()[0]
    data = req("https://v3.football.api-sports.io/teams", {"search": nome_curto})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    return None

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away):
    home = normalizar(home)
    away = normalizar(away)

    hoje = datetime.utcnow().strftime("%Y-%m-%d")
    lista = []

    data = req("https://v3.football.api-sports.io/fixtures", {"date": hoje})
    if data:
        lista += data.get("response", [])

    data = req("https://v3.football.api-sports.io/fixtures", {"next": 100})
    if data:
        lista += data.get("response", [])

    melhor = None
    score_max = 0

    for j in lista:
        h = normalizar(j["teams"]["home"]["name"])
        a = normalizar(j["teams"]["away"]["name"])

        score = 0
        if home in h or h in home:
            score += 1
        if away in a or a in away:
            score += 1

        if score > score_max:
            score_max = score
            melhor = j

    return melhor

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ODDS =================
def pegar_odds(fixture_id):
    data = req("https://v3.football.api-sports.io/odds", {"fixture": fixture_id})

    odds = {}

    if not data or not data.get("response"):
        return odds

    try:
        for book in data["response"][0]["bookmakers"]:
            for bet in book["bets"]:
                if bet["name"] == "Goals Over/Under":
                    for v in bet["values"]:
                        if "Over 2.5" in v["value"]:
                            odds["Over 2.5"] = float(v["odd"])
                        if "Under 2.5" in v["value"]:
                            odds["Under 2.5"] = float(v["odd"])
                        if "Over 1.5" in v["value"]:
                            odds["Over 1.5"] = float(v["odd"])

                if bet["name"] == "Both Teams Score":
                    for v in bet["values"]:
                        if v["value"] == "Yes":
                            odds["Ambas marcam"] = float(v["odd"])
    except:
        pass

    return odds

# ================= ANALISE =================
def analisar(home, away):
    fixture = buscar_fixture(home, away)

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
        return "❌ Sem dados"

    total = len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas marcam": btts / total
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    odds = {}
    liga = "N/A"
    hora = "--:--"
    home_nome = home
    away_nome = away

    if fixture:
        odds = pegar_odds(fixture["fixture"]["id"])
        liga = fixture["league"]["name"]
        dt = datetime.fromisoformat(fixture["fixture"]["date"].replace("Z","+00:00"))
        hora = dt.strftime("%H:%M")
        home_nome = fixture["teams"]["home"]["name"]
        away_nome = fixture["teams"]["away"]["name"]

    resposta = f"""🔍 ANÁLISE

⚽ {home_nome} x {away_nome}
🏆 {liga}
⏰ {hora}

🎯 Melhor entrada: {melhor}
📊 Probabilidade: {int(prob*100)}%"""

    # VALUE BET
    if melhor in odds:
        odd_real = odds[melhor]
        odd_justa = 1 / prob if prob > 0 else 0

        if odd_real > odd_justa:
            valor = (odd_real / odd_justa - 1) * 100

            resposta += f"""

🔥 VALUE BET
💰 Odd: {odd_real}
📉 Odd justa: {round(odd_justa,2)}
📈 Valor: {round(valor,1)}%"""
        else:
            resposta += "\n\n⚠️ Sem valor nas odds atuais"

    else:
        resposta += "\n\n⚠️ Odds não disponíveis"

    return resposta

# ================= AUTO =================
def auto():
    while True:
        data = req("https://v3.football.api-sports.io/fixtures", {"next": 30})

        if data:
            enviados = 0

            for j in data["response"]:
                h = j["teams"]["home"]["name"]
                a = j["teams"]["away"]["name"]

                res = analisar(h, a)

                if "VALUE BET" in res:
                    enviar("🔥 SINAL AUTOMÁTICO\n\n" + res)
                    enviados += 1

                if enviados >= 5:
                    break

        time.sleep(1200)

# ================= TELEGRAM =================
def enviar(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT VALUE BET ATIVO 💰")

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

                texto = u["message"].get("text", "").lower()

                if "x" in texto:
                    h, a = texto.split("x")
                    enviar(analisar(h.strip(), a.strip()))

                else:
                    enviar("⚠️ Use: time x time")

        except:
            pass

        time.sleep(5)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
