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
JANELA_MIN = 5
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
        return datetime.fromisoformat(data_str.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
    except:
        return None

def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
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

# ================= DECISÃO PROFISSIONAL =================
def escolher_entrada(probs):

    over15 = probs["Over 1.5"]
    over25 = probs["Over 2.5"]
    under25 = probs["Under 2.5"]
    btts = probs["Ambas Marcam"]

    # 🔥 PRIORIDADE DE VALOR (AGRESSIVO)

    # 1️⃣ Over 2.5 forte
    if over25 >= 0.65:
        return "Over 2.5", over25

    # 2️⃣ Ambas marcam forte
    if btts >= 0.62:
        return "Ambas Marcam", btts

    # 3️⃣ Under forte (defensivo real)
    if under25 >= 0.78:
        return "Under 2.5", under25

    # 4️⃣ Over 2.5 médio (valor > segurança)
    if over25 >= 0.55:
        return "Over 2.5", over25

    # 5️⃣ Ambas médio
    if btts >= 0.55:
        return "Ambas Marcam", btts

    # 6️⃣ fallback controlado
    if over15 >= 0.75:
        return "Over 1.5", over15

    # 7️⃣ último recurso
    melhor = max(probs, key=probs.get)
    return melhor, probs[melhor]

# ================= ANALISE =================
def analisar(home, away):

    fixture = buscar_fixture(home, away)

    if not fixture:
        return {
            "msg": f"⚠️ Não encontrei jogo para: {home} x {away}",
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

    if len(gols) < 5:
        return {
            "msg": "⚠️ Dados insuficientes",
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

    melhor, prob = escolher_entrada(probs)

    # 🎯 NÍVEL
    if prob >= 0.80:
        nivel = "🔥 FORTE"
    elif prob >= 0.68:
        nivel = "⚖️ MÉDIA"
    elif prob >= 0.58:
        nivel = "⚠️ RISCO"
    else:
        nivel = "❌ DESCARTAR"

    dt = parse_data(fixture["fixture"]["date"])

    if dt:
        data_str = dt.strftime("%d/%m")
        hora_str = dt.strftime("%H:%M")
    else:
        data_str = "-"
        hora_str = "-"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    texto = f"""🔎 ANÁLISE

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

    return {
        "msg": texto,
        "prob": prob,
        "entrada": melhor,
        "nivel": nivel,
        "fixture_id": fixture["fixture"]["id"]
    }

# ================= MULTIPLA =================
def montar_multipla(candidatos):

    candidatos = [c for c in candidatos if c["nivel"] in ["🔥 FORTE", "⚖️ MÉDIA"]]

    if len(candidatos) < 7:
        return None

    candidatos.sort(key=lambda x: x["prob"], reverse=True)

    selecionados = candidatos[:7]

    msg = "💰 MÚLTIPLA AGRESSIVA\n\n"

    for c in selecionados:
        jogo = c["msg"].split("\n")[2]
        msg += f"{jogo} → {c['entrada']}\n"

    msg += "\n💵 Entrada sugerida: R$5 a R$10"

    return msg

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.now()
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

                    if res["prob"] > 0:
                        candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            for c in candidatos[:5]:
                enviar("🤖 AUTO\n\n" + c["msg"])
                enviados_ids.add(c["fixture_id"])

            multi = montar_multipla(candidatos)
            if multi:
                enviar(multi)

        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        partes = re.split(r"x|vs|versus", texto.lower())

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        h = partes[0].strip()
        a = partes[1].strip()

        res = analisar(h, a)
        return res["msg"]

    except:
        return "⚠️ Erro no comando"

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT AGRESSIVO ONLINE")

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
