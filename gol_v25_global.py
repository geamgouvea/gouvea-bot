import requests
import time
from datetime import datetime, timedelta

# 🔐 CONFIG
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
jogos_enviados = set()
ultimo_envio = 0

TEMPO_ENVIO = 1800  # 1800 = 30 min | 3600 = 1 hora

# 🔥 REQUEST
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r
    except:
        return None
    return None

# 🔎 BUSCAR TIME
def buscar_time(nome):
    res = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
    if res and res.json()["response"]:
        return res.json()["response"][0]["team"]["id"]
    return None

# 📊 HISTÓRICO
def pegar_jogos(team_id):
    res = safe_request(f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10")
    if res:
        return res.json().get("response", [])
    return []

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

            total = g1 + g2
            gols.append(total)

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

    # 🔥 FILTRO PESADO
    if prob < 75:
        return None

    return melhor, prob

# ⚽ BUSCAR JOGOS (PRÓXIMAS 12H)
def buscar_jogos():
    jogos = []
    agora = datetime.utcnow()
    limite = agora + timedelta(hours=12)

    res = safe_request("https://v3.football.api-sports.io/fixtures", {
        "date": agora.strftime("%Y-%m-%d")
    })

    if not res:
        return []

    for j in res.json().get("response", []):
        try:
            if j["fixture"]["status"]["short"] != "NS":
                continue

            dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))

            if not (agora <= dt <= limite):
                continue

            home = j["teams"]["home"]["name"]
            away = j["teams"]["away"]["name"]

            chave = f"{home}-{away}"

            if chave in jogos_enviados:
                continue

            jogos.append((home, away, dt.strftime("%H:%M")))

        except:
            continue

    return jogos

# 🔥 GERAR MULTIPLA AUTOMÁTICA
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for home, away, hora in jogos:
        analise = analisar(home, away)

        if analise:
            mercado, prob = analise
            picks.append((home, away, mercado, prob, hora))

    picks.sort(key=lambda x: x[3], reverse=True)

    if not picks:
        return None

    picks = picks[:qtd]

    msg = "🔥 GOUVEA BET – SINAL AUTOMÁTICO\n\n"

    for i, (h, a, m, p, hr) in enumerate(picks, 1):
        msg += f"{i}️⃣ {h} x {a}\n⏰ {hr}\n🎯 {m} ({p}%)\n\n"
        jogos_enviados.add(f"{h}-{a}")

    return msg

# 🔍 PESQUISA MANUAL
def pesquisa_manual(texto):
    if " x " not in texto:
        return "❌ Use: Time1 x Time2"

    home, away = texto.split(" x ")
    resultado = analisar(home.strip(), away.strip())

    if not resultado:
        return "❌ Jogo fraco ou sem dados"

    mercado, prob = resultado

    return f"🔎 {home} x {away}\n🎯 {mercado}\n📊 Probabilidade: {prob}%"

# 📲 ENVIAR
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# 🤖 BOT
def main():
    global last_update_id, ultimo_envio

    print("BOT ONLINE 🚀")

    while True:
        try:
            agora = time.time()

            # 🔥 ENVIO AUTOMÁTICO
            if agora - ultimo_envio > TEMPO_ENVIO:
                msg = gerar_multipla(3)
                if msg:
                    enviar(msg)
                ultimo_envio = agora

            # 🔥 COMANDOS TELEGRAM
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 30, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()

                if texto == "/start":
                    enviar("🤖 Gouvea Bet Online!\n\nUse:\nmultipla 3\nou\nTime x Time")

                elif texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(gerar_multipla(qtd) or "❌ Nenhum jogo forte")

                elif " x " in texto:
                    enviar(pesquisa_manual(texto))

        except Exception as e:
            print("ERRO:", e)

        time.sleep(2)

if __name__ == "__main__":
    main()
