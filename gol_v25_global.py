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

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

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

# ================= BUSCA FORTE =================
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

            score = max(
                (similar(home_n, h) + similar(away_n, a)) / 2,
                (similar(home_n, a) + similar(away_n, h)) / 2
            )

            if home_n.split()[0] in h or away_n.split()[0] in a:
                score += 0.15

            if score > melhor_score:
                melhor_score = score
                melhor = j

    if melhor_score < 0.40:  # 🔥 mais flexível
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
        # 🔥 fallback obrigatório (NUNCA RETORNA VAZIO)
        return {
            "msg": f"""🔎 ANÁLISE (Fallback)

⚽ {home} x {away}

🎯 Over 1.5
📊 65%
⚠️ Estimativa (dados limitados)""",
            "prob": 0.65,
            "fixture_id": f"{home}-{away}"
        }

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
        return {
            "msg": f"""🔎 ANÁLISE

⚽ {home} x {away}

🎯 Over 1.5
📊 60%
⚠️ Poucos dados""",
            "prob": 0.60,
            "fixture_id": fixture["fixture"]["id"]
        }

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

    return {
        "msg": f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média: {round(media,2)}""",
        "prob": prob,
        "fixture_id": fixture["fixture"]["id"]
    }

# ================= MÚLTIPLA =================
def gerar_multipla(lista):
    if len(lista) < 7:
        return "⚠️ Múltipla insuficiente"

    jogos = lista[:10]

    msg = "🎯 MÚLTIPLA (7 a 10 jogos)\n\n"
    for j in jogos:
        msg += f"⚽ {j['msg'].splitlines()[2]}\n➡️ {j['msg'].splitlines()[4]}\n\n"

    msg += "💰 Sugestão: R$5 a R$10"

    return msg

# ================= AUTO =================
def auto():
    while True:
        try:
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

                    candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            if candidatos:
                enviar(gerar_multipla(candidatos))
            else:
                enviar("⚠️ Nenhum jogo hoje")

        except Exception as e:
            enviar(f"ERRO AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        partes = re.split(r"x|vs|versus", texto.lower())

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        return analisar(partes[0].strip(), partes[1].strip())["msg"]

    except:
        return "Erro"

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

        except Exception as e:
            enviar(f"ERRO: {e}")

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
