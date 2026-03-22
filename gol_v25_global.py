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
        return None
    return None

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)

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

# ================= ODDS =================
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
def calcular(jogos):
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

    if len(gols) < 5:
        return None

    total = len(gols)

    return {
        "over15": sum(g >= 2 for g in gols) / total,
        "over25": sum(g >= 3 for g in gols) / total,
        "under25": sum(g <= 2 for g in gols) / total,
        "btts": btts / total
    }

# ================= VALOR =================
def tem_valor(prob, odd):
    if prob == 0:
        return False
    margem = 0.90
    return odd > ((1 / prob) * margem)

# ================= ANALISE AUTO =================
def analisar_auto(fixture):
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
        prob = calcular(jogos)

        if not prob:
            return None

        odds = pegar_odds(fixture_id)

        mercados = {
            "Over 1.5": prob["over15"],
            "Over 2.5": prob["over25"],
            "Under 2.5": prob["under25"],
            "BTTS": prob["btts"]
        }

        opcoes_valor = []
        opcoes_simples = []

        for mercado, p in mercados.items():
            odd = odds.get(mercado)

            opcoes_simples.append((mercado, p))

            if odd and p >= 0.55 and tem_valor(p, odd):
                opcoes_valor.append((mercado, p))

        if opcoes_valor:
            melhor = max(opcoes_valor, key=lambda x: x[1])
            tipo = "🔥 VALOR"
        else:
            melhor = max(opcoes_simples, key=lambda x: x[1])
            tipo = "⚠️ PROVÁVEL"

        prob_final = int(melhor[1] * 100)

        return {
            "home": home,
            "away": away,
            "liga": liga,
            "hora": hora,
            "entrada": melhor[0],
            "prob": prob_final,
            "tipo": tipo
        }

    except:
        return None

# ================= ANALISE MANUAL =================
def analisar_manual(texto):
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
    prob = calcular(jogos)

    if not prob:
        return f"⚠️ {home} x {away}\nPoucos dados"

    opcoes = [
        ("Over 2.5", prob["over25"]),
        ("Over 1.5", prob["over15"]),
        ("Ambas marcam", prob["btts"]),
        ("Under 2.5", prob["under25"])
    ]

    entrada, p = max(opcoes, key=lambda x: x[1])
    p = int(p * 100)

    return f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 Melhor entrada: {entrada}
📊 Probabilidade: {p}%"""

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = request("https://v3.football.api-sports.io/fixtures", {"next": 50})
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
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= MULTIPLA =================
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for j in jogos:
        r = analisar_auto(j)
        if r and r["prob"] >= 60:
            picks.append(r)

    picks.sort(key=lambda x: x["prob"], reverse=True)

    if len(picks) < 2:
        return "⚠️ Poucas oportunidades agora"

    msg = "🔥 MÚLTIPLA ELITE\n\n"

    for i, p in enumerate(picks[:qtd], 1):
        msg += f"""{i}️⃣ {p['home']} x {p['away']}
🏆 {p['liga']}
⏰ {p['hora']}
🎯 {p['entrada']}
📊 {p['prob']}% {p['tipo']}

"""

    return msg

# ================= AUTO =================
def auto():
    jogos = buscar_jogos()
    enviados = 0

    for j in jogos:
        if enviados >= 5:
            break

        fid = j["fixture"]["id"]

        if fid in jogos_enviados:
            continue

        r = analisar_auto(j)

        if r:
            msg = f"""🔥 SINAL AUTOMÁTICO

⚽ {r['home']} x {r['away']}
🏆 {r['liga']}
⏰ {r['hora']}

🎯 {r['entrada']}
📊 {r['prob']}% {r['tipo']}"""

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
                    enviar(analisar_manual(texto))

            if time.time() - ultimo_auto > 1200:
                auto()
                ultimo_auto = time.time()

        except:
            pass

        time.sleep(5)

if __name__ == "__main__":
    main()
