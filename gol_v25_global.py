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

# 🔥 CORREÇÃO DEFINITIVA DO DATETIME
def parse_data(data_str):
    try:
        dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)  # remove timezone
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

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away):

    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(15):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):

            status = j["fixture"]["status"]["short"]
            if status in ["FT", "CANC"]:
                continue

            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score = max(
                (similar(home_n, h) + similar(away_n, a)) / 2,
                (similar(home_n, a) + similar(away_n, h)) / 2
            )

            if home_n.split()[0] in h:
                score += 0.10
            if away_n.split()[0] in a:
                score += 0.10

            if score > melhor_score:
                melhor_score = score
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

# ================= ESCOLHA INTELIGENTE =================
def escolher_melhor_entrada(probs):

    ordenado = sorted(probs.items(), key=lambda x: x[1], reverse=True)

    melhor, prob = ordenado[0]
    segundo, prob2 = ordenado[1]

    if prob - prob2 >= 0.10:
        return melhor, prob

    if melhor == "Over 1.5" and prob < 0.78:
        return segundo, prob2

    return melhor, prob

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

    if len(gols) < 6:
        return fallback(home, away)

    total = len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts / total
    }

    melhor, prob = escolher_melhor_entrada(probs)

    # nível
    if prob >= 0.85:
        nivel = "🔥 FORTE"
    elif prob >= 0.72:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    # DATA E HORA CORRIGIDO
    dt = parse_data(fixture["fixture"]["date"])
    if dt:
        dt_local = dt - timedelta(hours=4)
        data_str = dt_local.strftime("%d/%m")
        hora_str = dt_local.strftime("%H:%M")
    else:
        data_str = "-"
        hora_str = "-"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}
📅 {data_str}
⏰ {hora_str}

📊 Probabilidades:
* Over 1.5: {int(probs["Over 1.5"]*100)}%
* Over 2.5: {int(probs["Over 2.5"]*100)}%
* Under 2.5: {int(probs["Under 2.5"]*100)}%
* Ambas: {int(probs["Ambas Marcam"]*100)}%

🎯 Melhor entrada: {melhor}
📈 {int(prob*100)}%

{nivel}"""

# ================= FALLBACK =================
def fallback(home, away):
    return f"""🔎 ANÁLISE (Estimativa)

⚽ {home} x {away}

⚠️ Dados insuficientes"""

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

                    if "Estimativa" in res:
                        continue

                    candidatos.append((res, fid))

            # ENVIO
            for c, fid in candidatos[:5]:
                enviar("🤖 AUTO\n\n" + c)
                enviados_ids.add(fid)

            # MÚLTIPLA INTELIGENTE
            if len(candidatos) >= 7:
                multi = "💰 MÚLTIPLA SUGERIDA\n\n"

                for c, _ in candidatos[:7]:
                    jogo = c.split("\n")[2]
                    entrada = c.split("Melhor entrada:")[1].split("\n")[0]
                    multi += f"{jogo} → {entrada}\n"

                enviar(multi)

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

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
