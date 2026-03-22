import requests
import time
from datetime import datetime
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

MODO_TESTE = True
INTERVALO = 60 if MODO_TESTE else 1800

last_update_id = None
jogos_enviados = set()

# ================= NORMALIZAR =================
def normalizar_nome(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    nome = nome.encode('ASCII', 'ignore').decode('ASCII')
    return nome

# ================= REQUEST =================
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar_nome(nome)

    data = safe_request(
        "https://v3.football.api-sports.io/teams",
        {"search": nome}
    )

    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    return None

# ================= HISTÓRICO =================
def pegar_jogos(team_id):
    data = safe_request("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= LIGA =================
def liga_valida(nome):
    nome = nome.lower()

    boas = ["premier", "la liga", "serie a", "bundesliga", "ligue 1", "brasileiro"]
    ruins = ["friendly", "amistoso", "youth", "u17", "u20", "u23", "women"]

    if any(r in nome for r in ruins):
        return False

    return any(b in nome for b in boas)

# ================= ANALISE =================
def analisar(fixture):
    try:
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        liga = fixture["league"]["name"]
        horario = fixture["fixture"]["date"]
        fixture_id = fixture["fixture"]["id"]

        if not liga_valida(liga):
            return None

        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return None

        jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

        gols = []
        btts = 0

        for j in jogos:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            if g1 is None or g2 is None:
                continue

            gols.append(g1 + g2)

            if g1 > 0 and g2 > 0:
                btts += 1

        if len(gols) < 8:
            return None

        total = len(gols)

        prob_over25 = sum(g >= 3 for g in gols) / total
        prob_btts = btts / total
        prob_over15 = min(0.90, prob_over25 + 0.20)

        opcoes = [
            ("Over 2.5", prob_over25),
            ("Ambas marcam", prob_btts),
            ("Over 1.5", prob_over15)
        ]

        melhor = max(opcoes, key=lambda x: x[1])

        prob = int(melhor[1] * 100)

        # 🔥 AJUSTES PROFISSIONAIS
        prob = min(prob, 85)

        if prob < 60:
            return None

        forca = 10 if prob >= 80 else 9 if prob >= 72 else 8 if prob >= 65 else 7

        horario_formatado = datetime.fromisoformat(
            horario.replace("Z","+00:00")
        ).strftime("%d/%m %H:%M")

        return home, away, melhor[0], prob, forca, liga, horario_formatado, fixture_id

    except:
        return None

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = safe_request("https://v3.football.api-sports.io/fixtures", {"next": 30})
    if not data:
        return []

    jogos = []
    agora = datetime.utcnow()

    for j in data.get("response", []):
        try:
            if j["fixture"]["status"]["short"] != "NS":
                continue

            dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
            diff = (dt - agora).total_seconds()

            if 0 < diff < 43200:
                jogos.append(j)
        except:
            continue

    return jogos

# ================= ENVIO =================
def enviar(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

# ================= AUTOMÁTICO =================
def enviar_sinais_automaticos():
    global jogos_enviados

    jogos = buscar_jogos()
    sinais = []

    for j in jogos:
        resultado = analisar(j)

        if resultado:
            home, away, entrada, prob, forca, liga, horario, fixture_id = resultado

            if fixture_id not in jogos_enviados:
                sinais.append(resultado)

    sinais.sort(key=lambda x: x[3], reverse=True)
    sinais = sinais[:5]

    if not sinais:
        return

    msg = "🔥 SINAIS AUTOMÁTICOS\n\n"

    for s in sinais:
        home, away, entrada, prob, forca, liga, horario, fixture_id = s

        msg += f"""⚽ {home} x {away}
🏆 {liga}
⏰ {horario}
🎯 {entrada}
📊 {prob}%
⭐ {forca}/10

"""

        jogos_enviados.add(fixture_id)

    enviar(msg)

# ================= MANUAL =================
def analise_manual(texto):
    try:
        home, away = texto.split("x")

        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return "❌ Times não encontrados"

        jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

        gols = [
            j["goals"]["home"] + j["goals"]["away"]
            for j in jogos
            if j["goals"]["home"] is not None and j["goals"]["away"] is not None
        ]

        if len(gols) < 8:
            return "⚠️ Poucos dados"

        prob = int((sum(g >= 3 for g in gols) / len(gols)) * 100)
        prob = min(prob, 85)

        if prob < 60:
            return "❌ Jogo sem valor"

        return f"""🔍 ANÁLISE MANUAL

⚽ {home.strip()} x {away.strip()}

🎯 Over 2.5
📊 {prob}%"""

    except:
        return "Erro"

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 Gouvea Bet PRO ATUALIZADO 🔥")

    ultimo_envio = 0

    while True:
        try:
            agora = time.time()

            if agora - ultimo_envio > INTERVALO:
                enviar_sinais_automaticos()
                ultimo_envio = agora

            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "").lower()

                if "x" in texto:
                    enviar(analise_manual(texto))

        except:
            pass

        time.sleep(5)

if __name__ == "__main__":
    main()
