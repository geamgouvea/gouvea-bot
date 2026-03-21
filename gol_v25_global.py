import requests
import time
import os
from datetime import datetime

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
jogos_enviados = set()
ultimo_envio = 0

# ================= REQUEST =================
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# ================= TIME =================
def buscar_time(nome):
    data = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data["response"]:
        return data["response"][0]["team"]["id"]
    return None

def pegar_jogos(team_id):
    data = safe_request(f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10")
    if data:
        return data.get("response", [])
    return []

# ================= ANALISE INTELIGENTE =================
def analisar(home, away):
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

    if len(gols) < 5:
        return None

    total = len(gols)

    over15 = sum(g >= 2 for g in gols) / total
    over25 = sum(g >= 3 for g in gols) / total
    under35 = sum(g <= 3 for g in gols) / total
    ambas = btts / total
    media = sum(gols) / total

    # 🔥 MAIS FLEXÍVEL (AGORA VAI DAR MAIS ENTRADA)
    if over25 >= 0.60 and media >= 2.5:
        entrada = "Over 2.5"
        prob = over25

    elif ambas >= 0.60:
        entrada = "Ambas marcam"
        prob = ambas

    elif over15 >= 0.70:
        entrada = "Over 1.5"
        prob = over15

    elif under35 >= 0.65:
        entrada = "Under 3.5"
        prob = under35

    else:
        return None

    prob = int(prob * 100)

    if prob >= 85:
        forca = 10
    elif prob >= 80:
        forca = 9
    elif prob >= 75:
        forca = 8
    else:
        forca = 7

    return entrada, prob, forca

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    jogos = []
    hoje = datetime.utcnow().strftime("%Y-%m-%d")

    data = safe_request(f"https://v3.football.api-sports.io/fixtures?date={hoje}")
    if not data:
        return []

    agora = datetime.now()

    for j in data.get("response", []):

        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
        dt = dt.astimezone()

        diff = (dt - agora).total_seconds()

        if diff < 0 or diff > 43200:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        jogos.append((home, away, dt.strftime("%H:%M")))

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

# ================= BOT ONLINE (ANTI-SPAM) =================
def iniciar():
    if not os.path.exists("bot_on.txt"):
        enviar("🤖 Gouvea Bet Inteligente Online!")
        with open("bot_on.txt", "w") as f:
            f.write("ok")

# ================= AUTOMATICO =================
def rodar_automatico():
    global jogos_enviados, ultimo_envio

    agora = time.time()

    # ⛔ evita spam (mínimo 5 minutos entre envios)
    if agora - ultimo_envio < 300:
        return

    jogos = buscar_jogos()

    for home, away, hora in jogos:

        chave = f"{home}x{away}"

        if chave in jogos_enviados:
            continue

        resultado = analisar(home, away)

        if resultado:
            entrada, prob, forca = resultado

            if prob >= 75:
                msg = f"""🔥 SINAL AUTOMÁTICO

⚽ {home} x {away}
⏰ {hora}

🎯 {entrada}
📊 {prob}%
🔥 Força: {forca}/10
"""
                enviar(msg)
                jogos_enviados.add(chave)
                ultimo_envio = agora
                break  # envia só 1 por ciclo

# ================= MULTIPLA =================
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for home, away, hora in jogos:
        resultado = analisar(home, away)

        if resultado:
            entrada, prob, _ = resultado
            picks.append((home, away, entrada, prob))

    picks.sort(key=lambda x: x[3], reverse=True)

    if len(picks) < qtd:
        return "❌ Nenhuma múltipla forte agora"

    msg = "🔥 MÚLTIPLA INTELIGENTE\n\n"

    for i, (h, a, e, p) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🎯 {e} ({p}%)\n\n"

    return msg

# ================= MANUAL =================
def analisar_manual(texto):
    try:
        home, away = texto.split(" x ")

        resultado = analisar(home, away)

        if not resultado:
            return "⚠️ Sem valor agora"

        entrada, prob, forca = resultado

        return f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 Melhor entrada: {entrada}
📊 {prob}%
🔥 Força: {forca}/10
"""
    except:
        return "❌ Use: Time x Time"

# ================= MAIN =================
def main():
    global last_update_id

    iniciar()

    ultimo_loop = 0

    while True:
        agora = time.time()

        if agora - ultimo_loop > 1800:  # 30 min
            rodar_automatico()
            ultimo_loop = agora

        try:
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
                    continue

                if " x " in texto:
                    enviar(analisar_manual(texto))
                    continue

        except Exception as e:
            print("ERRO:", e)

        time.sleep(3)

if __name__ == "__main__":
    main()
