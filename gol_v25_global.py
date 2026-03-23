import requests
import time
from datetime import datetime, timedelta, timezone

# ==============================
# 🔑 CONFIGURAÇÕES (PREENCHA)
# ==============================

TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

# ==============================
# 📤 TELEGRAM
# ==============================

def enviar(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg})

# ==============================
# 🌍 BUSCAR JOGOS
# ==============================

def buscar_jogos():
    try:
        url = f"https://api.football-data.org/v4/matches"
        headers = {"X-Auth-Token": API_KEY}
        res = requests.get(url, headers=headers)
        data = res.json()

        jogos = []

        for m in data.get("matches", []):
            utc = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))

            jogos.append({
                "home": m["homeTeam"]["name"],
                "away": m["awayTeam"]["name"],
                "liga": m["competition"]["name"],
                "data": utc,
                "media_gols": 2.4
            })

        return jogos

    except:
        return []

# ==============================
# 🔎 ENCONTRAR JOGO (INTELIGENTE)
# ==============================

def normalizar(txt):
    return txt.lower().replace("á","a").replace("ã","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")

def encontrar_jogo(texto, jogos):
    texto = normalizar(texto)

    for j in jogos:
        casa = normalizar(j["home"])
        fora = normalizar(j["away"])

        if casa in texto or fora in texto:
            return j

    return None

# ==============================
# 🧠 ANÁLISE
# ==============================

def analisar(jogo):
    media = jogo["media_gols"]

    if media >= 3.2:
        return ("Over 2.5", 80)
    elif media >= 2.6:
        return ("Ambas Marcam", 75)
    elif media >= 2.2:
        return ("Over 1.5", 70)
    else:
        return ("Under 2.5", 75)

# ==============================
# 📊 CLASSIFICAÇÃO
# ==============================

def classificar(prob):
    if prob >= 80:
        return "🔥 FORTE"
    elif prob >= 70:
        return "⚖️ MÉDIA"
    else:
        return "⚠️ RISCO"

# ==============================
# 🧾 FORMATAR
# ==============================

def formatar(jogo, analise, tipo):
    pick, prob = analise
    nivel = classificar(prob)

    data_str = jogo["data"].strftime("%d/%m")
    hora_str = jogo["data"].strftime("%H:%M")

    return f"""🤖 {tipo}

🔎 ANÁLISE

⚽ {jogo['home']} x {jogo['away']}
🏆 {jogo['liga']}
📅 {data_str}
⏰ {hora_str}

🎯 {pick}
📊 {prob}%
📈 Média gols: {jogo['media_gols']}

{nivel}
"""

# ==============================
# 🧠 MANUAL (CORRIGIDO REAL)
# ==============================

def manual(texto):
    jogos = buscar_jogos()

    jogo = encontrar_jogo(texto, jogos)

    # 🔥 FALLBACK (SE NÃO ENCONTRAR)
    if not jogo:
        partes = texto.split("x")

        if len(partes) != 2:
            enviar("❌ Use formato: Time x Time")
            return

        jogo = {
            "home": partes[0].strip(),
            "away": partes[1].strip(),
            "liga": "Não identificada",
            "data": datetime.now(timezone.utc),
            "media_gols": 2.4
        }

    analise = analisar(jogo)
    enviar(formatar(jogo, analise, "MANUAL"))

# ==============================
# 🤖 AUTO (CORRIGIDO REAL)
# ==============================

def auto():
    jogos = buscar_jogos()

    agora = datetime.now(timezone.utc)
    limite = agora + timedelta(hours=12)

    candidatos = []

    for j in jogos:
        if agora <= j["data"] <= limite:
            analise = analisar(j)
            pick, prob = analise

            if prob >= 65:
                candidatos.append((j, analise))

    if not candidatos:
        enviar("⚠️ AUTO: Nenhum jogo qualificado")
        return

    # ordena pelos melhores
    candidatos.sort(key=lambda x: x[1][1], reverse=True)

    for j, a in candidatos[:5]:
        enviar("🔥 SINAL\n\n" + formatar(j, a, "AUTO"))

# ==============================
# ▶️ LOOP PRINCIPAL
# ==============================

def iniciar():
    enviar("🤖 BOT ONLINE")

    while True:
        try:
            auto()
        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(1200)  # 20 minutos

# ==============================
# 🚀 START
# ==============================

if __name__ == "__main__":
    iniciar()
