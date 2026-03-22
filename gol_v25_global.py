import requests
import time
from datetime import datetime
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

MODO_TESTE = True  # TRUE = roda a cada 1 min / FALSE = 30 min

last_update_id = None
jogos_enviados = set()

INTERVALO = 60 if MODO_TESTE else 1800  # 1 min teste / 30 min produção

# ================= NORMALIZAR =================
def normalizar_nome(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    nome = nome.encode('ASCII', 'ignore').decode('ASCII')

    remover = ["fc", "club", "clube", "de", "da", "do"]
    for r in remover:
        nome = nome.replace(f" {r} ", " ")

    return nome.strip()

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

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome_original = nome
    nome = normalizar_nome(nome)

    mapa = {
        "real madrid": ["real madrid", "rm"],
        "atletico madrid": ["atletico madrid", "atl madrid"],
        "athletic bilbao": ["athletic bilbao", "bilbao"],
        "real betis": ["real betis", "betis"],
        "inter milan": ["inter", "inter milan", "inter de milao"],
        "ac milan": ["milan", "ac milan"],
        "psg": ["psg", "paris saint germain"],
        "manchester united": ["manchester united", "man united"],
        "manchester city": ["manchester city", "man city"],
        "bayern munich": ["bayern"],
        "borussia dortmund": ["dortmund"],
        "flamengo": ["flamengo"],
        "corinthians": ["corinthians"],
        "palmeiras": ["palmeiras"],
        "santos": ["santos"],
        "cruzeiro": ["cruzeiro"],
        "gremio": ["gremio"],
        "internacional": ["internacional"]
    }

    for oficial, aliases in mapa.items():
        for alias in aliases:
            if alias in nome:
                nome = oficial

    data = safe_request(
        "https://v3.football.api-sports.io/teams",
        {"search": nome}
    )

    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    data = safe_request(
        "https://v3.football.api-sports.io/teams",
        {"search": nome_original}
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
    return data.get("response", []) if data else []

# ================= LIGA =================
def liga_valida(nome):
    nome = nome.lower()

    boas = ["premier", "la liga", "serie a", "bundesliga", "ligue 1", "brasileiro"]
    ruins = ["friendly", "amistoso", "youth", "u17", "u20", "u23", "women"]

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
                if bet["name"] == "Goals Over/Under":
                    for v in bet["values"]:
                        if "Over 2.5" in v["value"]:
                            odds["Over 2.5"] = float(v["odd"])
                        if "Over 1.5" in v["value"]:
                            odds["Over 1.5"] = float(v["odd"])

                if bet["name"] == "Both Teams Score":
                    for v in bet["values"]:
                        odds["BTTS"] = float(v["odd"])
    except:
        pass

    return odds

# ================= VALOR =================
def tem_valor(prob, odd):
    return prob > 0 and odd > (1 / prob)

# ================= ANALISAR =================
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
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            if g1 is None or g2 is None:
                continue

            gols.append(g1 + g2)

            if g1 > 0 and g2 > 0:
                btts += 1

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

        if "BTTS" in odds and tem_valor(prob_btts, odds["BTTS"]):
            opcoes.append(("Ambas marcam", prob_btts))

        if "Over 1.5" in odds and tem_valor(prob_over15, odds["Over 1.5"]):
            opcoes.append(("Over 1.5", prob_over15))

        if not opcoes:
            return None

        melhor = max(opcoes, key=lambda x: x[1])

        prob = int(melhor[1] * 100)
        forca = 10 if prob >= 80 else 9 if prob >= 72 else 8 if prob >= 65 else 7

        return melhor[0], prob, forca, liga

    except:
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

# ================= ENVIO =================
def enviar(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

# ================= SINAIS AUTOMÁTICOS =================
def enviar_sinais_automaticos():
    global jogos_enviados

    print("🔄 Rodando análise automática...")

    jogos = buscar_jogos()
    sinais = []

    for j in jogos:
        fixture_id = j["fixture"]["id"]

        if fixture_id in jogos_enviados:
            continue

        resultado = analisar(j)

        if resultado:
            home = j["teams"]["home"]["name"]
            away = j["teams"]["away"]["name"]
            entrada, prob, forca, liga = resultado

            if prob >= 65:
                sinais.append((fixture_id, home, away, entrada, prob, forca, liga))

    sinais.sort(key=lambda x: x[4], reverse=True)
    sinais = sinais[:5]

    if not sinais:
        print("Sem sinais agora")
        return

    msg = "🔥 SINAIS AUTOMÁTICOS\n\n"

    for s in sinais:
        fixture_id, home, away, entrada, prob, forca, liga = s

        msg += f"""⚽ {home} x {away}
🏆 {liga}
🎯 {entrada}
📊 {prob}%
⭐ {forca}/10

"""

        jogos_enviados.add(fixture_id)

    enviar(msg)

# ================= MANUAL =================
def analise_manual(texto):
    if "x" not in texto:
        return "⚠️ Use: Time A x Time B"

    home, away = texto.split("x")

    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return f"""🔍 ANÁLISE MANUAL

⚽ {home.strip()} x {away.strip()}

🎯 Over 1.5
📊 55%"""

    jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

    gols = [j["goals"]["home"] + j["goals"]["away"]
            for j in jogos if j["goals"]["home"] and j["goals"]["away"]]

    if not gols:
        return "Sem dados"

    prob = int((sum(g >= 3 for g in gols) / len(gols)) * 100)

    return f"""🔍 ANÁLISE MANUAL

⚽ {home.strip()} x {away.strip()}

🎯 Over 2.5
📊 {prob}%"""

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 Gouvea Bet PRO ONLINE")

    ultimo_envio = 0

    while True:
        try:
            agora = time.time()

            # AUTOMÁTICO
            if agora - ultimo_envio > INTERVALO:
                enviar_sinais_automaticos()
                ultimo_envio = agora

            # TELEGRAM
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "").lower()

                if texto.startswith("multipla"):
                    enviar("Use automático agora 🔥")

                elif "x" in texto:
                    enviar(analise_manual(texto))

        except Exception as e:
            print("ERRO:", e)

        time.sleep(5)

if __name__ == "__main__":
    main()
