# =========================
# IMPORTS
# =========================
import requests
import time
from datetime import datetime, timedelta

# =========================
# CONFIGURAÇÕES DO USUÁRIO
# =========================

TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
modo_auto = True
janela_horas = 12
intervalo_execucao = 1800  # 30 minutos

# API de jogos (exemplo - você pode trocar)
API_URL = "https://api.football-data.org/v4/matches"
API_KEY = "SUA_API_KEY_AQUI"

HEADERS = {"X-Auth-Token": API_KEY}

# =========================
# TELEGRAM
# =========================

def enviar_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg
    }
    requests.post(url, data=payload)

# =========================
# NORMALIZAÇÃO
# =========================

def normalizar(texto):
    texto = texto.lower().strip()

    substituicoes = {
        "á":"a","ã":"a","â":"a","ä":"a",
        "é":"e","ê":"e",
        "í":"i",
        "ó":"o","ô":"o","õ":"o",
        "ú":"u",
        "ç":"c"
    }

    for k,v in substituicoes.items():
        texto = texto.replace(k,v)

    remover = ["fc","sc","ac","club","clube","de","da","do"]
    for r in remover:
        texto = texto.replace(" " + r, "")

    return texto.replace(".", "").replace("-", "").strip()

# =========================
# DATA
# =========================

def agora_utc():
    return datetime.utcnow()

def parse_data(data_str):
    try:
        return datetime.fromisoformat(data_str.replace("Z","+00:00")).replace(tzinfo=None)
    except:
        return None

# =========================
# BUSCAR JOGOS NA API
# =========================

def carregar_jogos():
    try:
        resposta = requests.get(API_URL, headers=HEADERS)
        dados = resposta.json()

        jogos = []

        for m in dados.get("matches", []):
            jogos.append({
                "home": m["homeTeam"]["name"],
                "away": m["awayTeam"]["name"],
                "liga": m["competition"]["name"],
                "data": m["utcDate"],
                "media_gols": 2.4,  # fallback (API não traz direto)
                "probabilidade": 70
            })

        return jogos

    except:
        return []

# =========================
# BUSCA INTELIGENTE
# =========================

def encontrar_jogo(texto, jogos):
    entrada = normalizar(texto)

    for jogo in jogos:
        casa = normalizar(jogo["home"])
        fora = normalizar(jogo["away"])

        if casa in entrada and fora in entrada:
            return jogo

    for jogo in jogos:
        nome = normalizar(jogo["home"] + " " + jogo["away"])
        if entrada in nome or nome in entrada:
            return jogo

    return None

# =========================
# FILTRO
# =========================

def jogo_valido(jogo):
    liga = normalizar(jogo["liga"])

    bloqueios = ["u20","u19","u18","women","feminino","reserves","ii"]

    for b in bloqueios:
        if b in liga:
            return False

    return True

# =========================
# ANÁLISE
# =========================

def analisar(jogo):
    media = jogo.get("media_gols", 2.4)
    prob = jogo.get("probabilidade", 70)

    if media >= 3.3:
        mercado = "Over 2.5"
    elif media >= 2.6:
        mercado = "Ambas Marcam"
    elif media >= 2.2:
        mercado = "Over 1.5"
    else:
        mercado = "Under 2.5"

    if prob >= 80:
        nivel = "🔥 FORTE"
    elif prob >= 70:
        nivel = "⚖️ MÉDIA"
    else:
        nivel = "⚠️ RISCO"

    return {
        "mercado": mercado,
        "prob": prob,
        "media": media,
        "nivel": nivel
    }

# =========================
# FORMATAÇÃO
# =========================

def formatar(jogo, analise, modo):
    data = jogo["data"]

    return f"""
🤖 {modo}

🔥 SINAL

🔎 ANÁLISE

⚽ {jogo['home']} x {jogo['away']}
🏆 {jogo['liga']}
📅 {data[:10]}
⏰ {data[11:16]}

🎯 {analise['mercado']}
📊 {analise['prob']}%
📈 Média gols: {analise['media']}

{analise['nivel']}
"""

# =========================
# MANUAL
# =========================

def manual(texto):
    jogos = carregar_jogos()

    jogo = encontrar_jogo(texto, jogos)

    if not jogo:
        enviar_telegram("❌ Jogo não encontrado")
        return

    analise = analisar(jogo)

    enviar_telegram(formatar(jogo, analise, "MANUAL"))

# =========================
# AUTOMÁTICO
# =========================

def auto():
    while True:
        try:
            jogos = carregar_jogos()
            agora = agora_utc()

            lista = []

            for jogo in jogos:
                data_jogo = parse_data(jogo["data"])
                if not data_jogo:
                    continue

                diff = (data_jogo - agora).total_seconds() / 3600

                if 0 <= diff <= janela_horas:

                    if not jogo_valido(jogo):
                        continue

                    analise = analisar(jogo)

                    if analise["prob"] >= 65:
                        lista.append((jogo, analise))

            lista = sorted(lista, key=lambda x: x[1]["prob"], reverse=True)[:5]

            if lista:
                for jogo, analise in lista:
                    enviar_telegram(formatar(jogo, analise, "AUTO"))
            else:
                enviar_telegram("⚠️ AUTO: Nenhum jogo qualificado")

        except Exception as e:
            enviar_telegram(f"❌ ERRO AUTO: {str(e)}")

        time.sleep(intervalo_execucao)

# =========================
# START
# =========================

def start():
    enviar_telegram("🤖 BOT ONLINE")

    if modo_auto:
        auto()

# =========================
# EXECUÇÃO
# =========================

if __name__ == "__main__":
    start()
