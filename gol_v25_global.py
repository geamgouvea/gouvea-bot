import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

DIAS_BUSCA = 7
AUTO_INTERVALO = 1200  # 20 min

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

# ================= COMPARAR TIMES =================
def match_time(nome_input, nome_api):
    nome_input = normalizar(nome_input)
    nome_api = normalizar(nome_api)

    return (
        nome_input in nome_api or
        nome_api in nome_input
    )

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away):
    for i in range(DIAS_BUSCA):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_busca
        })

        if not data:
            continue

        for j in data.get("response", []):
            h = j["teams"]["home"]["name"]
            a = j["teams"]["away"]["name"]

            if (match_time(home, h) and match_time(away, a)) or \
               (match_time(home, a) and match_time(away, h)):
                return j

    return None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ANALISAR =================
def analisar(home, away):
    fixture = buscar_fixture(home, away)

    if not fixture:
        return "❌ Jogo não encontrado (7 dias)"

    # dados reais
    home_api = fixture["teams"]["home"]["name"]
    away_api = fixture["teams"]["away"]["name"]
    home_id = fixture["teams"]["home"]["id"]
    away_id = fixture["teams"]["away"]["id"]

    # horário
    dt = datetime.fromisoformat(
        fixture["fixture"]["date"].replace("Z", "+00:00")
    )
    dt = dt - timedelta(hours=4)

    # BLOQUEAR jogo iniciado
    if dt <= datetime.utcnow() - timedelta(hours=4):
        return "❌ Jogo já iniciado"

    # histórico
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
        return "❌ Poucos dados"

    media = sum(gols) / len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / len(gols),
        "Over 2.5": sum(g >= 3 for g in gols) / len(gols),
        "Under 2.5": sum(g <= 2 for g in gols) / len(gols),
        "Ambas Marcam": btts / len(gols)
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    # filtro MAIS REALISTA (corrigido)
    if melhor == "Over 1.5" and prob < 0.75:
        return None
    if melhor == "Over 2.5" and prob < 0.70:
        return None
    if melhor == "Under 2.5" and prob < 0.70:
        return None
    if melhor == "Ambas Marcam" and prob < 0.60:
        return None

    return f"""🔎 ANÁLISE

⚽ {home_api} x {away_api}
🏆 {fixture["league"]["name"]}
📅 {dt.strftime("%d/%m")}
⏰ {dt.strftime("%H:%M")}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

# ================= AUTO =================
def auto():
    while True:
        try:
            enviados = 0

            for i in range(DIAS_BUSCA):
                data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {
                    "date": data_busca
                })

                if not data:
                    continue

                for j in data.get("response", []):
                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    h = j["teams"]["home"]["name"]
                    a = j["teams"]["away"]["name"]

                    res = analisar(h, a)

                    if not res or "❌" in res:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + res)

                    enviados_ids.add(fid)
                    enviados += 1

                    if enviados >= 5:
                        break

                if enviados >= 5:
                    break

        except:
            pass

        time.sleep(AUTO_INTERVALO)

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ONLINE")

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

                texto = u["message"].get("text", "").lower()

                if "x" in texto:
                    try:
                        h, a = texto.split("x")
                        res = analisar(h.strip(), a.strip())

                        if not res:
                            enviar("❌ Sem valor")
                        else:
                            enviar("🧠 MANUAL\n\n" + res)

                    except:
                        enviar("⚠️ Use: time x time")
                else:
                    enviar("⚠️ Use: time x time")

        except:
            pass

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
