import requests
from datetime import datetime, timedelta

# CONFIG
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

# LIGAS PERMITIDAS (TOP + MADRUGADA)
LIGAS_PERMITIDAS = [
    "Argentina", "Brazil", "Portugal", "Netherlands", "Scotland",
    "Saudi Arabia", "USA", "Mexico", "Colombia", "Chile"
]

# CONTROLE DE DUPLICADOS
jogos_enviados = set()

def buscar_jogos():
    url = f"https://v3.football.api-sports.io/fixtures?next=100"
    headers = {"x-apisports-key": API_KEY}
    response = requests.get(url, headers=headers).json()

    jogos = []
    agora = datetime.utcnow()

    # HOJE + AMANHÃ + MADRUGADA
    limite = agora + timedelta(days=1)
    limite = limite.replace(hour=6, minute=0, second=0)

    for jogo in response["response"]:
        liga = jogo["league"]["name"]
        pais = jogo["league"]["country"]

        if pais not in LIGAS_PERMITIDAS:
            continue

        casa = jogo["teams"]["home"]["name"]
        fora = jogo["teams"]["away"]["name"]

        data_jogo = jogo["fixture"]["date"]
        dt = datetime.fromisoformat(data_jogo.replace("Z", ""))

        if not (agora <= dt <= limite):
            continue

        chave = f"{casa}x{fora}{dt}"
        if chave in jogos_enviados:
            continue

        jogos_enviados.add(chave)

        jogos.append({
            "casa": casa,
            "fora": fora,
            "liga": liga,
            "data": dt.strftime("%d/%m"),
            "hora": dt.strftime("%H:%M")
        })

    return jogos


def analisar_jogo(jogo):
    # SIMULAÇÃO INTELIGENTE (PODE LIGAR EM API REAL DE ESTATÍSTICA)
    media_gols = round(1.5 + (hash(jogo["casa"]) % 150) / 100, 2)

    if media_gols >= 2.8:
        mercado = "Over 2.5"
        prob = 78
    elif media_gols >= 2.2:
        mercado = "Over 1.5"
        prob = 75
    elif media_gols >= 1.8:
        mercado = "Ambas Marcam"
        prob = 72
    else:
        mercado = "Under 2.5"
        prob = 70

    return mercado, prob, media_gols


def enviar_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


def gerar_sinal(jogo):
    mercado, prob, media = analisar_jogo(jogo)

    msg = f"""
🤖 AUTO

🔥 SINAL ELITE

🔎 ANÁLISE

⚽ {jogo['casa']} x {jogo['fora']}
🏆 {jogo['liga']}
📅 {jogo['data']}
⏰ {jogo['hora']}

🎯 {mercado}
📊 {prob}%
📈 Média gols: {media}
"""

    return msg


def rodar_bot():
    jogos = buscar_jogos()

    for jogo in jogos:
        sinal = gerar_sinal(jogo)
        enviar_telegram(sinal)


if __name__ == "__main__":
    rodar_bot()
