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

DIAS_BUSCA = 3
AUTO_INTERVALO = 1200

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

# ================= BUSCAR FIXTURE =================
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

    # evitar over 1.5 fraco
    if melhor == "Over 1.5" and (prob < 0.8 or media < 2.8):
        melhor = "Over 2.5" if probs["Over 2.5"] > 0.7 else "Ambas Marcam"
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

        # converter UTC → Brasil (-4h)
        dt = dt - timedelta(hours=4)

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

    ligas_permitidas = [
        "brazil", "argentina", "portugal",
        "netherlands", "scotland", "saudi",
        "spain", "germany", "italy", "france"
    ]

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

                    liga = j["league"]["name"].lower()

                    # filtro liga
                    if not any(l in liga for l in ligas_permitidas):
                        continue

                    h = j["teams"]["home"]["name"]
                    a = j["teams"]["away"]["name"]

                    # bloquear sub / feminino
                    if "u21" in h.lower() or "u21" in a.lower():
                        continue
                    if "women" in h.lower() or "women" in a.lower():
                        continue

                    res = analisar(h, a)

                    if "❌" in res:
                        continue

                    try:
                        prob = int(res.split("📊 ")[1].split("%")[0])
                        media = float(res.split("Média gols: ")[1])
                        mercado = res.split("🎯 ")[1].split("\n")[0]
                    except:
                        continue

                    # filtro profissional
                    if mercado == "Over 1.5" and (prob < 80 or media < 2.8):
                        continue
                    if mercado == "Over 2.5" and (prob < 72 or media < 2.4):
                        continue
                    if mercado == "Under 2.5" and (prob < 72 or media > 2.2):
                        continue
                    if mercado == "Ambas Marcam" and prob < 70:
                        continue

                    enviar("🤖 AUTO\n\n🔥 SINAL ELITE\n\n" + res)

                    enviados_ids.add(fid)
                    enviados += 1

                    if enviados >= 3:
                        break

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
