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

last_update_id = None

# ================= UTILS =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)

    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
    if not data or not data.get("response"):
        return None

    return data["response"][0]["team"]["id"]

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ANALISE PROFISSIONAL =================
def analisar(home, away):

    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return "❌ Não consegui identificar os times"

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

    if len(gols) < 4:
        return "⚠️ Poucos dados — tendência neutra"

    total = len(gols)
    media = sum(gols) / total

    over15 = sum(g >= 2 for g in gols) / total
    over25 = sum(g >= 3 for g in gols) / total
    under25 = sum(g <= 2 for g in gols) / total
    btts_p = btts / total

    # ================= DECISÃO INTELIGENTE =================
    if over25 >= 0.65 and media >= 2.8:
        pick = "Over 2.5"
        prob = over25

    elif btts_p >= 0.65:
        pick = "Ambas Marcam"
        prob = btts_p

    elif under25 >= 0.65 and media <= 2.2:
        pick = "Under 2.5"
        prob = under25

    else:
        pick = "Over 1.5"
        prob = over15

    # ================= NÍVEL =================
    if prob >= 0.80:
        nivel = "🔥 FORTE"
    elif prob >= 0.70:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ ARRISCADO"

    return {
        "texto": f"""🧠 ANÁLISE

⚽ {home.title()} x {away.title()}

🎯 {pick}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}

{nivel}""",
        "prob": prob
    }

# ================= MULTIPLA PROFISSIONAL =================
def gerar_multipla():

    candidatos = []

    for i in range(2):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):

            home = j["teams"]["home"]["name"]
            away = j["teams"]["away"]["name"]

            res = analisar(home, away)

            if isinstance(res, dict) and res["prob"] >= 0.70:
                candidatos.append((home, away, res))

    candidatos.sort(key=lambda x: x[2]["prob"], reverse=True)

    tamanho = 7 if len(candidatos) >= 7 else len(candidatos)

    if tamanho < 5:
        return "⚠️ Poucos jogos bons hoje"

    picks = candidatos[:tamanho]

    msg = f"💰 MÚLTIPLA ({tamanho} jogos)\n\n"

    for i, (h, a, r) in enumerate(picks, 1):
        msg += f"{i}. {h} x {a}\n🎯 {r['texto'].split('🎯')[1].splitlines()[0]}\n\n"

    msg += "💵 Sugestão: R$5 a R$10"

    return msg

# ================= MANUAL =================
def manual(texto):

    texto = texto.lower().strip()

    if texto == "/multipla":
        return gerar_multipla()

    partes = re.split(r"x|vs|versus", texto)

    if len(partes) != 2:
        return "⚠️ Use: time x time"

    h = partes[0].strip()
    a = partes[1].strip()

    res = analisar(h, a)

    if isinstance(res, dict):
        return res["texto"]
    else:
        return res

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
