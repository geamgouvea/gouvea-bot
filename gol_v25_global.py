import requests
import time
from datetime import datetime
import unicodedata
import joblib
import os
import numpy as np

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}
last_update_id = None
ultimo_auto = 0  # controle auto

# ================= START LOG =================
print("🚀 BOT INICIANDO...")

# ================= IA =================
modelo = None
if os.path.exists("modelo.pkl"):
    modelo = joblib.load("modelo.pkl")
    print("✅ IA carregada")
else:
    print("⚠️ IA não encontrada (usando fallback)")

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
        else:
            print("❌ API ERRO:", r.status_code)
    except Exception as e:
        print("❌ REQUEST ERRO:", e)
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        print("📤 ENVIANDO:", msg[:50])
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("❌ TELEGRAM ERRO:", e)

# ================= TIME =================
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

# ================= IA =================
def prever_ia(media_gols, media_sofridos, btts):
    if modelo:
        try:
            entrada = np.array([[media_gols, media_sofridos, btts]])
            return modelo.predict_proba(entrada)[0][1]
        except:
            pass

    # fallback
    score = (media_gols * 0.6) + (btts * 0.4) - (media_sofridos * 0.3)
    return max(0.1, min(score / 3, 0.9))

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
            return "❌ Sem dados"

        total = len(gols)

        media_gols = sum(gols) / total
        media_sofridos = media_gols / 2
        btts_rate = btts / total

        prob = prever_ia(media_gols, media_sofridos, btts_rate)

        if prob >= 0.65:
            melhor = "Over 2.5"
        elif prob >= 0.55:
            melhor = "Over 1.5"
        elif prob <= 0.40:
            melhor = "Under 2.5"
        else:
            melhor = "Ambas marcam"

        return f"""🔍 ANÁLISE IA

⚽ {home} x {away}

🎯 {melhor}
📊 {int(prob*100)}%"""

    except Exception as e:
        print("❌ ANALISE ERRO:", e)
        return "❌ Erro na análise"

# ================= AUTO =================
def rodar_auto():
    print("🤖 AUTO EXECUTANDO...")

    data = req("https://v3.football.api-sports.io/fixtures", {"next": 10})

    if not data:
        return

    enviados = 0

    for j in data.get("response", []):
        try:
            h = j["teams"]["home"]["name"]
            a = j["teams"]["away"]["name"]

            res = analisar(h, a)

            if "📊" in res:
                enviar("🔥 AUTO\n\n" + res)
                enviados += 1

            if enviados >= 2:
                break
        except:
            continue

# ================= MAIN =================
def main():
    global last_update_id, ultimo_auto

    enviar("🤖 BOT ELITE ATIVO")

    while True:
        try:
            print("🔄 LOOP RODANDO...")

            # ================= TELEGRAM =================
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id}
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "").lower()

                print("📩 RECEBIDO:", texto)

                if "x" in texto:
                    try:
                        h, a = texto.split("x")
                        enviar(analisar(h.strip(), a.strip()))
                    except:
                        enviar("⚠️ Use: time x time")

            # ================= AUTO =================
            if time.time() - ultimo_auto > 1200:
                rodar_auto()
                ultimo_auto = time.time()

        except Exception as e:
            print("❌ LOOP ERRO:", e)

        time.sleep(5)

# ================= START =================
if __name__ == "__main__":
    main()
