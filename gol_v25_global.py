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

DIAS_BUSCA = 3  # busca jogos hoje + próximos dias
AUTO_INTERVALO = 1200  # 20 minutos

enviados_ids = set()
last_update_id = None

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    nome = nome.encode('ASCII', 'ignore').decode('ASCII')
    return nome

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

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)

    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
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

# ================= BUSCAR FIXTURE POR DATA =================
def buscar_fixture(home, away):
    home = normalizar(home)
    away = normalizar(away)

    for i in range(DIAS_BUSCA):
        data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

        data = req("https://v3.football.api-sports.io/fixtures", {
            "date": data_busca
        })

        if not data:
            continue

        for j in data.get("response", []):
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            if (home in h and away in a) or (home in a and away in h):
                return j

    return None

# ================= ANALISE =================
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return "❌ Times não encontrados"

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
        return "❌ Sem dados"

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

    # trava inteligência (evita Over 1.5 fixo)
    if melhor == "Over 1.5" and media < 2:
        melhor = "Under 2.5"
        prob = probs[melhor]

    fixture = buscar_fixture(home, away)

    liga = "Estimativa"
    data_txt = "--/--"
    hora = "--:--"

    if fixture:
        liga = fixture["league"]["name"]

        dt = datetime.fromisoformat(
            fixture["fixture"]["date"].replace("Z", "+00:00")
        )

        data_txt = dt.strftime("%d/%m")
        hora = dt.strftime("%H:%M")

    return f"""🔎 ANÁLISE

⚽ {home} x {away}
🏆 {liga}
📅 {data_txt}
⏰ {hora}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

# ================= AUTO =================
def auto():
    global enviados_ids

    while True:
        try:
            for i in range(DIAS_BUSCA):
                data_busca = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {
                    "date": data_busca
                })

                if not data:
                    continue

                enviados = 0

                for j in data.get("response", []):
                    fid = j["fixture"]["id"]

                    if fid in enviados_ids:
                        continue

                    h = j["teams"]["home"]["name"]
                    a = j["teams"]["away"]["name"]

                    res = analisar(h, a)

                    if "❌" in res:
                        continue

                    if "📊 7" in res or "📊 8" in res or "📊 9" in res:
                        enviar("🤖 AUTO\n\n🔥 SINAL PRO\n\n" + res)
                        enviados_ids.add(fid)
                        enviados += 1

                    if enviados >= 3:
                        break

        except:
            pass

        time.sleep(AUTO_INTERVALO)

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ATIVO COM SUCESSO")

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
                        enviar(analisar(h.strip(), a.strip()))
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
