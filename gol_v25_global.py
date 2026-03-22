import requests
import time
from datetime import datetime, timedelta
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None

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
    except:
        pass
    return None

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)

    mapa = {
        "real": "Real Madrid",
        "real madrid": "Real Madrid",
        "atletico": "Atletico Madrid",
        "atletico madrid": "Atletico Madrid",
        "inter": "Inter",
        "inter milao": "Inter",
        "inter de milao": "Inter",
        "milan": "AC Milan",
        "psg": "Paris Saint Germain",
    }

    nome = mapa.get(nome, nome)

    data = req("https://v3.football.api-sports.io/teams", {"search": nome})

    if data and data["response"]:
        return data["response"][0]["team"]["id"]

    return None

# ================= BUSCAR JOGO (CORRIGIDO) =================
def buscar_fixture(home, away):
    hoje = datetime.utcnow().strftime("%Y-%m-%d")

    # tenta hoje
    data = req("https://v3.football.api-sports.io/fixtures", {"date": hoje})

    if data:
        for j in data["response"]:
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            if home in h and away in a:
                return j
            if away in h and home in a:
                return j

    # fallback próximos
    data = req("https://v3.football.api-sports.io/fixtures", {"next": 50})

    if data:
        for j in data["response"]:
            h = normalizar(j["teams"]["home"]["name"])
            a = normalizar(j["teams"]["away"]["name"])

            if home in h and away in a:
                return j
            if away in h and home in a:
                return j

    return None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data["response"] if data else []

# ================= ANALISE =================
def analisar(home, away):
    home_n = normalizar(home)
    away_n = normalizar(away)

    fixture = buscar_fixture(home_n, away_n)

    if not fixture:
        return "❌ Jogo não encontrado"

    home_nome = fixture["teams"]["home"]["name"]
    away_nome = fixture["teams"]["away"]["name"]
    liga = fixture["league"]["name"]
    data_jogo = fixture["fixture"]["date"]

    dt = datetime.fromisoformat(data_jogo.replace("Z","+00:00"))
    hora = dt.strftime("%H:%M")

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

    p_over15 = sum(g >= 2 for g in gols) / total
    p_over25 = sum(g >= 3 for g in gols) / total
    p_under25 = sum(g <= 2 for g in gols) / total
    p_btts = btts / total

    opcoes = {
        "Over 1.5": p_over15,
        "Over 2.5": p_over25,
        "Under 2.5": p_under25,
        "Ambas marcam": p_btts
    }

    melhor = max(opcoes, key=opcoes.get)
    prob = int(opcoes[melhor] * 100)

    return f"""🔍 ANÁLISE

⚽ {home_nome} x {away_nome}
🏆 {liga}
⏰ {hora}

🎯 Melhor entrada: {melhor}
📊 Probabilidade: {prob}%"""

# ================= MULTIPLA =================
def multipla(qtd=3):
    data = req("https://v3.football.api-sports.io/fixtures", {"next": 30})

    if not data:
        return "❌ Erro API"

    jogos = []

    for j in data["response"]:
        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        res = analisar(home, away)

        if "Probabilidade" in res:
            prob = int(res.split("Probabilidade: ")[1].replace("%",""))
            if prob >= 65:
                jogos.append((prob, res))

    jogos.sort(reverse=True)

    if len(jogos) < 2:
        return "⚠️ Poucas oportunidades agora"

    msg = "🔥 MÚLTIPLA\n\n"

    for i, (_, r) in enumerate(jogos[:qtd], 1):
        msg += f"{i}️⃣\n{r}\n\n"

    return msg

# ================= TELEGRAM =================
def enviar(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ELITE ATIVO 🔥")

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

                if "multipla" in texto:
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(multipla(qtd))

                elif "x" in texto:
                    try:
                        h, a = texto.split("x")
                        enviar(analisar(h.strip(), a.strip()))
                    except:
                        enviar("⚠️ Use: time x time")

                else:
                    enviar("⚠️ Use:\n- time x time\n- multipla 2")

        except Exception as e:
            print("Erro:", e)

        time.sleep(5)

if __name__ == "__main__":
    main()
