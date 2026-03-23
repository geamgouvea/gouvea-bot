import requests
import time
import threading
from datetime import datetime
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}
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
    except Exception as e:
        print("ERRO REQUEST:", e)
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("ERRO TELEGRAM:", e)

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)

    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    nome_curto = nome.split()[0]
    data = req("https://v3.football.api-sports.io/teams", {"search": nome_curto})
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
    home_n = normalizar(home)
    away_n = normalizar(away)

    data = req("https://v3.football.api-sports.io/fixtures", {"next": 200})

    if not data:
        return None

    melhor = None
    score_max = 0

    for j in data.get("response", []):
        h = normalizar(j["teams"]["home"]["name"])
        a = normalizar(j["teams"]["away"]["name"])

        score = 0
        if home_n in h or h in home_n:
            score += 1
        if away_n in a or a in away_n:
            score += 1
        if home_n in a or away_n in h:
            score += 1

        if score > score_max:
            score_max = score
            melhor = j

    if score_max >= 2:
        return melhor

    return None

# ================= ANALISE =================
def analisar(home, away):
    try:
        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return "❌ Times não encontrados"

        jogos = historico(home_id) + historico(away_id)

        gols = []
        btts = 0

        for j in jogos:
            try:
                g1 = j["goals"]["home"]
                g2 = j["goals"]["away"]

                if g1 is None or g2 is None:
                    continue

                total = g1 + g2
                gols.append(total)

                if g1 > 0 and g2 > 0:
                    btts += 1
            except:
                continue

        if not gols:
            return "❌ Sem dados suficientes"

        total = len(gols)

        probs = {
            "Over 1.5": sum(g >= 2 for g in gols) / total,
            "Over 2.5": sum(g >= 3 for g in gols) / total,
            "Under 2.5": sum(g <= 2 for g in gols) / total,
            "Ambas marcam": btts / total
        }

        melhor = max(probs, key=probs.get)
        prob = int(probs[melhor] * 100)
        media = round(sum(gols)/len(gols), 2)

        fixture = buscar_fixture(home, away)

        # SE NÃO ACHAR JOGO → NÃO TRAVA MAIS
        if fixture:
            liga = fixture["league"]["name"]

            dt = datetime.fromisoformat(
                fixture["fixture"]["date"].replace("Z","+00:00")
            )
            hora = dt.strftime("%H:%M")

            home_nome = fixture["teams"]["home"]["name"]
            away_nome = fixture["teams"]["away"]["name"]
        else:
            liga = "Estimativa"
            hora = "--:--"
            home_nome = home
            away_nome = away

        return f"""🔥 SINAL PRO

⚽ {home_nome} x {away_nome}
🏆 {liga}
⏰ {hora}

🎯 {melhor}
📊 {prob}%
📈 Média gols: {media}
"""

    except Exception as e:
        print("ERRO ANALISE:", e)
        return "❌ Erro ao analisar"

# ================= AUTO =================
def auto():
    while True:
        try:
            print("🤖 AUTO RODANDO...")

            data = req("https://v3.football.api-sports.io/fixtures", {"next": 50})

            if data:
                enviados = 0

                for j in data.get("response", []):
                    home = j["teams"]["home"]["name"]
                    away = j["teams"]["away"]["name"]

                    liga = j["league"]["name"]

                    dt = datetime.fromisoformat(
                        j["fixture"]["date"].replace("Z","+00:00")
                    )
                    hora = dt.strftime("%H:%M")

                    res = analisar(home, away)

                    if "📊" in res:
                        prob = int(res.split("📊 ")[1].split("%")[0])

                        if prob >= 75:
                            mensagem = f"""🤖 AUTO

🔥 SINAL PRO

⚽ {home} x {away}
🏆 {liga}
⏰ {hora}

{res.split("🎯")[1]}"""

                            enviar(mensagem)
                            enviados += 1

                    if enviados >= 3:
                        break

        except Exception as e:
            print("ERRO AUTO:", e)

        time.sleep(1200)

# ================= MAIN =================
def main():
    global last_update_id

    print("🚀 BOT INICIADO")
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

        except Exception as e:
            print("ERRO MAIN:", e)

        time.sleep(5)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
