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

INTERVALO_AUTO = 1200  # 20 min
ULTIMOS_ENVIADOS = set()
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
        else:
            print("API ERRO:", r.status_code)
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

# ================= ANALISE SIMPLES =================
def analisar_fixture(jogo):
    try:
        gols = []
        btts = 0

        for f in jogo["fixture"]["status"],:
            pass

        # pegar estatística via histórico simples
        stats = req("https://v3.football.api-sports.io/fixtures", {
            "team": jogo["teams"]["home"]["id"],
            "last": 5
        })

        if not stats:
            return None

        for j in stats.get("response", []):
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            if g1 is None or g2 is None:
                continue

            total = g1 + g2
            gols.append(total)

            if g1 > 0 and g2 > 0:
                btts += 1

        if not gols:
            return None

        media = sum(gols) / len(gols)

        if media >= 2.8:
            mercado = "Over 2.5"
            prob = 78
        elif media >= 2.2:
            mercado = "Over 1.5"
            prob = 74
        elif media >= 1.6:
            mercado = "Ambas Marcam"
            prob = 70
        else:
            mercado = "Under 2.5"
            prob = 72

        dt = datetime.fromisoformat(jogo["fixture"]["date"].replace("Z","+00:00")) - timedelta(hours=4)

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
    while True:
        try:
            print("AUTO RODANDO...")
            enviados = 0

            hoje = datetime.utcnow().strftime("%Y-%m-%d")

            data = req("https://v3.football.api-sports.io/fixtures", {"date": hoje})

            if not data:
                time.sleep(INTERVALO_AUTO)
                continue

            for j in data.get("response", []):
                fid = j["fixture"]["id"]

                if fid in ULTIMOS_ENVIADOS:
                    continue

                pais = j["league"]["country"].lower()

                if pais not in ["brazil","argentina","portugal","netherlands","scotland","saudi arabia"]:
                    continue

                nome = j["teams"]["home"]["name"].lower()

                if "u21" in nome or "women" in nome:
                    continue

                analise = analisar_fixture(j)

                if not analise:
                    continue

                enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + analise)

                ULTIMOS_ENVIADOS.add(fid)
                enviados += 1

                if enviados >= 3:
                    break

            if enviados == 0:
                enviar("⚠️ Sem jogos bons agora")

        except Exception as e:
            print("ERRO AUTO:", e)

        time.sleep(INTERVALO_AUTO)

# ================= MANUAL =================
def buscar_jogo_manual(texto):
    data = req("https://v3.football.api-sports.io/fixtures", {"next": 100})

    if not data:
        return None

    t1, t2 = texto.split("x")
    t1 = normalizar(t1)
    t2 = normalizar(t2)

    for j in data.get("response", []):
        h = normalizar(j["teams"]["home"]["name"])
        a = normalizar(j["teams"]["away"]["name"])

        if (t1 in h and t2 in a) or (t1 in a and t2 in h):
            return j

    return None

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
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text","").lower()

                if "x" in texto:
                    jogo = buscar_jogo_manual(texto)

                    if not jogo:
                        enviar("❌ Jogo não encontrado")
                        continue

                    analise = analisar_fixture(jogo)

                    if analise:
                        enviar("🧠 MANUAL\n\n" + analise)
                    else:
                        enviar("❌ Erro na análise")

                else:
                    enviar("⚠️ Use: time x time")

        except Exception as e:
            print("ERRO MAIN:", e)

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto, daemon=True).start()
    main()
