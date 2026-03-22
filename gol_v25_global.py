import requests
import time
from datetime import datetime
import unicodedata
import random

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
    except:
        return None
    return None

# ================= BUSCAR TIME INTELIGENTE =================
def buscar_time(nome):
    nome_original = nome
    nome = normalizar_nome(nome)

    mapa = {
        "real madrid": "Real Madrid",
        "atletico madrid": "Atletico Madrid",
        "atletico de madrid": "Atletico Madrid",
        "barcelona": "Barcelona",
        "barcelona guayaquil": "Barcelona SC",
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
        "internacional": "Internacional",
        "chapecoense": "Chapecoense"
    }

    nome_busca = mapa.get(nome, nome_original)

    data = safe_request("https://v3.football.api-sports.io/teams", {"search": nome_busca})

    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    partes = nome_original.split()
    if len(partes) > 1:
        data = safe_request("https://v3.football.api-sports.io/teams", {"search": partes[0]})
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

                if nome == "Goals Over/Under":
                    for v in bet["values"]:
                        if "Over 2.5" in v["value"]:
                            odds["Over 2.5"] = float(v["odd"])
                        if "Over 1.5" in v["value"]:
                            odds["Over 1.5"] = float(v["odd"])
                        if "Under 2.5" in v["value"]:
                            odds["Under 2.5"] = float(v["odd"])

                if nome == "Both Teams Score":
                    for v in bet["values"]:
                        if v["value"] == "Yes":
                            odds["BTTS"] = float(v["odd"])
    except:
        pass

    return odds

# ================= ANALISE =================
def analisar(fixture):
    try:
        fixture_id = fixture["fixture"]["id"]

        if fixture_id in jogos_enviados:
            return None

        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]

        liga = fixture["league"]["name"]

        data_jogo = datetime.fromisoformat(fixture["fixture"]["date"].replace("Z","+00:00"))
        hora = data_jogo.astimezone().strftime("%H:%M")

        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return None

        jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

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

        prob_over25 = sum(g >= 3 for g in gols) / total
        prob_over15 = sum(g >= 2 for g in gols) / total
        prob_under25 = sum(g <= 2 for g in gols) / total
        prob_btts = btts / total

        odds = pegar_odds(fixture_id)

        opcoes = [
            ("Over 2.5", prob_over25),
            ("Over 1.5", prob_over15),
            ("Under 2.5", prob_under25),
            ("Ambas marcam", prob_btts)
        ]

        melhor = max(opcoes, key=lambda x: x[1])

        prob = int(melhor[1] * 100)

        if prob < 60:
            return None

        jogos_enviados.add(fixture_id)

        return home, away, melhor[0], prob, liga, hora

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
        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
        diff = (dt - agora).total_seconds()

        if 0 < diff < 43200:
            jogos.append(j)

    return jogos

# ================= ENVIAR =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= MULTIPLA =================
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for j in jogos:
        resultado = analisar(j)
        if resultado:
            picks.append(resultado)

    if len(picks) < 2:
        return "⚠️ Poucas oportunidades agora"

    picks.sort(key=lambda x: x[3], reverse=True)

    msg = "🔥 MÚLTIPLA ELITE\n\n"

    for i, (h, a, e, p, l, hora) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🏆 {l}\n⏰ {hora}\n🎯 {e} ({p}%)\n\n"

    return msg

# ================= MANUAL =================
def analise_manual(texto):
    if "x" not in texto:
        return "⚠️ Use: Time A x Time B"

    home, away = texto.split("x")
    home = home.strip()
    away = away.strip()

    jogos = buscar_jogos()

    for j in jogos:
        if home.lower() in j["teams"]["home"]["name"].lower() and away.lower() in j["teams"]["away"]["name"].lower():
            resultado = analisar(j)
            if resultado:
                h, a, e, p, l, hora = resultado
                return f"""🔍 ANÁLISE

⚽ {h} x {a}
🏆 {l}
⏰ {hora}

🎯 Melhor entrada: {e}
📊 Probabilidade: {p}%"""

    return "❌ Jogo não encontrado ou sem valor"

# ================= AUTO =================
def auto_envio():
    while True:
        jogos = buscar_jogos()
        enviados = 0

        for j in jogos:
            if enviados >= random.randint(3, 5):
                break

            resultado = analisar(j)

            if resultado:
                h, a, e, p, l, hora = resultado

                msg = f"""🔥 SINAL AUTOMÁTICO

⚽ {h} x {a}
🏆 {l}
⏰ {hora}

🎯 {e}
📊 {p}%"""

                enviar(msg)
                enviados += 1

        time.sleep(random.randint(1200, 1800))

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ELITE ATIVO 🔥")

    import threading
    threading.Thread(target=auto_envio, daemon=True).start()

    while True:
        try:
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
                    qtd = int(texto.split()[1]) if len(texto.split()) > 1 else 3
                    enviar(gerar_multipla(qtd))

                elif "x" in texto:
                    enviar(analise_manual(texto))

                else:
                    enviar("⚠️ Use:\n- multipla 3\n- time x time")

        except:
            pass

        time.sleep(5)

if __name__ == "__main__":
    main()
