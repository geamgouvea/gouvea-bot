import requests
import time
from datetime import datetime

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
bot_iniciado = False
jogos_enviados = set()

# ================= REQUEST =================
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("ERRO REQUEST:", e)
    return None

# ================= BUSCAR TIMES =================
def buscar_time(nome):
    data = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
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

# ================= ANÁLISE =================
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
    media = sum(gols) / total

    over15 = sum(g >= 2 for g in gols) / total
    over25 = sum(g >= 3 for g in gols) / total
    under35 = sum(g <= 3 for g in gols) / total
    ambas = btts / total

    # 🎯 LÓGICA EQUILIBRADA (NÃO TRAVA)
    if over25 >= 0.58 and media >= 2.4:
        entrada = "Over 2.5"
        prob = over25

    elif ambas >= 0.58:
        entrada = "Ambas marcam"
        prob = ambas

    elif over15 >= 0.68:
        entrada = "Over 1.5"
        prob = over15

    elif under35 >= 0.63:
        entrada = "Under 3.5"
        prob = under35

    else:
        return None

    prob = int(prob * 100)

    if prob < 70:
        return None

    forca = 10 if prob >= 85 else 9 if prob >= 80 else 8

    return entrada, prob, forca

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = safe_request("https://v3.football.api-sports.io/fixtures", {"next": 50})
    if not data:
        return []

    jogos = []
    agora = datetime.utcnow()

    for j in data.get("response", []):
        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
        diff = (dt - agora).total_seconds()

        if diff < 0 or diff > 43200:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]
        hora = dt.strftime("%H:%M")

        jogos.append((home, away, hora))

    return jogos

# ================= ENVIAR =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print("ERRO ENVIO:", e)

# ================= AUTOMÁTICO =================
def enviar_sinais():
    jogos = buscar_jogos()

    for home, away, hora in jogos:
        chave = f"{home}x{away}"

        if chave in jogos_enviados:
            continue

        resultado = analisar(home, away)

        if resultado:
            entrada, prob, forca = resultado

            msg = f"""🔥 SINAL AUTOMÁTICO

⚽ {home} x {away}
⏰ {hora}

🎯 {entrada}
📊 {prob}%
🔥 Força: {forca}/10
"""

            enviar(msg)
            jogos_enviados.add(chave)

# ================= MANUAL =================
def analise_manual(texto):
    if "x" not in texto:
        return

    try:
        partes = texto.split("x")
        home = partes[0].strip()
        away = partes[1].strip()
    except:
        return

    resultado = analisar(home, away)

    if not resultado:
        enviar("⚠️ Jogo sem valor agora")
        return

    entrada, prob, forca = resultado

    msg = f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 Melhor entrada: {entrada}
📊 {prob}%
🔥 Força: {forca}/10
"""

    enviar(msg)

# ================= MÚLTIPLA =================
def gerar_multipla(qtd=2):
    jogos = buscar_jogos()
    picks = []

    for home, away, hora in jogos:
        resultado = analisar(home, away)
        if resultado:
            entrada, prob, _ = resultado
            picks.append((home, away, entrada, prob))

    picks.sort(key=lambda x: x[3], reverse=True)

    if not picks:
        return "❌ Nenhuma múltipla forte agora"

    msg = "🔥 MÚLTIPLA INTELIGENTE\n\n"

    for i, (h, a, e, p) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🎯 {e} ({p}%)\n\n"

    return msg

# ================= MAIN =================
def main():
    global last_update_id, bot_iniciado

    if not bot_iniciado:
        enviar("🤖 Gouvea Bet Inteligente Online!")
        bot_iniciado = True

    ultimo_loop = 0

    while True:
        try:
            agora = time.time()

            # 🔁 automático 30 min
            if agora - ultimo_loop > 1800:
                enviar_sinais()
                ultimo_loop = agora

            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 10, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                msg = u["message"]

                if "text" not in msg:
                    continue

                texto = msg["text"].lower().strip()

                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 2
                    enviar(gerar_multipla(qtd))
                else:
                    analise_manual(texto)

        except Exception as e:
            print("ERRO LOOP:", e)

        time.sleep(5)

if __name__ == "__main__":
    main()
