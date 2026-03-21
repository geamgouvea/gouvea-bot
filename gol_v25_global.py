import requests
import time
from datetime import datetime, timedelta

# 🔐 CONFIG
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
enviados = set()  # 🔥 evitar repetição automática

# 🔄 REQUEST
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r
    except:
        return None
    return None

# 🔍 BUSCAR TIME
def buscar_time(nome):
    res = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
    if not res:
        return None
    data = res.json()
    if data["response"]:
        return data["response"][0]["team"]["id"]
    return None

# 📊 HISTÓRICO
def pegar_jogos(team_id):
    res = safe_request(f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10")
    if not res:
        return []
    return res.json().get("response", [])

# 🧠 ANÁLISE COMPLETA
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

    gols = []
    btts = 0
    casa = 0
    fora = 0

    for j in jogos:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            if g1 is None or g2 is None:
                continue

            gols.append(g1 + g2)

            if g1 > 0 and g2 > 0:
                btts += 1

            if g1 > g2:
                casa += 1
            elif g2 > g1:
                fora += 1

        except:
            continue

    if len(gols) < 6:
        return None

    total = len(gols)

    stats = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 3.5": sum(g <= 3 for g in gols) / total,
        "Ambas marcam": btts / total,
        "Casa vence": casa / total,
        "Fora vence": fora / total
    }

    melhor = max(stats, key=stats.get)
    prob = int(stats[melhor] * 100)

    if prob < 65:  # 🔥 filtro ajustado
        return None

    return melhor, prob

# ⚽ BUSCAR JOGOS (PRÓXIMAS 12H)
def buscar_jogos():
    jogos = []
    hoje = datetime.utcnow().strftime("%Y-%m-%d")

    res = safe_request(f"https://v3.football.api-sports.io/fixtures?date={hoje}")
    if not res:
        return []

    data = res.json()
    agora = datetime.now()

    for j in data.get("response", []):
        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00")).astimezone()
        diff = (dt - agora).total_seconds()

        if diff < 0 or diff > 43200:  # 12h
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        jogos.append((home, away, dt.strftime("%H:%M")))

    return jogos

# 🔥 GERAR MÚLTIPLA
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []
    usados = set()

    for home, away, hora in jogos:
        if home in usados or away in usados:
            continue

        resultado = analisar(home, away)
        if resultado:
            melhor, prob = resultado
            picks.append((home, away, melhor, prob, hora))

            usados.add(home)
            usados.add(away)

    picks.sort(key=lambda x: x[3], reverse=True)

    if not picks:
        return "⚠️ Poucos jogos fortes agora."

    picks = picks[:qtd]

    msg = "🔥 GOUVEA BET – MÚLTIPLA\n\n"

    for i, (h, a, e, p, hr) in enumerate(picks, 1):
        msg += f"{i}️⃣ {h} x {a}\n⏰ {hr}\n🎯 {e} ({p}%)\n\n"

    return msg

# 🔍 PESQUISA MANUAL
def analisar_jogo(texto):
    try:
        home, away = texto.split(" x ")
    except:
        return "❌ Use: Time x Time"

    resultado = analisar(home, away)
    if not resultado:
        return "⚠️ Jogo sem valor agora."

    melhor, prob = resultado

    return f"""
🔍 ANÁLISE

⚽ {home} x {away}
🎯 {melhor}
📊 Probabilidade: {prob}%
"""

# 📲 ENVIAR
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

# 🤖 BOT
def main():
    global last_update_id

    print("BOT ONLINE 🚀")

    ultimo_envio = datetime.now() - timedelta(minutes=30)

    while True:
        try:
            # 🔁 LOOP AUTOMÁTICO (30 MIN)
            if (datetime.now() - ultimo_envio).total_seconds() > 1800:
                msg = gerar_multipla(3)

                if msg not in enviados:
                    enviar(msg)
                    enviados.add(msg)

                ultimo_envio = datetime.now()

            # 📩 COMANDOS TELEGRAM
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 10, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()

                if texto == "/start":
                    enviar("🤖 Gouvea Bet Online!\nUse:\nmultipla 3\nou\nTime x Time")

                elif texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(gerar_multipla(qtd))

                elif " x " in texto:
                    enviar(analisar_jogo(texto))

        except Exception as e:
            print("ERRO:", e)

        time.sleep(5)

if __name__ == "__main__":
    main()
