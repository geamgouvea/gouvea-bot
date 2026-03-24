import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata
from difflib import SequenceMatcher

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

AUTO_INTERVALO = 1800  # 30 minutos
JANELA_MIN = 0
JANELA_MAX = 1440  # 24h

enviados_ids = set()
last_update_id = None

# ================= BASE =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            print("Erro API:", r.status_code, r.text)
    except Exception as e:
        print("Erro request:", e)
    return None

def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

def parse_data(data_str):
    try:
        dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except:
        return None

# ================= BUSCA INTELIGENTE =================
def buscar_fixture(home, away):

    home_n = normalizar(home)
    away_n = normalizar(away)

    data = req("https://v3.football.api-sports.io/fixtures", {
        "next": 100
    })

    if not data:
        print("Erro ao buscar fixtures")
        return None

    melhor = None
    melhor_score = 0

    for j in data.get("response", []):

        h = normalizar(j["teams"]["home"]["name"])
        a = normalizar(j["teams"]["away"]["name"])

        score = (similar(home_n, h) + similar(away_n, a)) / 2
        score_inv = (similar(home_n, a) + similar(away_n, h)) / 2

        final = max(score, score_inv)

        if final > melhor_score:
            melhor_score = final
            melhor = j

    print(f"[DEBUG] {home} x {away} | score: {round(melhor_score,2)}")

    if melhor_score < 0.40:
        return None

    return melhor

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= DECISÃO =================
def escolher_mercado(media, probs):

    if media >= 3.0 and probs["Over 2.5"] >= 0.60:
        return "Over 2.5", probs["Over 2.5"]

    if probs["Ambas Marcam"] >= 0.65 and media >= 2.3:
        return "Ambas Marcam", probs["Ambas Marcam"]

    if media <= 2.0 and probs["Under 2.5"] >= 0.60:
        return "Under 2.5", probs["Under 2.5"]

    if probs["Over 1.5"] >= 0.65:
        return "Over 1.5", probs["Over 1.5"]

    return None, 0

# ================= ANALISAR =================
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

    if len(gols) < 3:
        print("[DEBUG] poucos jogos:", len(gols))
        return None

    total = len(gols)
    media = sum(gols) / total

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts / total
    }

    melhor, prob = escolher_mercado(media, probs)

    if not melhor or prob < 0.50:
        return None

    dt = parse_data(fixture["fixture"]["date"])
    if not dt:
        return None

    dt_local = dt - timedelta(hours=4)

    if prob >= 0.80:
        nivel = "🔥 FORTE"
    elif prob >= 0.70:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    return {
        "msg": f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}
📅 {dt_local.strftime("%d/%m")}
⏰ {dt_local.strftime("%H:%M")}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}

{nivel}""",
        "prob": prob,
        "fixture_id": fixture["fixture"]["id"],
        "kickoff": dt
    }

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.utcnow()
            candidatos = []

            data = req("https://v3.football.api-sports.io/fixtures", {
                "next": 100
            })

            if not data:
                time.sleep(AUTO_INTERVALO)
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

                if not res:
                    continue

                candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            if not candidatos:
                enviar("⚠️ AUTO: Nenhum jogo qualificado")
            else:
                for c in candidatos[:5]:
                    enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + c["msg"])
                    enviados_ids.add(c["fixture_id"])

        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        if "x" not in texto.lower():
            return "⚠️ Use: time x time"

        h, a = texto.lower().split("x")
        h = h.strip()
        a = a.strip()

        res = analisar(h, a)

        if not res:
            return "❌ Jogo não encontrado ou sem dados suficientes"

        return "🧠 MANUAL\n\n" + res["msg"]

    except:
        return "⚠️ Erro. Use: time x time"

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ONLINE (DEFINITIVO)")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id}
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
