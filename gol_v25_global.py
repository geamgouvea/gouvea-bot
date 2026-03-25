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

# ================= DATA =================
def parse_data(data_str):
    try:
        return datetime.fromisoformat(data_str.replace("Z", "+00:00")).replace(tzinfo=None)
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
    except:
        pass
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away):
    home_n = normalizar(home)
    away_n = normalizar(away)

    melhor = None
    melhor_score = 0

    for i in range(10):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            score1 = (similar(home_n, h) + similar(away_n, a)) / 2
            score2 = (similar(home_n, a) + similar(away_n, h)) / 2

            final = max(score1, score2)

            if home_n.split()[0] in h or away_n.split()[0] in a:
                final += 0.10

            if final > melhor_score:
                melhor_score = final
                melhor = j

    if melhor_score < 0.55:
        return None

    return melhor

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ESCOLHA MERCADO =================
def escolher_mercado(media, probs):

    if media >= 3.0 and probs["Over 2.5"] >= 0.65:
        return "Over 2.5", probs["Over 2.5"]

    if probs["Ambas Marcam"] >= 0.70:
        return "Ambas Marcam", probs["Ambas Marcam"]

    if media <= 2.2 and probs["Under 2.5"] >= 0.65:
        return "Under 2.5", probs["Under 2.5"]

    if probs["Over 1.5"] >= 0.72:
        return "Over 1.5", probs["Over 1.5"]

    melhor = max(probs, key=probs.get)
    return melhor, probs[melhor]

# ================= ANALISE =================
def analisar(home, away):
    try:
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

        if len(gols) < 4:
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

        dt = parse_data(fixture["fixture"]["date"])

        if dt:
            dt_local = dt - timedelta(hours=4)
            data_txt = dt_local.strftime("%d/%m")
            hora_txt = dt_local.strftime("%H:%M")
        else:
            data_txt = "-"
            hora_txt = "-"

        liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

        if prob >= 0.82:
            nivel = "🔥 FORTE"
        elif prob >= 0.72:
            nivel = "⚖️ MÉDIA"
        else:
            nivel = "⚠️ RISCO"

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

    except:
        return None

# ================= MANUAL =================
def manual(texto):
    try:
        partes = re.split(r"x|vs|versus", texto.lower())

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        h = partes[0].strip()
        a = partes[1].strip()

        res = analisar(h, a)

        if not res:
            return "❌ Não foi possível analisar o jogo"

        return "🧠 MANUAL\n\n" + res["msg"]

    except:
        return "⚠️ Erro no comando"

# ================= AUTO COM MULTIPLA =================
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

                    if not res:
                        continue

                    if res["prob"] >= 0.70:
                        candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            # MULTIPLA 7
            if len(candidatos) >= 7:
                msg = "🎯 MÚLTIPLA (7 JOGOS)\n\n"

                for i, c in enumerate(candidatos[:7], 1):
                    linha = c["msg"].split("\n")[2]
                    mercado = c["msg"].split("🎯")[1].split("\n")[0]
                    msg += f"{i}. {linha} → {mercado}\n"

                enviar(msg)

            # MULTIPLA 10
            if len(candidatos) >= 10:
                msg = "\n💣 MÚLTIPLA BINGO (10 JOGOS)\n\n"

                for i, c in enumerate(candidatos[:10], 1):
                    linha = c["msg"].split("\n")[2]
                    mercado = c["msg"].split("🎯")[1].split("\n")[0]
                    msg += f"{i}. {linha} → {mercado}\n"

                enviar(msg)

            if len(candidatos) == 0:
                enviar("⚠️ AUTO: Nenhum jogo qualificado")

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
                params={"offset": last_update_id or 0},
                timeout=10
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
    threading.Thread(target=auto, daemon=True).start()
    main()
