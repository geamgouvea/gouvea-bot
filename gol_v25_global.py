import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata
from difflib import SequenceMatcher
import re

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

AUTO_INTERVALO = 1800
JANELA_MIN = 10
JANELA_MAX = 720

enviados_ids = set()
last_update_id = None

# ================= UTILS =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def parse_data(data_str):
    try:
        return datetime.fromisoformat(data_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except:
        return None

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

# ================= BUSCAR JOGO (CORRIGIDO) =================
def buscar_fixture(home, away):

    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(15):  # 🔥 busca ampliada
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):

            status = j["fixture"]["status"]["short"]

            # 🔥 NÃO IGNORA jogos válidos
            if status in ["FT", "CANC"]:
                continue

            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score1 = (similar(home_n, h) + similar(away_n, a)) / 2
            score2 = (similar(home_n, a) + similar(away_n, h)) / 2

            final = max(score1, score2)

            # bônus por palavra chave
            if home_n.split()[0] in h:
                final += 0.10
            if away_n.split()[0] in a:
                final += 0.10

            if final > melhor_score:
                melhor_score = final
                melhor = j

    if melhor_score < 0.35:
        return None

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
        return fallback(home, away)

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

    if len(gols) < 5:
        return fallback(home, away)

    total = len(gols)

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

    if prob >= 0.75:
        nivel = "🔥 FORTE"
    elif prob >= 0.65:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}

📊 Probabilidades:
* Over 1.5: {int(over15*100)}%
* Over 2.5: {int(over25*100)}%
* Under 2.5: {int(under25*100)}%
* Ambas: {int(ambas*100)}%

🎯 Melhor entrada: {melhor}
📈 {int(prob*100)}%

{nivel}"""

# ================= FALLBACK INTELIGENTE =================
def fallback(home, away):

    base = 0.60

    return f"""🔎 ANÁLISE (Estimativa)

⚽ {home} x {away}

📊 Probabilidades:
* Over 1.5: {int(base*100)}%
* Over 2.5: 50%
* Under 2.5: 50%
* Ambas: 55%

⚠️ Dados limitados"""

# ================= MANUAL =================
def manual(texto):
    try:
        texto = texto.lower()

        partes = re.split(r"x|vs|versus", texto)

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        h = partes[0].strip()
        a = partes[1].strip()

        return analisar(h, a)

    except:
        return "⚠️ Erro na análise"

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.utcnow()
            candidatos = []

            for i in range(2):
                data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
                if not data:
                    continue

                for j in data.get("response", []):

                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    dt = parse_data(j["fixture"]["date"])
                    if not dt:
                        continue

                    diff = (dt - agora).total_seconds() / 60

                    if diff < JANELA_MIN or diff > JANELA_MAX:
                        continue

                    res = analisar(
                        j["teams"]["home"]["name"],
                        j["teams"]["away"]["name"]
                    )

                    candidatos.append((res, fid))

            enviados = 0

            for c, fid in candidatos[:5]:
                enviar("🤖 AUTO\n\n" + c)
                enviados_ids.add(fid)
                enviados += 1

            if enviados == 0:
                enviar("⚠️ Nenhum jogo encontrado")

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
