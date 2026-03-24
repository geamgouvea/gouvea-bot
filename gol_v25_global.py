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

AUTO_INTERVALO = 1800
JANELA_MIN = 10
JANELA_MAX = 720

enviados_ids = set()
last_update_id = None

# ================= DATA =================
def parse_data(data_str):
    try:
        dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    except:
        return None

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

        elif r.status_code == 429:
            time.sleep(2)

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

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(5):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score = (similar(home_n, h) + similar(away_n, a)) / 2
            score_inv = (similar(home_n, a) + similar(away_n, h)) / 2

            final = max(score, score_inv)

            if final > melhor_score:
                melhor_score = final
                melhor = j

    if melhor_score < 0.60:
        return None

    return melhor

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ESCOLHA =================
def escolher_mercado(media, probs):

    if media >= 3.0 and probs["Over 2.5"] >= 0.65:
        return "Over 2.5", probs["Over 2.5"]

    if probs["Ambas Marcam"] >= 0.70:
        return "Ambas Marcam", probs["Ambas Marcam"]

    if media <= 2.1:
        return "Under 2.5", probs["Under 2.5"]

    return "Over 1.5", probs["Over 1.5"]

# ================= ANALISE =================
def analisar(home, away, forcar=False):

    fixture = buscar_fixture(home, away)

    if not fixture:
        if forcar:
            return f"""🧠 MANUAL

🔎 ANÁLISE

⚽ {home} x {away}
🏆 Liga não identificada
📅 Data não informada
⏰ Horário não informado

🎯 Over 1.5
📊 65%
📈 Média gols: 2.2

⚠️ RISCO"""
        return None

    home_id = fixture["teams"]["home"]["id"]
    away_id = fixture["teams"]["away"]["id"]

    jogos = historico(home_id) + historico(away_id)

    gols = []
    btts = 0

    for j in jogos:
        g1 = j["goals"]["home"]
        g2 = j["goals"]["away"]

        if not isinstance(g1, int) or not isinstance(g2, int):
            continue

        gols.append(g1 + g2)

        if g1 > 0 and g2 > 0:
            btts += 1

    if len(gols) < 4:
        media = 2.2
        prob = 0.65
        melhor = "Over 1.5"
    else:
        total = len(gols)
        media = sum(gols) / total

        probs = {
            "Over 1.5": sum(g >= 2 for g in gols) / total,
            "Over 2.5": sum(g >= 3 for g in gols) / total,
            "Under 2.5": sum(g <= 2 for g in gols) / total,
            "Ambas Marcam": btts / total
        }

        melhor, prob = escolher_mercado(media, probs)

    if not forcar and prob < 0.65:
        return None

    if prob >= 0.85:
        nivel = "🔥 FORTE"
    elif prob >= 0.70:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

    dt = parse_data(fixture["fixture"]["date"])
    if dt:
        dt_local = dt - timedelta(hours=4)
        data_txt = dt_local.strftime("%d/%m")
        hora_txt = dt_local.strftime("%H:%M")
    else:
        data_txt = "Data não informada"
        hora_txt = "Horário não informado"

    return {
        "msg": f"""🔎 ANÁLISE

⚽ {fixture["teams"]["home"]["name"]} x {fixture["teams"]["away"]["name"]}
🏆 {liga}
📅 {data_txt}
⏰ {hora_txt}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}

{nivel}""",
        "prob": prob,
        "fixture_id": fixture["fixture"]["id"]
    }

# ================= AUTO =================
def auto():
    while True:
        try:
            agora = datetime.utcnow()
            candidatos = []

            for i in range(3):
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

                    if not res or not isinstance(res, dict) or "prob" not in res:
                        continue

                    candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            enviados = 0

            for c in candidatos[:5]:
                enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + c["msg"])
                enviados_ids.add(c["fixture_id"])
                enviados += 1

            if enviados == 0:
                enviar("⚠️ AUTO: Nenhum jogo qualificado")

        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MANUAL =================
def manual(texto):
    try:
        texto = texto.lower().replace(" vs ", " x ").replace("-", " x ")

        if "x" not in texto:
            return None

        partes = texto.split("x")

        if len(partes) != 2:
            return None

        h = partes[0].strip()
        a = partes[1].strip()

        res = analisar(h, a, forcar=True)

        return res if isinstance(res, str) else "🧠 MANUAL\n\n" + res["msg"]

    except:
        return None

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ONLINE")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id, "timeout": 10}
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "")

                if "x" in texto.lower() or "vs" in texto.lower():
                    resposta = manual(texto)
                    if resposta:
                        enviar(resposta)

        except:
            pass

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
