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

INTERVALO_AUTO = 1200
ULTIMOS_ENVIADOS = {}
ENVIADOS_HASH = set()
last_update_id = None

# ================= UTIL =================
def normalizar(txt):
    txt = txt.lower().strip()
    txt = unicodedata.normalize('NFKD', txt)
    return txt.encode('ASCII', 'ignore').decode('ASCII')

def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("REQUEST ERRO:", e)
    return None

def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print("TELEGRAM ERRO:", e)

# ================= ANALISE =================
def analisar_fixture(jogo):
    try:
        gols = []

        for team_id in [jogo["teams"]["home"]["id"], jogo["teams"]["away"]["id"]]:
            stats = req("https://v3.football.api-sports.io/fixtures", {
                "team": team_id,
                "last": 5
            })

            if not stats:
                continue

            for j in stats.get("response", []):
                g1 = j["goals"]["home"]
                g2 = j["goals"]["away"]

                if g1 is None or g2 is None:
                    continue

                gols.append(g1 + g2)

        if len(gols) < 6:
            return None

        media = sum(gols) / len(gols)

        if media >= 2.8:
            mercado, prob = "Over 2.5", 78
        elif media >= 2.2:
            mercado, prob = "Over 1.5", 74
        elif media >= 1.6:
            mercado, prob = "Ambas Marcam", 70
        else:
            mercado, prob = "Under 2.5", 72

        dt = datetime.fromisoformat(
            jogo["fixture"]["date"].replace("Z","+00:00")
        ) - timedelta(hours=4)

        return f"""🔎 ANÁLISE

⚽ {jogo['teams']['home']['name']} x {jogo['teams']['away']['name']}
🏆 {jogo['league']['name']}
📅 {dt.strftime("%d/%m")}
⏰ {dt.strftime("%H:%M")}

🎯 {mercado}
📊 {prob}%
📈 Média gols: {round(media,2)}"""

    except Exception as e:
        print("ERRO ANALISE:", e)
        return None

# ================= AUTO =================
def auto():
    global ULTIMOS_ENVIADOS, ENVIADOS_HASH

    while True:
        try:
            print("AUTO RODANDO...")
            enviados = 0

            agora = datetime.utcnow()
            hoje = agora.strftime("%Y-%m-%d")

            data = req("https://v3.football.api-sports.io/fixtures", {"date": hoje})

            if not data:
                time.sleep(INTERVALO_AUTO)
                continue

            # limpar cache
            ULTIMOS_ENVIADOS = {
                k:v for k,v in ULTIMOS_ENVIADOS.items()
                if (agora - v).total_seconds() < 21600
            }

            for j in data.get("response", []):
                time.sleep(0.2)

                fid = j["fixture"]["id"]

                if fid in ULTIMOS_ENVIADOS:
                    continue

                status = j["fixture"]["status"]["short"]
                if status != "NS":
                    continue

                data_jogo = datetime.fromisoformat(
                    j["fixture"]["date"].replace("Z","+00:00")
                )

                if data_jogo > agora + timedelta(hours=12):
                    continue

                pais = j["league"]["country"].lower()
                if pais not in [
                    "brazil","argentina","portugal",
                    "netherlands","scotland","saudi arabia"
                ]:
                    continue

                h = j["teams"]["home"]["name"].lower()
                a = j["teams"]["away"]["name"].lower()

                if any(x in h or x in a for x in ["u21","u23","women","w"]):
                    continue

                analise = analisar_fixture(j)

                if not analise:
                    continue

                hash_msg = hash(analise)
                if hash_msg in ENVIADOS_HASH:
                    continue

                enviar("🤖 AUTO\n\n🔥 SINAL ELITE\n\n" + analise)

                ULTIMOS_ENVIADOS[fid] = agora
                ENVIADOS_HASH.add(hash_msg)

                enviados += 1

                if enviados >= 3:
                    break

            if enviados == 0:
                print("Sem sinais")

        except Exception as e:
            print("ERRO AUTO:", e)

        time.sleep(INTERVALO_AUTO)

# ================= MANUAL =================
def buscar_jogo_manual(texto):
    data = req("https://v3.football.api-sports.io/fixtures", {"next": 100})

    if not data:
        return None

    try:
        t1, t2 = texto.split("x")
    except:
        return None

    t1 = normalizar(t1)
    t2 = normalizar(t2)

    melhor = None
    score_max = 0

    for j in data.get("response", []):
        h = normalizar(j["teams"]["home"]["name"])
        a = normalizar(j["teams"]["away"]["name"])

        score = 0
        if t1 in h: score += 1
        if t2 in a: score += 1
        if t1 in a: score += 1
        if t2 in h: score += 1

        if score > score_max:
            score_max = score
            melhor = j

    return melhor if score_max >= 3 else None

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ONLINE")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id},
                timeout=10
            )

            if r.status_code != 200:
                time.sleep(3)
                continue

            data = r.json()

            for u in data.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text","").lower().strip()

                if "x" not in texto:
                    continue

                jogo = buscar_jogo_manual(texto)

                if not jogo:
                    enviar("❌ Jogo não encontrado")
                    continue

                analise = analisar_fixture(jogo)

                if analise:
                    enviar("🧠 MANUAL\n\n" + analise)

        except Exception as e:
            print("ERRO MAIN:", e)

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
