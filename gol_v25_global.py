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

DIAS_BUSCA = 5
AUTO_INTERVALO = 1200  # 20 minutos

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

# ================= COMPARAÇÃO INTELIGENTE =================
def comparar_times(input_nome, api_nome):
    input_nome = normalizar(input_nome)
    api_nome = normalizar(api_nome)

    palavras_input = input_nome.split()
    palavras_api = api_nome.split()

    matches = sum(1 for p in palavras_input if p in palavras_api)

    return matches >= 1

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)
    busca = nome.split()[0]

    data = req("https://v3.football.api-sports.io/teams", {"search": busca})

    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    return None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

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

            if (comparar_times(home, h) and comparar_times(away, a)) or \
               (comparar_times(home, a) and comparar_times(away, h)):
                return j

    return None

# ================= ANALISE =================
def analisar(home, away):
    fixture = buscar_fixture(home, away)

    if not fixture:
        return "❌ Jogo não encontrado para os próximos dias"

    home_api = fixture["teams"]["home"]["name"]
    away_api = fixture["teams"]["away"]["name"]

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

    if not gols:
        return "❌ Sem dados suficientes"

    total_jogos = len(gols)
    media = sum(gols) / total_jogos

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total_jogos,
        "Over 2.5": sum(g >= 3 for g in gols) / total_jogos,
        "Under 2.5": sum(g <= 2 for g in gols) / total_jogos,
        "Ambas Marcam": btts / total_jogos
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    # filtro profissional
    if melhor == "Over 1.5" and (prob < 0.8 or media < 2.8):
        return None
    if melhor == "Over 2.5" and (prob < 0.72 or media < 2.4):
        return None
    if melhor == "Under 2.5" and (prob < 0.72 or media > 2.2):
        return None
    if melhor == "Ambas Marcam" and prob < 0.65:
        return None

    # data e hora
    dt = datetime.fromisoformat(
        fixture["fixture"]["date"].replace("Z", "+00:00")
    )

    # converter UTC → Brasil (-4h)
    dt = dt - timedelta(hours=4)

    # NÃO ENVIAR jogo já iniciado
    if dt <= datetime.utcnow() - timedelta(hours=4):
        return None

    data_txt = dt.strftime("%d/%m")
    hora = dt.strftime("%H:%M")
    liga = fixture["league"]["name"]

    return f"""🔎 ANÁLISE

⚽ {home_api} x {away_api}
🏆 {liga}
📅 {data_txt}
⏰ {hora}

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

                    if not res:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL ELITE\n\n" + res)

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
                            enviar("❌ Sem valor ou jogo inválido")
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
