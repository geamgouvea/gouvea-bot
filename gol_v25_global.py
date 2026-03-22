import requests
import time
from datetime import datetime

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
bot_iniciado = False
jogos_enviados = set()
ultimo_loop = 0

# ================= REQUEST =================
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# ================= LIGA INTELIGENTE =================
def liga_valida(nome_liga):
    nome = nome_liga.lower()

    palavras_boas = [
        "premier", "la liga", "serie a", "bundesliga", "ligue 1",
        "portugal", "eredivisie", "scotland", "scottish",
        "brasileiro", "brazil", "argentina",
        "mls", "mexico",
        "champions league", "europa league",
        "libertadores", "sudamericana"
    ]

    palavras_ruins = [
        "friendly", "amistoso", "youth",
        "u17", "u20", "u23",
        "reserve", "women"
    ]

    if any(p in nome for p in palavras_ruins):
        return False

    return any(p in nome for p in palavras_boas)

# ================= TIMES =================
def buscar_time(nome):
    data = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]
    return None

# ================= HISTÓRICO =================
def pegar_jogos(team_id):
    data = safe_request("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    if data:
        return data.get("response", [])
    return []

# ================= ODDS =================
def pegar_odds(fixture_id):
    data = safe_request("https://v3.football.api-sports.io/odds", {
        "fixture": fixture_id
    })

    odds = {}

    if not data or not data.get("response"):
        return odds

    try:
        for book in data["response"][0]["bookmakers"]:
            for bet in book["bets"]:
                nome = bet["name"]

                if nome == "Match Winner":
                    for v in bet["values"]:
                        odds[v["value"]] = float(v["odd"])

                if nome == "Both Teams Score":
                    for v in bet["values"]:
                        odds["BTTS_" + v["value"]] = float(v["odd"])

                if nome == "Goals Over/Under":
                    for v in bet["values"]:
                        if "Over 2.5" in v["value"]:
                            odds["Over 2.5"] = float(v["odd"])
                        if "Over 1.5" in v["value"]:
                            odds["Over 1.5"] = float(v["odd"])
    except:
        pass

    return odds

# ================= VALOR =================
def tem_valor(prob, odd):
    odd_justa = 1 / prob
    return odd > odd_justa

# ================= ANÁLISE =================
def analisar(fixture):
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]
    liga = fixture["league"]["name"]
    fixture_id = fixture["fixture"]["id"]

    if not liga_valida(liga):
        return None

    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    jogos_home = pegar_jogos(home_id)
    jogos_away = pegar_jogos(away_id)

    peso = 1.0
    soma_peso = 0

    over25 = 0
    btts = 0
    home_win = 0
    away_win = 0

    for j in jogos_home[-10:]:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]
            if g1 is None or g2 is None:
                continue

            soma_peso += peso

            if g1 > g2:
                home_win += peso

            if g1 + g2 >= 3:
                over25 += peso

            if g1 > 0 and g2 > 0:
                btts += peso

            peso += 0.2
        except:
            continue

    peso = 1.0

    for j in jogos_away[-10:]:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]
            if g1 is None or g2 is None:
                continue

            soma_peso += peso

            if g2 > g1:
                away_win += peso

            if g1 + g2 >= 3:
                over25 += peso

            if g1 > 0 and g2 > 0:
                btts += peso

            peso += 0.2
        except:
            continue

    if soma_peso == 0:
        return None

    prob_home = home_win / soma_peso
    prob_away = away_win / soma_peso
    prob_over25 = over25 / soma_peso
    prob_btts = btts / soma_peso

    odds = pegar_odds(fixture_id)

    opcoes = []

    if "Home" in odds and tem_valor(prob_home, odds["Home"]):
        opcoes.append(("Casa vence", prob_home))

    if "Away" in odds and tem_valor(prob_away, odds["Away"]):
        opcoes.append(("Fora vence", prob_away))

    if "Over 2.5" in odds and tem_valor(prob_over25, odds["Over 2.5"]):
        opcoes.append(("Over 2.5", prob_over25))

    if "BTTS_Yes" in odds and tem_valor(prob_btts, odds["BTTS_Yes"]):
        opcoes.append(("Ambas marcam", prob_btts))

    # 🔥 OVER 1.5 (SEGURANÇA)
    prob_over15 = min(0.90, prob_over25 + 0.15)

    if "Over 1.5" in odds and tem_valor(prob_over15, odds["Over 1.5"]):
        opcoes.append(("Over 1.5", prob_over15))

    if not opcoes:
        return None

    melhor = max(opcoes, key=lambda x: x[1])

    prob = int(melhor[1] * 100)
    forca = 10 if prob >= 85 else 9 if prob >= 78 else 8

    return melhor[0], prob, forca, liga

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = safe_request("https://v3.football.api-sports.io/fixtures", {"next": 30})
    if not data:
        return []

    jogos = []
    agora = datetime.utcnow()

    for j in data.get("response", []):
        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
        diff = (dt - agora).total_seconds()

        if diff < 0 or diff > 43200:
            continue

        jogos.append(j)

    return jogos

# ================= ENVIAR =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

# ================= AUTOMÁTICO =================
def enviar_sinais():
    jogos = buscar_jogos()
    enviados_agora = 0

    for j in jogos:
        fixture_id = j["fixture"]["id"]

        if fixture_id in jogos_enviados:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]
        hora = j["fixture"]["date"][11:16]

        resultado = analisar(j)

        if resultado:
            entrada, prob, forca, liga = resultado

            msg = f"""🔥 SINAL PRO

🏆 Liga: {liga}

⚽ {home} x {away}
⏰ {hora}

🎯 {entrada}
📊 {prob}%
🔥 Força: {forca}/10
💰 Entrada com VALOR
"""

            enviar(msg)
            jogos_enviados.add(fixture_id)
            enviados_agora += 1

        if enviados_agora >= 3:
            break

# ================= MÚLTIPLA =================
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for j in jogos:
        resultado = analisar(j)
        if resultado:
            home = j["teams"]["home"]["name"]
            away = j["teams"]["away"]["name"]
            entrada, prob, _, liga = resultado

            picks.append((home, away, entrada, prob, liga))

    picks.sort(key=lambda x: x[3], reverse=True)

    if len(picks) < 2:
        return "❌ Sem múltipla forte"

    msg = "🔥 MÚLTIPLA PRO\n\n"

    for i, (h, a, e, p, l) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🏆 {l}\n🎯 {e} ({p}%)\n\n"

    return msg

# ================= MAIN =================
def main():
    global last_update_id, bot_iniciado, ultimo_loop

    if not bot_iniciado:
        enviar("🤖 Gouvea Bet PRO Online!")
        bot_iniciado = True

    while True:
        try:
            agora = time.time()

            if agora - ultimo_loop > 1200:
                enviar_sinais()
                ultimo_loop = agora

            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 10, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "").lower()

                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(gerar_multipla(qtd))

        except:
            pass

        time.sleep(5)

if __name__ == "__main__":
    main()
