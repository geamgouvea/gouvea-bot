import requests
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import unicodedata

# -------------------------------
# 🔑 CONFIGURAÇÕES
# -------------------------------
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

BASE_URL = "https://v3.football.api-sports.io/fixtures"

HEADERS = {
    "x-apisports-key": API_KEY
}

# -------------------------------
# 📩 Enviar mensagem (Telegram)
# -------------------------------
def enviar_mensagem(texto):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": texto
    }

    try:
        requests.post(url, data=payload)
    except:
        print("Erro ao enviar mensagem")

# -------------------------------
# 🔤 Normalizar texto
# -------------------------------
def normalizar(texto):
    return unicodedata.normalize('NFKD', texto)\
        .encode('ASCII', 'ignore')\
        .decode('ASCII')\
        .lower()

# -------------------------------
# 🔍 Similaridade
# -------------------------------
def parecido(a, b):
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()

# -------------------------------
# 🧠 Verifica se os times batem
# -------------------------------
def times_batem(home, away, t1, t2):
    return (
        (parecido(home, t1) > 0.6 or parecido(away, t1) > 0.6) and
        (parecido(home, t2) > 0.6 or parecido(away, t2) > 0.6)
    )

# -------------------------------
# 📅 Buscar jogos (-7 até +7 dias)
# -------------------------------
def buscar_jogos():
    jogos = []
    hoje = datetime.now()

    for i in range(-7, 8):
        data = (hoje + timedelta(days=i)).strftime("%Y-%m-%d")

        params = {"date": data}

        try:
            response = requests.get(BASE_URL, headers=HEADERS, params=params)

            if response.status_code != 200:
                continue

            dados = response.json()

            if "response" in dados:
                jogos.extend(dados["response"])

        except:
            continue

    return jogos

# -------------------------------
# 🎯 Encontrar jogo
# -------------------------------
def encontrar_jogo(time1, time2):
    jogos = buscar_jogos()

    melhor_jogo = None
    melhor_score = 0

    for jogo in jogos:
        home = jogo["teams"]["home"]["name"]
        away = jogo["teams"]["away"]["name"]

        score = max(
            parecido(home, time1),
            parecido(away, time1)
        ) + max(
            parecido(home, time2),
            parecido(away, time2)
        )

        if times_batem(home, away, time1, time2):
            if score > melhor_score:
                melhor_score = score
                melhor_jogo = jogo

    if melhor_jogo:
        return melhor_jogo

    return None

# -------------------------------
# ▶️ EXECUÇÃO PRINCIPAL
# -------------------------------
def executar(time1, time2):
    jogo = encontrar_jogo(time1, time2)

    if jogo:
        home = jogo["teams"]["home"]["name"]
        away = jogo["teams"]["away"]["name"]
        data = jogo["fixture"]["date"]
        status = jogo["fixture"]["status"]["long"]

        msg = (
            f"✅ Jogo encontrado!\n\n"
            f"{home} x {away}\n"
            f"📅 {data}\n"
            f"📊 Status: {status}"
        )

    else:
        msg = "❌ Não foi possível encontrar esse jogo.\nTente outro nome ou aguarde disponibilidade na API."

    enviar_mensagem(msg)

# -------------------------------
# 📌 TESTE MANUAL
# -------------------------------
if __name__ == "__main__":
    t1 = input("Time 1: ")
    t2 = input("Time 2: ")

    executar(t1, t2)
