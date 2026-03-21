import requests
import time
from datetime import datetime

# 🔐 CONFIG
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
bot_iniciado = False
jogos_enviados = set()

# 🔒 REQUEST SEGURO
def safe_request(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# 🕒 PEGAR JOGOS (12H)
def buscar_jogos():
    url = "https://v3.football.api-sports.io/fixtures"
    hoje = datetime.utcnow().strftime("%Y-%m-%d")

    data = safe_request(f"{url}?date={hoje}")
    if not data:
        return []

    jogos = []
    agora = datetime.utcnow()

    for j in data["response"]:
        status = j["fixture"]["status"]["short"]

        # Só pré-jogo
        if status != "NS":
            continue

        data_jogo = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))

        diff = (data_jogo - agora).total_seconds()

        # Apenas próximas 12h
        if diff < 0 or diff > 43200:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]
        hora = data_jogo.strftime("%H:%M")

        jogos.append((home, away, hora))

    return jogos

# 📊 HISTÓRICO
def pegar_jogos(team):
    data = safe_request(f"https://v3.football.api-sports.io/fixtures?team={team}&last=10")
    if not data:
        return []

    return data["response"]

# 🔎 BUSCAR TIME
def buscar_time(nome):
    data = safe_request(f"https://v3.football.api-sports.io/teams?search={nome}")
    if not data or not data["response"]:
        return None

    return data["response"][0]["team"]["id"]

# 🧠 ANÁLISE INTELIGENTE REAL
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

            total = g1 + g2
            gols.append(total)

            if g1 > 0 and g2 > 0:
                btts += 1
        except:
            continue

    if len(gols) < 6:
        return None

    total_jogos = len(gols)
    media = sum(gols) / total_jogos

    over15 = sum(g >= 2 for g in gols) / total_jogos
    over25 = sum(g >= 3 for g in gols) / total_jogos
    under35 = sum(g <= 3 for g in gols) / total_jogos
    btts = btts / total_jogos

    # 🎯 DECISÃO INTELIGENTE
    if over25 >= 0.6 and media >= 2.5:
        mercado = "Over 2.5"
        prob = over25
    elif btts >= 0.6:
        mercado = "Ambas marcam"
        prob = btts
    elif over15 >= 0.7:
        mercado = "Over 1.5"
        prob = over15
    elif under35 >= 0.65:
        mercado = "Under 3.5"
        prob = under35
    else:
        return None

    prob = int(prob * 100)

    if prob < 70:
        return None

    forca = 10 if prob >= 85 else 9 if prob >= 80 else 8

    return mercado, prob, forca

# 📩 ENVIAR TELEGRAM
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

# 🔥 SINAL AUTOMÁTICO
def enviar_sinais():
    jogos = buscar_jogos()

    for home, away, hora in jogos:
        chave = f"{home}x{away}"

        if chave in jogos_enviados:
            continue

        resultado = analisar(home, away)

        if resultado:
            mercado, prob, forca = resultado

            msg = f"""🔥 SINAL AUTOMÁTICO

⚽ {home} x {away}
⏰ {hora}

🎯 {mercado}
📊 {prob}%
🔥 Força: {forca}/10
"""

            enviar(msg)
            jogos_enviados.add(chave)

# 🎯 MÚLTIPLA
def gerar_multipla(qtd=2):
    jogos = buscar_jogos()
    picks = []

    for home, away, hora in jogos:
        resultado = analisar(home, away)
        if resultado:
            mercado, prob, _ = resultado
            picks.append((home, away, mercado, prob))

    picks.sort(key=lambda x: x[3], reverse=True)
    picks = picks[:qtd]

    if not picks:
        return "❌ Nenhuma múltipla forte agora"

    msg = "🔥 MÚLTIPLA INTELIGENTE\n\n"

    for i, (h, a, m, p) in enumerate(picks, 1):
        msg += f"{i}️⃣ {h} x {a}\n🎯 {m} ({p}%)\n\n"

    return msg

# 🔍 ANÁLISE MANUAL
def analise_manual(texto):
    if " x " not in texto:
        return

    home, away = texto.split(" x ")

    resultado = analisar(home.strip(), away.strip())

    if not resultado:
        enviar("⚠️ Jogo sem valor agora")
        return

    mercado, prob, forca = resultado

    msg = f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 Melhor entrada: {mercado}
📊 {prob}%
🔥 Força: {forca}/10
"""

    enviar(msg)

# 🤖 BOT PRINCIPAL
def main():
    global last_update_id, bot_iniciado

    if not bot_iniciado:
        enviar("🤖 Gouvea Bet Inteligente Online!")
        bot_iniciado = True

    tempo_loop = 1800  # 30 minutos
    ultimo_envio = 0

    while True:
        try:
            agora = time.time()

            # 🔁 LOOP AUTOMÁTICO
            if agora - ultimo_envio > tempo_loop:
                enviar_sinais()
                ultimo_envio = agora

            # 📩 TELEGRAM
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 10, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()

                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 2
                    enviar(gerar_multipla(qtd))

                else:
                    analise_manual(texto)

        except Exception as e:
            print("ERRO:", e)

        time.sleep(5)

if __name__ == "__main__":
    main()
