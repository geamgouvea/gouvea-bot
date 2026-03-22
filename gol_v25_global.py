import requests
import time
from datetime import datetime

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
jogos_enviados = set()
ultimo_loop = 0

# ================= REQUEST =================
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            print("Erro API:", r.status_code)
    except Exception as e:
        print("Erro request:", e)
    return None

# ================= LIGA =================
def liga_valida(nome_liga):
    nome = nome_liga.lower()

    boas = [
        "premier", "la liga", "serie a", "bundesliga", "ligue 1",
        "portugal", "eredivisie", "scotland", "brasileiro",
        "argentina", "mls", "mexico"
    ]

    ruins = [
        "friendly", "amistoso", "youth",
        "u17", "u20", "u23",
        "reserve", "women"
    ]

    if any(r in nome for r in ruins):
        return False

    return any(b in nome for b in boas)

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
    except Exception as e:
        print("Erro odds:", e)

    return odds

# ================= VALOR =================
def tem_valor(prob, odd):
    if prob == 0:
        return False
    return odd > (1 / prob)

# ================= ANÁLISE =================
def analisar(fixture):
    try:
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

        jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

        if len(jogos) < 6:
            return None

        gols = []
        btts = 0

        for j in jogos:
            try:
                g1 = j["goals"]["home"]
                g2 = j["goals"]["away"]
                if g1 is None or g2 is None:
                    continue

                total = g1 + g2
                gols.append(total)

                if g1 > 0 and g2 > 0:
                    btts += 1
            except:
                continue

        total = len(gols)

        if total == 0:
            return None

        prob_over25 = sum(g >= 3 for g in gols) / total
        prob_btts = btts / total

        prob_over15 = min(0.90, prob_over25 + 0.20)

        odds = pegar_odds(fixture_id)

        opcoes = []

        if "Over 2.5" in odds and tem_valor(prob_over25, odds["Over 2.5"]):
            opcoes.append(("Over 2.5", prob_over25))

        if "BTTS_Yes" in odds and tem_valor(prob_btts, odds["BTTS_Yes"]):
            opcoes.append(("Ambas marcam", prob_btts))

        if "Over 1.5" in odds and tem_valor(prob_over15, odds["Over 1.5"]):
            opcoes.append(("Over 1.5", prob_over15))

        if not opcoes:
            return None

        melhor = max(opcoes, key=lambda x: x[1])

        prob = int(melhor[1] * 100)
        forca = 10 if prob >= 80 else 9 if prob >= 72 else 8 if prob >= 65 else 7

        return melhor[0], prob, forca, liga

    except Exception as e:
        print("Erro análise:", e)
        return None

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = safe_request("https://v3.football.api-sports.io/fixtures", {"next": 30})
    if not data:
        return []

    jogos = []
    agora = datetime.utcnow()

    for j in data.get("response", []):
        try:
            if j["fixture"]["status"]["short"] != "NS":
                continue

            dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
            diff = (dt - agora).total_seconds()

            if 0 < diff < 43200:
                jogos.append(j)
        except:
            continue

    return jogos

# ================= ENVIAR =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print("Erro envio:", e)

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

            # 🔥 AGORA MAIS FLEXÍVEL
            if prob >= 65:
                picks.append((home, away, entrada, prob, liga))

    picks.sort(key=lambda x: x[3], reverse=True)

    if len(picks) < 2:
        return "⚠️ Poucas oportunidades boas agora"

    msg = "🔥 MÚLTIPLA AJUSTADA\n\n"

    for i, (h, a, e, p, l) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🏆 {l}\n🎯 {e} ({p}%)\n\n"

    return msg

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 Gouvea Bet PRO Ajustado Online!")

    while True:
        try:
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 10, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "").lower().strip()

                print("Recebido:", texto)

                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(gerar_multipla(qtd))

        except Exception as e:
            print("Erro:", e)

        time.sleep(5)

if __name__ == "__main__":
    main()
