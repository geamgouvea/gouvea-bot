import requests
import time
from datetime import datetime
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
jogos_enviados = set()

# ================= NORMALIZAR =================
def normalizar_nome(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    nome = nome.encode('ASCII', 'ignore').decode('ASCII')
    return nome

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

# ================= BUSCAR TIME INTELIGENTE =================
def buscar_time(nome):
    nome = normalizar_nome(nome)

    mapa = {
        "real madrid": "Real Madrid",
        "atletico madrid": "Atletico Madrid",
        "barcelona": "Barcelona",
        "inter": "Inter",
        "inter milan": "Inter",
        "milan": "AC Milan",
        "juventus": "Juventus",
        "psg": "Paris Saint Germain",
        "manchester united": "Manchester United",
        "manchester city": "Manchester City",
        "liverpool": "Liverpool",
        "chelsea": "Chelsea",
        "arsenal": "Arsenal",
        "bayern": "Bayern Munich",
        "dortmund": "Borussia Dortmund",
        "flamengo": "Flamengo",
        "corinthians": "Corinthians",
        "palmeiras": "Palmeiras",
        "santos": "Santos",
        "cruzeiro": "Cruzeiro",
        "gremio": "Gremio",
        "internacional": "Internacional"
    }

    nome_busca = mapa.get(nome, nome)

    data = safe_request(
        "https://v3.football.api-sports.io/teams",
        {"search": nome_busca}
    )

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

# ================= LIGA =================
def liga_valida(nome):
    nome = nome.lower()

    boas = [
        "premier", "la liga", "serie a", "bundesliga",
        "ligue 1", "portugal", "eredivisie",
        "scotland", "brasileiro", "argentina"
    ]

    ruins = [
        "friendly", "amistoso", "youth",
        "u17", "u20", "u23",
        "reserve", "women"
    ]

    if any(r in nome for r in ruins):
        return False

    return any(b in nome for b in boas)

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

                if nome == "Goals Over/Under":
                    for v in bet["values"]:
                        if "Over 2.5" in v["value"]:
                            odds["Over 2.5"] = float(v["odd"])
                        if "Over 1.5" in v["value"]:
                            odds["Over 1.5"] = float(v["odd"])

                if nome == "Both Teams Score":
                    for v in bet["values"]:
                        odds["BTTS_Yes"] = float(v["odd"])
    except Exception as e:
        print("Erro odds:", e)

    return odds

# ================= VALOR =================
def tem_valor(prob, odd):
    if prob == 0:
        return False
    return odd > (1 / prob)

# ================= ANALISE AUTO =================
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

                gols.append(g1 + g2)

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

# ================= ANALISE MANUAL =================
def analise_manual(texto):
    if "x" not in texto:
        return "⚠️ Use: Time A x Time B"

    try:
        home, away = texto.split("x")
        home = home.strip()
        away = away.strip()
    except:
        return "❌ Erro ao ler times"

    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return "❌ Times não encontrados"

    jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

    if len(jogos) < 6:
        return "⚠️ Poucos dados"

    gols = []
    btts = 0

    for j in jogos:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            if g1 is None or g2 is None:
                continue

            gols.append(g1 + g2)

            if g1 > 0 and g2 > 0:
                btts += 1
        except:
            continue

    total = len(gols)
    if total == 0:
        return "❌ Sem dados"

    prob_over25 = sum(g >= 3 for g in gols) / total
    prob_btts = btts / total
    prob_over15 = min(0.90, prob_over25 + 0.20)

    if prob_over25 >= 0.65:
        entrada = "Over 2.5"
        prob = prob_over25
    elif prob_btts >= 0.60:
        entrada = "Ambas marcam"
        prob = prob_btts
    else:
        entrada = "Over 1.5"
        prob = prob_over15

    prob = int(prob * 100)

    return f"""🔍 ANÁLISE MANUAL

⚽ {home} x {away}

🎯 {entrada}
📊 {prob}%"""

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

# ================= MULTIPLA =================
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for j in jogos:
        resultado = analisar(j)
        if resultado:
            home = j["teams"]["home"]["name"]
            away = j["teams"]["away"]["name"]
            entrada, prob, _, liga = resultado

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

    enviar("🤖 Gouvea Bet PRO Inteligente Online!")

    while True:
        try:
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={
                    "timeout": 10,
                    "offset": last_update_id if last_update_id else None
                }
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

                elif "x" in texto:
                    enviar(analise_manual(texto))

                else:
                    enviar("⚠️ Use:\n- multipla 2\n- time a x time b")

        except Exception as e:
            print("ERRO:", e)

        time.sleep(5)

if __name__ == "__main__":
    main()
