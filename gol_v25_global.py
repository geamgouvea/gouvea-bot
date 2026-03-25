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

AUTO_INTERVALO = 1800
JANELA_MIN = 20
JANELA_MAX = 720

enviados_ids = set()
last_update_id = None

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

# ================= REQUEST =================
def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
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

# ================= BUSCAR FIXTURE (REESCRITO) =================
def buscar_fixture(home, away):

    home = normalizar(home)
    away = normalizar(away)

    for i in range(3):  # hoje + 2 dias
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            # 🔥 MATCH FLEXÍVEL REAL
            if (
                (home in h or h in home) and
                (away in a or a in away)
            ) or (
                (home in a or a in home) and
                (away in h or h in away)
            ):
                return j

    return None

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
        return None

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

    if len(gols) < 6:
        return None

    total = len(gols)
    media = sum(gols) / total

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts / total
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    dt = datetime.fromisoformat(
        fixture["fixture"]["date"].replace("Z", "+00:00")
    )

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return {
        "msg": f"""⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média: {round(media,2)}""",
        "prob": prob,
        "fixture_id": fixture["fixture"]["id"]
    }

# ================= MULTIPLA =================
def gerar_multipla():

    candidatos = []

    for i in range(2):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):
            res = analisar(
                j["teams"]["home"]["name"],
                j["teams"]["away"]["name"]
            )

            if res and res["prob"] >= 0.70:
                candidatos.append(res)

    candidatos.sort(key=lambda x: x["prob"], reverse=True)

    picks = candidatos[:7]

    if len(picks) < 7:
        return "⚠️ Poucos jogos confiáveis hoje"

    msg = "💰 MÚLTIPLA (7 jogos)\n\n"

    for i, p in enumerate(picks, 1):
        msg += f"{i}. {p['msg']}\n\n"

    msg += "💵 Sugestão: R$5 a R$10"

    return msg

# ================= MANUAL =================
def manual(texto):

    texto = texto.lower()

    if texto == "/multipla":
        return gerar_multipla()

    partes = re.split(r"x|vs|versus", texto)

    if len(partes) != 2:
        return "⚠️ Use: time x time"

    h = partes[0].strip()
    a = partes[1].strip()

    res = analisar(h, a)

    if not res:
        return "❌ Jogo não encontrado"

    return "🧠 ANÁLISE\n\n" + res["msg"]

# ================= AUTO =================
def auto():
    while True:
        try:
            enviar("🤖 AUTO\n\n" + gerar_multipla())
        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

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

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
