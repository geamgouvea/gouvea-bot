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
JANELA_MIN = 5
JANELA_MAX = 720  # 12h

enviados_ids = set()
last_update_id = None

# ================= NORMALIZAR =================
def normalizar(txt):
    txt = txt.lower().strip()
    txt = unicodedata.normalize('NFKD', txt)
    return txt.encode('ASCII', 'ignore').decode('ASCII')

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

# ================= BUSCA INTELIGENTE =================
def buscar_fixture(home, away):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(15):  # 🔥 busca até 15 dias
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score = 0

            if home_n in h:
                score += 0.5
            if away_n in a:
                score += 0.5
            if home_n in a:
                score += 0.4
            if away_n in h:
                score += 0.4

            if score > melhor_score:
                melhor_score = score
                melhor = j

    # 🔥 NÃO BLOQUEIA MAIS
    return melhor

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ANALISE =================
def analisar(home, away):

    fixture = buscar_fixture(home, away)

    if not fixture:
        return "❌ Não encontrei esse jogo, tenta outro nome"

    home_id = fixture["teams"]["home"]["id"]
    away_id = fixture["teams"]["away"]["id"]

    jogos = historico(home_id) + historico(away_id)

    gols = []
    btts = 0

    for j in jogos:
        g1 = j["goals"]["home"]
        g2 = j["goals"]["away"]

        if g1 is None or g2 is None:
            continue

        total = g1 + g2
        gols.append(total)

        if g1 > 0 and g2 > 0:
            btts += 1

    if len(gols) == 0:
        return "⚠️ Sem dados suficientes"

    total = len(gols)
    media = sum(gols) / total

    over15 = sum(g >= 2 for g in gols) / total
    over25 = sum(g >= 3 for g in gols) / total
    under25 = sum(g <= 2 for g in gols) / total
    ambas = btts / total

    probs = {
        "Over 1.5": over15,
        "Over 2.5": over25,
        "Under 2.5": under25,
        "Ambas Marcam": ambas
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    dt = fixture["fixture"]["date"]
    dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    dt = dt - timedelta(hours=4)

    return f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name']} x {fixture["teams"]["away"]["name']}
🏆 {fixture["league"]["name"]}
📅 {dt.strftime("%d/%m")}
⏰ {dt.strftime("%H:%M")}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}
"""

# ================= MANUAL =================
def manual(texto):
    try:
        partes = re.split(r"x|vs|versus", texto.lower())

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        home = partes[0].strip()
        away = partes[1].strip()

        return analisar(home, away)

    except:
        return "⚠️ Erro no formato"

# ================= AUTO + MULTIPLA =================
def auto():
    while True:
        try:
            agora = datetime.utcnow()
            candidatos = []

            for i in range(2):
                data_busca = (agora + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
                if not data:
                    continue

                for j in data.get("response", []):
                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z", "+00:00"))
                    diff = (dt - agora).total_seconds() / 60

                    if diff < JANELA_MIN or diff > JANELA_MAX:
                        continue

                    res = analisar(
                        j["teams"]["home"]["name"],
                        j["teams"]["away"]["name"]
                    )

                    if "❌" in res or "⚠️" in res:
                        continue

                    candidatos.append((res, fid))

            # 🔥 ENVIA SINAIS
            for c in candidatos[:5]:
                enviar("🤖 AUTO\n\n" + c[0])
                enviados_ids.add(c[1])

            # 🔥 MÚLTIPLA (7 jogos)
            if len(candidatos) >= 7:
                multi = "🔥 MÚLTIPLA (7 jogos)\n\n"
                for c in candidatos[:7]:
                    multi += "• " + c[0].split("\n")[2] + "\n"

                enviar(multi)

            if len(candidatos) == 0:
                enviar("⚠️ AUTO: nenhum jogo encontrado")

        except Exception as e:
            enviar(f"ERRO: {e}")

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

                resposta = manual(texto)
                enviar(resposta)

        except:
            pass

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
