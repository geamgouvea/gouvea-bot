import requests
import time
import random
from datetime import datetime, timedelta

# 🔐 CONFIG
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
jogos_enviados = set()
ultimo_envio = 0

# 🔥 REQUEST
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r
    except:
        return None
    return None

# 🌍 FILTRO DE LIGAS
def liga_valida(pais):
    pais = pais.lower()
    validas = [
        "brazil","argentina","england","spain","italy","germany",
        "portugal","netherlands","belgium","mexico",
        "usa","japan","korea","china","australia"
    ]
    return any(p in pais for p in validas)

# 🔍 TIME
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

# 🧠 ANÁLISE INTELIGENTE
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

    gols = []
    btts = 0
    home_win = 0
    away_win = 0

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
                home_win += 1
            elif g2 > g1:
                away_win += 1
        except:
            continue

    if len(gols) < 6:
        return None

    total = len(gols)

    stats = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Ambas marcam": btts / total,
        "Under 3.5": sum(g <= 3 for g in gols) / total,
        "Casa vence": home_win / total,
        "Fora vence": away_win / total,
        "Casa ou Fora": (home_win + away_win) / total
    }

    candidatos = []

    for mercado, prob in stats.items():
        p = int(prob * 100)

        if mercado == "Over 1.5" and p >= 80:
            candidatos.append((mercado, p))
        elif mercado == "Over 2.5" and p >= 75:
            candidatos.append((mercado, p))
        elif mercado == "Ambas marcam" and p >= 70:
            candidatos.append((mercado, p))
        elif mercado == "Under 3.5" and p >= 75:
            candidatos.append((mercado, p))
        elif mercado in ["Casa vence", "Fora vence"] and p >= 65:
            candidatos.append((mercado, p))
        elif mercado == "Casa ou Fora" and p >= 80:
            candidatos.append((mercado, p))

    if not candidatos:
        return None

    candidatos.sort(key=lambda x: x[1], reverse=True)
    top = candidatos[:3]

    mercado, prob = random.choice(top)

    forca = 10 if prob >= 85 else 9 if prob >= 80 else 8

    return mercado, prob, forca

# ⚽ BUSCAR JOGOS (12H)
def buscar_jogos():
    jogos = []
    hoje = datetime.utcnow().strftime("%Y-%m-%d")

    res = safe_request(f"https://v3.football.api-sports.io/fixtures?date={hoje}")
    if not res:
        return []

    data = res.json()
    agora = datetime.now()

    for j in data.get("response", []):
        try:
            if j["fixture"]["status"]["short"] != "NS":
                continue

            dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
            dt = dt.astimezone()

            diff = (dt - agora).total_seconds()

            if diff < 0 or diff > 43200:  # 12h
                continue

            if not liga_valida(j["league"]["country"]):
                continue

            home = j["teams"]["home"]["name"]
            away = j["teams"]["away"]["name"]

            jogos.append((home, away, dt.strftime("%H:%M")))
        except:
            continue

    return jogos

# 💰 MÚLTIPLA
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for home, away, hora in jogos:
        chave = f"{home}-{away}"

        if chave in jogos_enviados:
            continue

        res = analisar(home, away)
        if res:
            mercado, prob, _ = res
            picks.append((home, away, mercado, prob, hora))

    picks.sort(key=lambda x: x[3], reverse=True)
    picks = picks[:qtd]

    if not picks:
        return "❌ Nenhuma múltipla forte encontrada agora"

    msg = "🔥 GOUVEA BET – MÚLTIPLA PRO\n\n"

    for i, (h, a, m, p, hr) in enumerate(picks, 1):
        msg += f"{i}️⃣ {h} x {a}\n⏰ {hr}\n🎯 {m} ({p}%)\n\n"
        jogos_enviados.add(f"{h}-{a}")

    return msg

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

# 🤖 LOOP AUTOMÁTICO
def loop_automatico():
    global ultimo_envio

    agora = time.time()

    if agora - ultimo_envio < 1800:  # 30 min
        return

    jogos = buscar_jogos()

    for home, away, hora in jogos:
        chave = f"{home}-{away}"

        if chave in jogos_enviados:
            continue

        res = analisar(home, away)
        if res:
            mercado, prob, forca = res

            msg = f"""🔥 SINAL AUTOMÁTICO

⚽ {home} x {away}
⏰ {hora}

🎯 {mercado}
📊 {prob}%
🔥 Força: {forca}/10
"""

            enviar(msg)
            jogos_enviados.add(chave)
            ultimo_envio = agora
            break

# 🤖 BOT
def main():
    global last_update_id

    enviar("🤖 Gouvea Bet Online!\nUse:\nmultipla 3\nou Time x Time")

    while True:
        try:
            # 🔥 AUTOMÁTICO
            loop_automatico()

            # 🔥 TELEGRAM
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 30, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()

                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(gerar_multipla(qtd))

                elif " x " in texto:
                    home, away = texto.split(" x ")
                    res = analisar(home, away)

                    if res:
                        mercado, prob, forca = res
                        enviar(f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 {mercado}
📊 {prob}%
🔥 Força: {forca}/10
""")
                    else:
                        enviar("⚠️ Jogo sem valor agora")

        except Exception as e:
            print("ERRO:", e)

        time.sleep(5)

if __name__ == "__main__":
    main()
