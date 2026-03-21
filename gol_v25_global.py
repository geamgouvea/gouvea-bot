import requests
import time
import threading
from datetime import datetime

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

jogos_enviados = set()
ultimo_envio = 0
last_update_id = None

# ================= LIGAS PERMITIDAS (TOP) =================
LIGAS_PERMITIDAS = [
    "Brazil",
    "England",
    "Spain",
    "Italy",
    "Germany",
    "France",
    "Netherlands",
    "Belgium",
    "Austria",
    "Portugal",
    "Japan",
    "South Korea",
    "Australia",
    "Saudi Arabia"
]

# ================= REQUEST =================
def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# ================= BUSCAR TIME =================
def buscar_time(nome):
    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data["response"]:
        return data["response"][0]["team"]["id"]
    return None

# ================= HISTÓRICO =================
def jogos_time(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
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

    jogos = jogos_time(home_id) + jogos_time(away_id)

    gols = []

    for j in jogos:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            if g1 is None or g2 is None:
                continue

            gols.append(g1 + g2)
        except:
            continue

    if len(gols) < 6:
        return None

    total = len(gols)
    media = sum(gols) / total

    over15 = sum(g >= 2 for g in gols) / total
    over25 = sum(g >= 3 for g in gols) / total

    # 🎯 EQUILÍBRIO
    if over25 >= 0.55 and media >= 2.3:
        entrada = "Over 2.5"
        prob = over25
    elif over15 >= 0.65:
        entrada = "Over 1.5"
        prob = over15
    else:
        return None

    prob = int(prob * 100)
    forca = 10 if prob >= 85 else 9 if prob >= 78 else 8 if prob >= 70 else 7

    return entrada, prob, forca

# ================= FILTRO DE LIGAS =================
def liga_permitida(nome_liga):
    nome = nome_liga.lower()
    return any(l.lower() in nome for l in LIGAS_PERMITIDAS)

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = req("https://v3.football.api-sports.io/fixtures", {"next": 80})
    if not data:
        return []

    jogos = []
    agora = datetime.utcnow()

    for j in data["response"]:
        liga_nome = j["league"]["country"]

        # 🔥 FILTRO AQUI
        if not liga_permitida(liga_nome):
            continue

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

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= AUTO =================
def auto_sinais():
    global ultimo_envio

    while True:
        try:
            agora = time.time()

            if agora - ultimo_envio > 1200:
                jogos = buscar_jogos()
                enviados = 0

                for home, away, hora in jogos:
                    chave = f"{home}x{away}"

                    if chave in jogos_enviados:
                        continue

                    res = analisar(home, away)

                    if res:
                        entrada, prob, forca = res

                        msg = f"""🔥 SINAL

⚽ {home} x {away}
⏰ {hora}

🎯 {entrada}
📊 {prob}%
⭐ {forca}/10
"""

                        enviar(msg)
                        jogos_enviados.add(chave)
                        enviados += 1

                    if enviados >= 3:
                        break

                ultimo_envio = agora

        except:
            pass

        time.sleep(10)

# ================= MÚLTIPLA =================
def gerar_multipla(qtd=5):
    jogos = buscar_jogos()
    picks = []

    for home, away, _ in jogos:
        res = analisar(home, away)
        if res:
            entrada, prob, forca = res
            if forca >= 7:
                picks.append((home, away, entrada, prob))

    picks.sort(key=lambda x: x[3], reverse=True)

    if len(picks) < 2:
        return "❌ Sem múltipla forte agora"

    msg = "🔥 MÚLTIPLA DO DIA\n\n"

    for i, (h, a, e, p) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🎯 {e} ({p}%)\n\n"

    return msg

# ================= MANUAL =================
def manual(texto):
    if "x" not in texto:
        enviar("Formato: Time A x Time B")
        return

    try:
        home, away = texto.split("x")
        home = home.strip()
        away = away.strip()
    except:
        return

    res = analisar(home, away)

    if not res:
        enviar("⚠️ Sem valor agora")
        return

    entrada, prob, forca = res

    msg = f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 {entrada}
📊 {prob}%
⭐ {forca}/10
"""

    enviar(msg)

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 Gouvea Bet LIGAS FILTRADAS Online!")

    while True:
        try:
            updates = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 10, "offset": last_update_id}
            ).json()

            for u in updates.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "").lower().strip()

                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 5
                    enviar(gerar_multipla(qtd))
                else:
                    manual(texto)

        except:
            pass

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto_sinais).start()
    main()
