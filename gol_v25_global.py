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
ultimo_loop = time.time()

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

# ================= ANÁLISE INTELIGENTE =================
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    jogos_home = pegar_jogos(home_id)
    jogos_away = pegar_jogos(away_id)

    gols = []
    btts = 0
    vitorias_home = 0
    vitorias_away = 0

    for j in jogos_home + jogos_away:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            if g1 is None or g2 is None:
                continue

            gols.append(g1 + g2)

            if g1 > 0 and g2 > 0:
                btts += 1

            if g1 > g2:
                vitorias_home += 1
            elif g2 > g1:
                vitorias_away += 1

        except:
            continue

    if len(gols) < 6:
        return None

    total = len(gols)

    over15 = sum(g >= 2 for g in gols) / total
    over25 = sum(g >= 3 for g in gols) / total
    under35 = sum(g <= 3 for g in gols) / total
    ambas = btts / total

    win_home = vitorias_home / total
    win_away = vitorias_away / total

    # 🎯 DECISÃO INTELIGENTE
    entrada = None
    prob = 0

    if win_home >= 0.55:
        entrada = "Casa vence"
        prob = win_home

    elif win_away >= 0.55:
        entrada = "Fora vence"
        prob = win_away

    elif over25 >= 0.55:
        entrada = "Over 2.5"
        prob = over25

    elif ambas >= 0.55:
        entrada = "Ambas marcam"
        prob = ambas

    elif over15 >= 0.65:
        entrada = "Over 1.5"
        prob = over15

    elif under35 >= 0.60:
        entrada = "Under 3.5"
        prob = under35

    if not entrada:
        return None

    prob = int(prob * 100)

    if prob < 70:
        return None

    forca = 10 if prob >= 85 else 9 if prob >= 78 else 8

    return entrada, prob, forca

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = safe_request("https://v3.football.api-sports.io/fixtures", {"next": 40})
    if not data:
        return []

    jogos = []
    agora = datetime.utcnow()

    for j in data.get("response", []):
        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
        diff = (dt - agora).total_seconds()

        if 0 < diff <= 43200:
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
    except:
        pass

# ================= AUTOMÁTICO =================
def enviar_sinais():
    jogos = buscar_jogos()
    enviados = 0

    for home, away, hora in jogos:
        chave = f"{home}x{away}"

        if chave in jogos_enviados:
            continue

        resultado = analisar(home, away)

        if resultado:
            entrada, prob, forca = resultado

            msg = f"""🔥 SINAL

⚽ {home} x {away}
⏰ {hora}

🎯 {entrada}
📊 {prob}%
🔥 Força: {forca}/10
"""

            enviar(msg)
            jogos_enviados.add(chave)
            enviados += 1

        if enviados >= 2:
            break

# ================= MANUAL =================
def analise_manual(texto):
    if "x" not in texto:
        return

    home, away = texto.split("x")
    home = home.strip()
    away = away.strip()

    resultado = analisar(home, away)

    if not resultado:
        enviar("⚠️ Sem valor agora (ou poucos dados)")
        return

    entrada, prob, forca = resultado

    enviar(f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 Melhor entrada: {entrada}
📊 {prob}%
🔥 Força: {forca}/10
""")

# ================= MÚLTIPLA =================
def gerar_multipla(qtd=2):
    jogos = buscar_jogos()
    picks = []

    for home, away, _ in jogos:
        r = analisar(home, away)
        if r:
            entrada, prob, _ = r
            if prob >= 75:
                picks.append((home, away, entrada, prob))

    picks.sort(key=lambda x: x[3], reverse=True)

    if len(picks) < qtd:
        return "❌ Sem múltipla forte agora"

    msg = "🔥 MÚLTIPLA\n\n"

    for i, (h, a, e, p) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🎯 {e} ({p}%)\n\n"

    return msg

# ================= MAIN =================
def main():
    global last_update_id, bot_iniciado, ultimo_loop

    if not bot_iniciado:
        enviar("🤖 Gouvea Bet Inteligente Online!")
        bot_iniciado = True

    while True:
        try:
            agora = time.time()

            # 🔁 LOOP 30 MIN
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

                texto = u["message"].get("text", "").lower()

                if texto.startswith("multipla"):
                    qtd = int(texto.split()[1]) if len(texto.split()) > 1 else 2
                    enviar(gerar_multipla(qtd))
                else:
                    analise_manual(texto)

        except Exception as e:
            print("ERRO:", e)

        time.sleep(5)

if __name__ == "__main__":
    main()
