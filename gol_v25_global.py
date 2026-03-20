import requests
import time
from datetime import datetime, timedelta, timezone

TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5

HEADERS = {"x-apisports-key": API_KEY}

ultimo_envio = {}
ultimo_auto = 0

# 🌍 LIGA
def nome_liga(liga, pais=""):
    liga = liga.lower()
    pais = pais.lower()

    if "brazil" in pais:
        if "serie a" in liga:
            return "🇧🇷 Campeonato Brasileiro – Série A"
        elif "serie b" in liga:
            return "🇧🇷 Campeonato Brasileiro – Série B"
        return "🇧🇷 Liga do Brasil"

    if "germany" in pais or "bundesliga" in liga:
        return "🇩🇪 Campeonato Alemão – Bundesliga"

    if "england" in pais:
        return "🏴 Premier League"

    if "spain" in pais:
        return "🇪🇸 La Liga"

    if "italy" in pais:
        return "🇮🇹 Serie A"

    if "france" in pais:
        return "🇫🇷 Ligue 1"

    return f"🌍 {liga.title()}"

# 🔍 TIME
def buscar_time(nome):
    try:
        url = "https://v3.football.api-sports.io/teams"
        res = requests.get(url, headers=HEADERS, params={"search": nome})
        data = res.json()
        if data["response"]:
            return data["response"][0]["team"]["id"]
    except:
        return None

# 📊 JOGOS
def pegar_jogos(team_id):
    try:
        url = f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10"
        res = requests.get(url, headers=HEADERS)
        return res.json().get("response", [])
    except:
        return []

# 🧠 ANÁLISE
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return "Over 1.5", 55, 5, 0.05

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

    if not gols:
        return "Over 1.5", 55, 5, 0.05

    total = len(gols)

    stats = {
        "Over 2.5": sum(1 for g in gols if g >= 3) / total,
        "Under 3.5": sum(1 for g in gols if g <= 3) / total,
        "Ambas marcam": btts / total
    }

    odds = {
        "Over 2.5": 1.80,
        "Under 3.5": 1.40,
        "Ambas marcam": 1.90
    }

    melhor = None
    melhor_score = -999

    for m, prob in stats.items():
        if prob < 0.60:
            continue

        ev = (prob * odds[m]) - 1

        if "Under" in m:
            ev -= 0.05

        if ev > melhor_score:
            melhor_score = ev
            melhor = m
            melhor_prob = prob
            melhor_ev = ev

    forca = 9 if melhor_prob >= 0.70 else 8 if melhor_prob >= 0.65 else 7

    return melhor, int(melhor_prob*100), forca, round(melhor_ev, 2)

# 📲 ENVIAR
def enviar(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg})

# 🔥 MULTIPLAS
def gerar_multiplas(jogos):
    msgs = []

    if len(jogos) >= 3:
        texto = "\n".join([f"{j['home']} x {j['away']} → {j['entrada']}" for j in jogos[:3]])
        msgs.append(f"GOUVEA BET\n\n🔥 MÚLTIPLA DO DIA (3 jogos)\n\n{texto}\n\n⭐ Confiança: Alta")

    if len(jogos) >= 4:
        texto = "\n".join([f"{j['home']} x {j['away']} → {j['entrada']}" for j in jogos[:4]])
        msgs.append(f"GOUVEA BET\n\n💣 MÚLTIPLA DO DIA (4 jogos)\n\n{texto}\n\n⭐ Confiança: Moderada")

    return msgs

# ⚽ BUSCAR JOGOS (PRÉ-JOGO)
def buscar_jogos():
    jogos = []
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    url = f"https://v3.football.api-sports.io/fixtures?date={hoje}"
    res = requests.get(url, headers=HEADERS).json()

    ligas_boas = ["brazil","england","spain","germany","italy","france"]

    agora = datetime.now(timezone.utc)

    for j in res.get("response", [])[:30]:

        status = j["fixture"]["status"]["short"]

        # 🛑 só pré-jogo
        if status != "NS":
            continue

        pais = j["league"]["country"].lower()

        if pais not in ligas_boas:
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))

        # ⏰ até 3 horas antes
        if (dt - agora).total_seconds() > 10800:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]
        liga = j["league"]["name"]

        dt -= timedelta(hours=4)

        jogos.append((home, away, liga, pais, dt.strftime("%d/%m"), dt.strftime("%H:%M")))

    return jogos

# 🤖 BOT
def main():
    global ultimo_auto
    last_update_id = None

    while True:
        try:
            # 🔥 AUTOMÁTICO
            if time.time() - ultimo_auto > 1800:
                jogos = buscar_jogos()
                filtrados = []

                for home, away, liga, pais, data_jogo, hora_jogo in jogos:
                    chave = f"{home}-{away}"

                    if chave in ultimo_envio:
                        continue

                    entrada, prob, forca, ev = analisar(home, away)

                    if forca < 8:
                        continue

                    msg = f"""GOUVEA BET

{home} x {away}

🏆 {nome_liga(liga, pais)}
📅 {data_jogo}
⏰ {hora_jogo}

🎯 Melhor entrada: {entrada}

📊 Prob: {prob}%
💰 EV: {ev}

⭐ Força: {forca}/10

✅ ENTRAR

🧠 Análise baseada em dados reais"""

                    enviar(msg)

                    filtrados.append({
                        "home": home,
                        "away": away,
                        "entrada": entrada
                    })

                    ultimo_envio[chave] = True

                for m in gerar_multiplas(filtrados):
                    enviar(m)

                ultimo_auto = time.time()

            # 🔍 MANUAL
            res = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                               params={"timeout":30,"offset":last_update_id}).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()

                if "x" not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")

                entrada, prob, forca, ev = analisar(home, away)

                msg = f"""GOUVEA BET

{home.title()} x {away.title()}

🎯 Melhor entrada: {entrada}

📊 Prob: {prob}%
💰 EV: {ev}

⭐ Força: {forca}/10

{"✅ ENTRAR" if forca >= 8 else "⚠️ MÉDIO"}"""

                enviar(msg)

        except Exception as e:
            print("ERRO:", e)

        time.sleep(2)

if __name__ == "__main__":
    main()
