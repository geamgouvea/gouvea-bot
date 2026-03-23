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
enviados_ids = set()

# ================= LIGAS =================
LIGAS_TOP = [
    "brazil","argentina",
    "england","spain","italy","germany","france",
    "netherlands","portugal","scotland","saudi-arabia"
]

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
        print("ERRO API:", e)
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

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)
    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]
    return None

# ================= ANALISE INTELIGENTE =================
def analisar_jogo(home_id, away_id):
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
        return None

    total = len(gols)

    probs = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Ambas Marcam": btts / total
    }

    melhor = max(probs, key=probs.get)
    prob = probs[melhor]

    media = sum(gols) / total

    return melhor, prob, media

# ================= FILTRO PROFISSIONAL =================
def filtro_ruim(home, away, liga_nome):
    home = home.lower()
    away = away.lower()
    liga_nome = liga_nome.lower()

    if any(x in home for x in ["u21","u23","reserves","b"]) or \
       any(x in away for x in ["u21","u23","reserves","b"]):
        return True

    if any(x in liga_nome for x in ["women","femin","fem","w"]):
        return True

    if any(x in liga_nome for x in ["division 2","segunda","reserve"]):
        return True

    return False

# ================= AUTO =================
def auto():
    global enviados_ids

    while True:
        try:
            print("AUTO rodando...")

            data = req("https://v3.football.api-sports.io/fixtures", {"next": 50})

            if data:
                enviados = 0

                for j in data["response"]:
                    fixture_id = j["fixture"]["id"]

                    if fixture_id in enviados_ids:
                        continue

                    liga_nome = j["league"]["name"]
                    pais = j["league"]["country"].lower()

                    if not any(p in pais for p in LIGAS_TOP):
                        continue

                    home = j["teams"]["home"]["name"]
                    away = j["teams"]["away"]["name"]

                    if filtro_ruim(home, away, liga_nome):
                        continue

                    dt = datetime.fromisoformat(
                        j["fixture"]["date"].replace("Z","+00:00")
                    )
                    hora = dt.strftime("%H:%M")

                    home_id = buscar_time(home)
                    away_id = buscar_time(away)

                    if not home_id or not away_id:
                        continue

                    analise = analisar_jogo(home_id, away_id)

                    if not analise:
                        continue

                    melhor, prob, media = analise

                    if prob < 0.65:
                        continue

                    msg = f"""🔥 SINAL PRO

⚽ {home} x {away}
🏆 {liga_nome}
⏰ {hora}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

                    enviar("🤖 AUTO\n\n" + msg)

                    enviados_ids.add(fixture_id)
                    enviados += 1

                    if enviados >= 3:
                        break

        except Exception as e:
            print("ERRO AUTO:", e)

        time.sleep(1200)

# ================= MANUAL =================
def analisar_manual(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return "❌ Times não encontrados"

    analise = analisar_jogo(home_id, away_id)

    if not analise:
        return "❌ Sem dados"

    melhor, prob, media = analise

    return f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

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
                        enviar(analisar_manual(h.strip(), a.strip()))
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
