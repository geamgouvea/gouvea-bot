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
                score += 0.1
            if away_n.split()[0] in a:
                score += 0.1

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

# ================= ESCOLHA PROFISSIONAL =================
def escolher_melhor_entrada(probs):

    over15 = probs["Over 1.5"]
    over25 = probs["Over 2.5"]
    under25 = probs["Under 2.5"]
    btts = probs["Ambas Marcam"]

    # 🔥 mercados com valor primeiro
    if over25 >= 0.70:
        return "Over 2.5", over25

    if btts >= 0.68:
        return "Ambas Marcam", btts

    if under25 >= 0.78:
        return "Under 2.5", under25

    # fallback sem vício
    if over15 >= 0.80:
        return "Over 1.5", over15

    # fallback final
    melhor = max(probs, key=probs.get)
    return melhor, probs[melhor]

# ================= ANALISE =================
def analisar(home, away):

    fixture = buscar_fixture(home, away)

    if not fixture:
        return {
            "texto": f"""🔎 ANÁLISE

⚽ {home} x {away}

⚠️ Jogo não encontrado ou sem dados suficientes""",
            "prob": 0,
            "entrada": "-",
            "nivel": "erro",
            "fixture_id": None
        }

    home_id = fixture["teams"]["home"]["id"]
    away_id = fixture["teams"]["away"]["id"]

    jogos = historico(home_id) + historico(away_id)

    gols = []
    btts_count = 0

    for j in jogos:
        g1 = j["goals"]["home"]
        g2 = j["goals"]["away"]

        if g1 is None or g2 is None:
            continue

        total = g1 + g2
        gols.append(total)

        if g1 > 0 and g2 > 0:
            btts_count += 1

    if len(gols) < 6:
        return {
            "texto": f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}

⚠️ Poucos dados para análise""",
            "prob": 0,
            "entrada": "-",
            "nivel": "erro",
            "fixture_id": None
        }

    total = len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts_count / total
    }

    melhor, prob = escolher_melhor_entrada(probs)

    if prob < 0.65:
        nivel = "❌ DESCARTAR"
    elif prob >= 0.85:
        nivel = "🔥 FORTE"
    elif prob >= 0.72:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    dt = parse_data(fixture["fixture"]["date"])

    if dt:
        dt_local = dt - timedelta(hours=4)
        data_str = dt_local.strftime("%d/%m")
        hora_str = dt_local.strftime("%H:%M")
    else:
        data_str = "-"
        hora_str = "-"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return {
        "texto": f"""🔎 ANÁLISE

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

{nivel}""",
        "prob": prob,
        "entrada": melhor,
        "nivel": nivel,
        "fixture_id": fixture["fixture"]["id"]
    }

# ================= MULTIPLA =================
def montar_multipla(candidatos):

    multi = "💰 MÚLTIPLA PROFISSIONAL\n\n"

    contagem = {
        "Over 1.5": 0,
        "Over 2.5": 0,
        "Under 2.5": 0,
        "Ambas Marcam": 0
    }

    selecionados = []

    for c in candidatos:

        if c["nivel"] in ["⚠️ RISCO", "❌ DESCARTAR"]:
            continue

        entrada = c["entrada"]

        if contagem[entrada] >= 2:
            continue

        selecionados.append(c)
        contagem[entrada] += 1

        if len(selecionados) == 7:
            break

    if len(selecionados) < 5:
        return None

    for c in selecionados:
        jogo = c["texto"].split("\n")[2]
        multi += f"{jogo} → {c['entrada']}\n"

    return multi

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

                    if res["nivel"] in ["⚠️ RISCO", "❌ DESCARTAR"]:
                        continue

                    candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            for c in candidatos[:5]:
                enviar("🤖 AUTO\n\n" + c["texto"])
                enviados_ids.add(c["fixture_id"])

            multi = montar_multipla(candidatos)

            if multi:
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
                enviar(analisar(*re.split(r"x|vs|versus", texto.lower()))["texto"])

        except:
            pass

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
