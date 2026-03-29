import requests
from datetime import datetime, timedelta, timezone
import time
import unicodedata
import difflib
import threading

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

BASE_URL = "https://api-football-v1.p.rapidapi.com/v3/fixtures"

HEADERS = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}

last_update_id = None

# ================= UTILS =================
def normalizar(texto):
    texto = texto.lower().strip()
    texto = unicodedata.normalize('NFD', texto)
    return texto.encode('ascii', 'ignore').decode('utf-8')

def similar(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    jogos = []

    for i in range(10):
        data = (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d")

        r = requests.get(BASE_URL, headers=HEADERS, params={"date": data})

        if r.status_code == 200:
            jogos.extend(r.json()["response"])

    return jogos

# ================= ENCONTRAR JOGO =================
def encontrar_jogo(texto, jogos):
    texto = normalizar(texto)

    melhor = None
    melhor_score = 0

    for j in jogos:
        casa = normalizar(j['teams']['home']['name'])
        fora = normalizar(j['teams']['away']['name'])

        combinado = f"{casa} x {fora}"

        score = similar(texto, combinado)

        if score > melhor_score:
            melhor_score = score
            melhor = j

    if melhor_score > 0.45:
        return melhor

    return None

# ================= PROBABILIDADES =================
def calcular_probs(media):
    if media >= 3:
        return {"Over 2.5": 85, "Ambas Marcam": 80, "Over 1.5": 95}
    elif media >= 2:
        return {"Over 1.5": 80, "Ambas Marcam": 65, "Under 2.5": 60}
    else:
        return {"Under 2.5": 80, "Under 1.5": 65}

def escolher(probs):
    return max(probs.items(), key=lambda x: x[1])

def nivel(prob):
    if prob >= 90:
        return "🔥 FORTE"
    elif prob >= 75:
        return "⚖️ MÉDIA"
    else:
        return "⚠️ RISCO"

# ================= ANALISAR =================
def analisar(jogo):
    try:
        casa = jogo['teams']['home']['name']
        fora = jogo['teams']['away']['name']
        liga = jogo['league']['name']

        dt = datetime.fromisoformat(jogo['fixture']['date'].replace("Z", "+00:00"))

        data = dt.strftime("%d/%m")
        hora = dt.strftime("%H:%M")

        media = 2.5

        probs = calcular_probs(media)
        entrada, prob = escolher(probs)

        return f"""🔎 ANÁLISE

⚽ {casa} x {fora}
🏆 {liga}
📅 {data}
⏰ {hora}

🎯 {entrada}
📊 {prob}%
📈 Média gols: {media}

{nivel(prob)}"""

    except Exception as e:
        return f"❌ Erro: {e}"

# ================= MANUAL =================
def manual(texto):
    jogos = buscar_jogos()
    jogo = encontrar_jogo(texto, jogos)

    if not jogo:
        return "❌ Não foi possível encontrar o jogo"

    return "🧠 MANUAL\n\n" + analisar(jogo)

# ================= AUTO =================
def auto():
    enviados = set()

    while True:
        try:
            jogos = buscar_jogos()

            for j in jogos:
                fid = j['fixture']['id']

                if fid in enviados:
                    continue

                msg = analisar(j)

                enviar("🤖 AUTO\n\n🔥 SINAL\n\n" + msg)

                enviados.add(fid)

                time.sleep(8)

        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(600)

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ONLINE")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id or 0}
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "")

                resposta = manual(texto)

                enviar(resposta)

        except:
            pass

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
