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
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    nome = nome.encode('ASCII', 'ignore').decode('ASCII')
    return nome

# ================= REQUEST =================
def request(url, params=None):
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

    mapa = {
        "inter": "Inter",
        "inter milao": "Inter",
        "internazionale": "Inter",
        "man united": "Manchester United",
        "psg": "Paris Saint Germain"
    }

    nome = mapa.get(nome, nome)

    data = request("https://v3.football.api-sports.io/teams", {"search": nome})

    if data and data.get("response"):
        return data["response"][0]["team"]["id"]
    return None

# ================= PEGAR JOGOS =================
def pegar_jogos(team_id):
    data = request("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    if data:
        return data.get("response", [])
    return []

# ================= PEGAR ODDS =================
def pegar_odds(fixture_id):
    data = request("https://v3.football.api-sports.io/odds", {
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
                        odds[v["value"]] = float(v["odd"])

                if bet["name"] == "Both Teams Score":
                    for v in bet["values"]:
                        odds[v["value"]] = float(v["odd"])

    except:
        pass

    return odds

# ================= CALCULO =================
def calcular_prob(jogos):
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

    if not gols:
        return None

    total = len(gols)

    return {
        "over15": sum(g >= 2 for g in gols) / total,
        "over25": sum(g >= 3 for g in gols) / total,
        "under25": sum(g <= 2 for g in gols) / total,
        "btts": btts / total
    }

# ================= ANALISE =================
def analisar_jogo(fixture):
    try:
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        liga = fixture["league"]["name"]
        data_jogo = fixture["fixture"]["date"]
        fixture_id = fixture["fixture"]["id"]

        dt = datetime.fromisoformat(data_jogo.replace("Z","+00:00"))
        hora = dt.strftime("%H:%M")

        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return None

        jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

        if len(jogos) < 6:
            return None

        prob = calcular_prob(jogos)
        if not prob:
            return None

        odds = pegar_odds(fixture_id)

        oportunidades = []

        mercados = {
            "Over 1.5": prob["over15"],
            "Over 2.5": prob["over25"],
            "Under 2.5": prob["under25"],
            "BTTS Yes": prob["btts"]
        }

        for mercado, p in mercados.items():
            odd = odds.get(mercado)
            if odd and p > 0.60 and odd > (1 / p):
                oportunidades.append((mercado, p))

        if not oportunidades:
            return None

        melhor = max(oportunidades, key=lambda x: x[1])

        prob_final = int(melhor[1] * 100)

        return {
            "home": home,
            "away": away,
            "liga": liga,
            "hora": hora,
            "entrada": melhor[0],
            "prob": prob_final
        }

    except:
        return None

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = request("https://v3.football.api-sports.io/fixtures", {"next": 50})
    if not data:
        return []

    jogos = []
    agora = datetime.utcnow()

    for j in data.get("response", []):
        try:
            dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
            diff = (dt - agora).total_seconds()

            if 0 < diff < 43200:  # 12h
                jogos.append(j)
        except:
            continue

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

# ================= AUTO =================
def auto():
    jogos = buscar_jogos()

    sinais = []

    for j in jogos:
        resultado = analisar_jogo(j)

        if resultado:
            key = f"{resultado['home']}x{resultado['away']}"

            if key not in jogos_enviados:
                jogos_enviados.add(key)
                sinais.append(resultado)

    sinais = sorted(sinais, key=lambda x: x["prob"], reverse=True)

    for s in sinais[:5]:
        msg = f"""🔥 SINAL ELITE

⚽ {s['home']} x {s['away']}
🏆 {s['liga']}
⏰ {s['hora']}

🎯 {s['entrada']}
📊 {s['prob']}%
"""
        enviar(msg)

# ================= MANUAL =================
def manual(texto):
    try:
        home, away = texto.split("x")
        home = home.strip()
        away = away.strip()

        fake_fixture = {
            "teams": {
                "home": {"name": home},
                "away": {"name": away}
            },
            "league": {"name": "Manual"},
            "fixture": {"id": 0, "date": datetime.utcnow().isoformat()}
        }

        r = analisar_jogo(fake_fixture)

        if not r:
            return "❌ Sem valor"

        return f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 {r['entrada']}
📊 {r['prob']}%
"""

    except:
        return "❌ Erro"

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ELITE ATIVO 🔥")

    ultimo_auto = datetime.utcnow()

    while True:
        try:
            # AUTO a cada 20 minutos
            if (datetime.utcnow() - ultimo_auto).seconds > 1200:
                auto()
                ultimo_auto = datetime.utcnow()

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

                if "x" in texto:
                    enviar(manual(texto))

                elif "multipla" in texto:
                    auto()

        except:
            pass

        time.sleep(5)

if __name__ == "__main__":
    main()
