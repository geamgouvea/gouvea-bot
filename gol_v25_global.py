import requests
import time
from datetime import datetime

# 🔐 CONFIG
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
jogos_usados = set()
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

# 📲 ENVIAR
def enviar(chat_id, msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": msg},
            timeout=10
        )
    except:
        pass

# 🔍 TIME
def buscar_time(nome):
    res = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
    if not res: return None
    data = res.json()
    if data["response"]:
        return data["response"][0]["team"]["id"]
    return None

# 📊 HISTÓRICO
def pegar_jogos(team_id):
    res = safe_request(f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10")
    if not res: return []
    return res.json().get("response", [])

# 🧠 ANÁLISE
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    jogos_home = pegar_jogos(home_id)
    jogos_away = pegar_jogos(away_id)

    gols = []
    btts = 0
    win_home = 0
    win_away = 0

    for j in jogos_home:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]
            if g1 is None or g2 is None:
                continue

            gols.append(g1 + g2)
            if g1 > 0 and g2 > 0:
                btts += 1
            if g1 > g2:
                win_home += 1
        except:
            continue

    for j in jogos_away:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]
            if g1 is None or g2 is None:
                continue

            gols.append(g1 + g2)
            if g1 > 0 and g2 > 0:
                btts += 1
            if g2 > g1:
                win_away += 1
        except:
            continue

    if len(gols) < 6:
        return None

    total = len(gols)

    stats = {
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Ambas marcam": btts / total,
        "Under 3.5": sum(g <= 3 for g in gols) / total,
        "Casa vence": win_home / len(jogos_home) if jogos_home else 0,
        "Fora vence": win_away / len(jogos_away) if jogos_away else 0
    }

    melhor = max(stats, key=stats.get)
    prob = int(stats[melhor] * 100)

    if prob < 75:
        return None

    return melhor, prob

# ⚽ BUSCAR JOGOS
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

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
        dt = dt.astimezone()

        diff = (dt - agora).total_seconds()

        if diff < 0 or diff > 43200:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        chave = f"{home}-{away}"

        if chave in jogos_usados:
            continue

        jogos.append((home, away, dt.strftime("%H:%M"), chave))

    return jogos

# 🔥 MULTIPLA INTELIGENTE
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    usados_tipos = set()

    for home, away, hora, chave in jogos:
        resultado = analisar(home, away)

        if not resultado:
            continue

        tipo, prob = resultado

        # evitar repetir tipo
        if tipo in usados_tipos:
            continue

        usados_tipos.add(tipo)
        jogos_usados.add(chave)

        picks.append((home, away, tipo, prob, hora))

    picks.sort(key=lambda x: x[3], reverse=True)
    picks = picks[:qtd]

    if not picks:
        return "❌ Nenhuma múltipla forte encontrada"

    msg = "🔥 GOUVEA BET – MÚLTIPLA ABSURDA\n\n"

    for i, (h, a, t, p, hr) in enumerate(picks, 1):
        msg += f"{i}️⃣ {h} x {a}\n⏰ {hr}\n🎯 {t} ({p}%)\n\n"

    return msg

# 🤖 BOT
def main():
    global last_update_id, ultimo_envio

    print("BOT ABSURDO ONLINE 🚀")

    while True:
        try:
            # 🔥 AUTO ENVIO
            if time.time() - ultimo_envio > 1800:
                msg = gerar_multipla(3)
                enviar(CHAT_ID_FIXO, msg)
                ultimo_envio = time.time()

            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 30, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u or "text" not in u["message"]:
                    continue

                chat_id = u["message"]["chat"]["id"]
                texto = u["message"]["text"].lower().strip()

                if texto == "/start":
                    enviar(chat_id, "🤖 BOT ATIVO – use: multipla 3 ou Time A x Time B")
                    continue

                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(chat_id, gerar_multipla(qtd))
                    continue

                if " x " in texto:
                    home, away = texto.split(" x ")
                    r = analisar(home, away)

                    if not r:
                        enviar(chat_id, "❌ Jogo fraco ou sem dados")
                        continue

                    tipo, prob = r
                    enviar(chat_id, f"{home} x {away}\n🎯 {tipo}\n📊 {prob}%")
                    continue

        except Exception as e:
            print("ERRO:", e)

        time.sleep(2)

if __name__ == "__main__":
    main()
