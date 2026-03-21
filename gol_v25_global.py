import requests
import time
import difflib
from datetime import datetime, timedelta, timezone

# 🔐 CONFIGURE AQUI
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None

# 🔥 REQUEST SEGURO
def safe_request(url, params=None):
    try:
        return requests.get(url, headers=HEADERS, params=params, timeout=10)
    except:
        return None

# 🧠 APELIDOS
apelidos = {
    "sevilha": "Sevilla",
    "valencia": "Valencia CF",
    "atlético mineiro": "Atletico Mineiro",
    "atletico mineiro": "Atletico Mineiro",
    "man city": "Manchester City",
    "man united": "Manchester United",
    "inter": "Inter Milan",
    "milan": "AC Milan",
    "psg": "Paris Saint Germain",
    "real": "Real Madrid",
    "barça": "Barcelona",
    "juve": "Juventus",
}

def corrigir_nome(nome):
    nome = nome.lower().strip()
    for apelido, oficial in apelidos.items():
        if apelido in nome:
            return oficial
    return nome.title()

# 🔍 BUSCA INTELIGENTE
def buscar_time(nome):
    try:
        nome_corrigido = corrigir_nome(nome)
        res = safe_request("https://v3.football.api-sports.io/teams", {"search": nome_corrigido})
        if not res:
            return None, []

        data = res.json()

        if not data["response"]:
            return None, []

        melhor_id = None
        melhor_score = 0
        sugestoes = []

        for t in data["response"]:
            nome_api = t["team"]["name"]
            score = difflib.SequenceMatcher(None, nome_corrigido.lower(), nome_api.lower()).ratio()

            sugestoes.append(nome_api)

            if score > melhor_score:
                melhor_score = score
                melhor_id = t["team"]["id"]

        if melhor_score < 0.5:
            return None, sugestoes[:3]

        return melhor_id, []

    except:
        return None, []

# 📊 JOGOS
def pegar_jogos(team_id):
    try:
        res = safe_request(f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10")
        if not res:
            return []
        return res.json().get("response", [])
    except:
        return []

# 🧠 ANÁLISE
def analisar(home, away):
    home_id, sug_home = buscar_time(home)
    away_id, sug_away = buscar_time(away)

    if not home_id or not away_id:
        return None, sug_home, sug_away

    jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

    gols = []
    btts = 0

    for j in jogos:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]
            total = g1 + g2
            gols.append(total)
            if g1 > 0 and g2 > 0:
                btts += 1
        except:
            continue

    if len(gols) < 8:
        return None, [], []

    total = len(gols)

    stats = {
        "Over 1.5": sum(1 for g in gols if g >= 2) / total,
        "Over 2.5": sum(1 for g in gols if g >= 3) / total,
        "Ambas marcam": btts / total,
        "Under 3.5": sum(1 for g in gols if g <= 3) / total
    }

    odds = {
        "Over 1.5": 1.30,
        "Over 2.5": 1.80,
        "Ambas marcam": 1.90,
        "Under 3.5": 1.40
    }

    melhor = None
    melhor_score = -999

    for m, prob in stats.items():
        ev = (prob * odds[m]) - 1
        score = ev + prob

        if score > melhor_score:
            melhor_score = score
            melhor = m
            melhor_prob = prob
            melhor_ev = ev

    if not melhor:
        return None, [], []

    forca = 9 if melhor_prob >= 0.75 else 8 if melhor_prob >= 0.65 else 7

    return (melhor, int(melhor_prob*100), forca, round(melhor_ev, 2)), [], []

# 📲 ENVIAR
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

# 🔥 MULTIPLA
def gerar_multipla(qtd=3):
    jogos = []
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    res = safe_request(f"https://v3.football.api-sports.io/fixtures?date={hoje}")
    if not res:
        return "❌ Erro ao buscar jogos"

    data = res.json()

    for j in data.get("response", [])[:30]:
        if j["fixture"]["status"]["short"] != "NS":
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        resultado, _, _ = analisar(home, away)
        if not resultado:
            continue

        entrada, prob, _, _ = resultado

        if prob < 70:
            continue

        jogos.append((home, away, entrada, prob))

    jogos.sort(key=lambda x: x[3], reverse=True)

    selecionados = jogos[:qtd]

    if not selecionados:
        return "❌ Nenhuma múltipla encontrada"

    msg = "🔥 GOUVEA BET – MÚLTIPLA\n\n"

    for i, (home, away, entrada, prob) in enumerate(selecionados, 1):
        msg += f"{i}️⃣ {home} x {away}\n🎯 {entrada} ({prob}%)\n\n"

    return msg

# 🤖 BOT
def main():
    global last_update_id

    print("BOT ONLINE...")

    while True:
        try:
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 30, "offset": last_update_id}
            )

            data = res.json() if res.status_code == 200 else {}

            for u in data.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()
                print("Recebi:", texto)

                # MULTIPLA
                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(gerar_multipla(qtd))
                    continue

                # INDIVIDUAL
                if " x " not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                partes = texto.split(" x ")
                if len(partes) != 2:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = partes

                resultado, sug_home, sug_away = analisar(home, away)

                if not resultado:
                    msg = "❌ Não encontrei esse jogo\n\n"

                    if sug_home:
                        msg += f"Sugestões casa: {', '.join(sug_home)}\n"
                    if sug_away:
                        msg += f"Sugestões fora: {', '.join(sug_away)}"

                    enviar(msg)
                    continue

                entrada, prob, forca, ev = resultado

                status = "✅ ENTRAR" if forca >= 8 else "⚠️ OBSERVAR"

                msg = f"""GOUVEA BET

{corrigir_nome(home)} x {corrigir_nome(away)}

🎯 Melhor entrada: {entrada}

📊 Prob: {prob}%
💰 EV: {ev}

⭐ Força: {forca}/10

{status}

🧠 Análise baseada em dados reais"""

                enviar(msg)

        except Exception as e:
            print("ERRO:", e)

        time.sleep(3)

if __name__ == "__main__":
    main()
