import requests
import time
from datetime import datetime, timedelta
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
    except:
        return None
    return None

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar_nome(nome)

    mapa = {
        "real madrid": "Real Madrid",
        "barcelona": "Barcelona",
        "inter": "Inter",
        "milan": "AC Milan",
        "psg": "Paris Saint Germain",
        "bayern": "Bayern Munich",
        "flamengo": "Flamengo",
        "corinthians": "Corinthians",
        "palmeiras": "Palmeiras",
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

    ruins = ["friendly", "amistoso", "youth", "u17", "u20", "u23", "women"]
    if any(r in nome for r in ruins):
        return False

    return True

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

# ================= VALOR =================
def tem_valor(prob, odd):
    if prob == 0:
        return False
    margem = 0.90
    return odd > ((1 / prob) * margem)

# ================= ANALISE =================
def analisar(fixture):
    try:
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        liga = fixture["league"]["name"]
        fixture_id = fixture["fixture"]["id"]
        horario = fixture["fixture"]["date"]

        if not liga_valida(liga):
            return None

        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return None

        jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

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
        if total < 6:
            return None

        prob_over25 = sum(g >= 3 for g in gols) / total
        prob_over15 = min(0.90, prob_over25 + 0.25)
        prob_btts = btts / total
        prob_under25 = 1 - prob_over25

        odds = pegar_odds(fixture_id)

        opcoes = []

        if "Over 2.5" in odds and prob_over25 >= 0.58 and tem_valor(prob_over25, odds["Over 2.5"]):
            opcoes.append(("Over 2.5", prob_over25))

        if "Over 1.5" in odds and prob_over15 >= 0.70 and tem_valor(prob_over15, odds["Over 1.5"]):
            opcoes.append(("Over 1.5", prob_over15))

        if "BTTS" in odds and prob_btts >= 0.55 and tem_valor(prob_btts, odds["BTTS"]):
            opcoes.append(("Ambas marcam", prob_btts))

        if "Under 2.5" in odds and prob_under25 >= 0.60 and tem_valor(prob_under25, odds["Under 2.5"]):
            opcoes.append(("Under 2.5", prob_under25))

        if not opcoes:
            return None

        entrada, prob = max(opcoes, key=lambda x: x[1])

        prob = int(prob * 100)

        hora = datetime.fromisoformat(horario.replace("Z","+00:00"))
        hora = hora.strftime("%H:%M")

        return home, away, entrada, prob, liga, hora

    except:
        return None

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = safe_request("https://v3.football.api-sports.io/fixtures", {"next": 50})
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

    picks.sort(key=lambda x: x[3], reverse=True)

    if len(picks) < qtd:
        return "⚠️ Poucas oportunidades agora"

    msg = "🔥 MÚLTIPLA ELITE\n\n"

    for i, (h, a, e, p, l, hr) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🏆 {l}\n⏰ {hr}\n🎯 {e} ({p}%)\n\n"

    return msg

# ================= AUTOMÁTICO =================
def auto_sinais():
    jogos = buscar_jogos()

    enviados = 0

    for j in jogos:
        if enviados >= 5:
            break

        fid = j["fixture"]["id"]

        if fid in jogos_enviados:
            continue

        resultado = analisar(j)

        if resultado:
            h, a, e, p, l, hr = resultado

            msg = f"""🔥 SINAL AUTOMÁTICO

⚽ {h} x {a}
🏆 {l}
⏰ {hr}

🎯 {e}
📊 {p}%"""

            enviar(msg)
            jogos_enviados.add(fid)
            enviados += 1

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ELITE ATIVO 🔥")

    ultimo_auto = time.time()

    while True:
        try:
            # comandos telegram
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id},
                timeout=10
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "").lower().strip()

                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(gerar_multipla(qtd))

                elif "x" in texto:
                    res = analisar_manual(texto)
                    enviar(res)

            # automático a cada 20 min
            if time.time() - ultimo_auto > 1200:
                auto_sinais()
                ultimo_auto = time.time()

        except:
            pass

        time.sleep(5)

if __name__ == "__main__":
    main()
