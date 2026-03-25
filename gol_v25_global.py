import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata
import re

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

AUTO_INTERVALO = 1800  # 30 min
JANELA_MIN = 10
JANELA_MAX = 360

enviados = set()
last_update_id = None

# ================= NORMALIZAR =================
def normalizar(txt):
    txt = txt.lower().strip()
    txt = unicodedata.normalize('NFKD', txt)
    return txt.encode('ascii', 'ignore').decode('ascii')

# ================= REQUEST =================
def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= BUSCAR JOGO (FORTE) =================
def buscar_jogo(home, away):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    # 🔥 busca ampla (15 dias)
    for i in range(15):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score = 0

            # match parcial inteligente
            if home_n in h or h in home_n:
                score += 1
            if away_n in a or a in away_n:
                score += 1

            if home_n in a or away_n in h:
                score += 0.5

            if score > melhor_score:
                melhor_score = score
                melhor = j

    return melhor  # 🔥 SEM BLOQUEIO

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ANALISE CASA/FORA =================
def analisar(home, away):

    jogo = buscar_jogo(home, away)

    if not jogo:
        return fallback(home, away)

    home_id = jogo["teams"]["home"]["id"]
    away_id = jogo["teams"]["away"]["id"]

    jogos_home = historico(home_id)
    jogos_away = historico(away_id)

    if not jogos_home or not jogos_away:
        return fallback(home, away)

    win_home = 0
    win_away = 0
    total = 0

    for j in jogos_home:
        g1 = j["goals"]["home"]
        g2 = j["goals"]["away"]
        if g1 is None or g2 is None:
            continue
        total += 1
        if g1 > g2:
            win_home += 1

    for j in jogos_away:
        g1 = j["goals"]["home"]
        g2 = j["goals"]["away"]
        if g1 is None or g2 is None:
            continue
        total += 1
        if g2 > g1:
            win_away += 1

    if total < 6:
        return fallback(home, away)

    prob_home = win_home / (len(jogos_home) or 1)
    prob_away = win_away / (len(jogos_away) or 1)

    if prob_home >= prob_away:
        escolha = "Casa vence 🏠"
        prob = prob_home
    else:
        escolha = "Fora vence ✈️"
        prob = prob_away

    if prob >= 0.75:
        nivel = "🔥 FORTE"
    elif prob >= 0.65:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    return f"""🔎 ANÁLISE

⚽ {jogo["teams"]["home"]["name"]} x {jogo["teams"]["away"]["name"]}

🎯 {escolha}
📊 {int(prob*100)}%

{nivel}"""

# ================= FALLBACK =================
def fallback(home, away):
    return f"""🔎 ANÁLISE (Fallback)

⚽ {home} x {away}

🎯 Casa vence 🏠
📊 60%

⚠️ Dados limitados"""

# ================= MANUAL =================
def manual(texto):
    partes = re.split(r"x|vs|versus", texto.lower())

    if len(partes) != 2:
        return "⚠️ Use: time x time"

    h = partes[0].strip()
    a = partes[1].strip()

    return analisar(h, a)

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.utcnow()
            lista = []

            for i in range(2):
                data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
                if not data:
                    continue

                for j in data.get("response", []):
                    fid = j["fixture"]["id"]

                    if fid in enviados:
                        continue

                    dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z", "+00:00"))

                    diff = (dt - agora).total_seconds() / 60

                    if diff < JANELA_MIN or diff > JANELA_MAX:
                        continue

                    res = analisar(
                        j["teams"]["home"]["name"],
                        j["teams"]["away"]["name"]
                    )

                    lista.append((res, fid))

            for r, fid in lista[:5]:
                enviar("🤖 AUTO\n\n" + r)
                enviados.add(fid)

            if not lista:
                enviar("⚠️ AUTO: Nenhum jogo encontrado")

        except Exception as e:
            enviar(f"❌ ERRO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ONLINE")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id or 0}
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "")
                enviar(manual(texto))

        except:
            pass

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
