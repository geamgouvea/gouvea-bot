import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

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

    data = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    nome_curto = nome.split()[0]
    data = safe_request("https://v3.football.api-sports.io/teams", {"search": nome_curto})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    return None

# ================= PEGAR JOGOS =================
def pegar_jogos(team_id):
    data = safe_request("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    if data:
        return data.get("response", [])
    return []

# ================= ODDS =================
def pegar_odds(fixture_id):
    data = safe_request("https://v3.football.api-sports.io/odds", {
        "fixture": fixture_id
    })

    odds = {}

    if not data or not data.get("response"):
        return odds

    try:
        for book in data["response"][0]["bookmakers"]:
            for bet in book["bets"]:
                if bet["name"] == "Goals Over/Under":
                    for v in bet["values"]:
                        if "Over 2.5" in v["value"]:
                            odds["over25"] = float(v["odd"])
                        if "Under 2.5" in v["value"]:
                            odds["under25"] = float(v["odd"])
                        if "Over 1.5" in v["value"]:
                            odds["over15"] = float(v["odd"])

                if bet["name"] == "Both Teams Score":
                    for v in bet["values"]:
                        if v["value"] == "Yes":
                            odds["btts"] = float(v["odd"])
    except:
        pass

    return odds

# ================= ANALISE =================
def analisar(fixture):
    try:
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        liga = fixture["league"]["name"]
        data_jogo = fixture["fixture"]["date"]

        horario = datetime.fromisoformat(data_jogo.replace("Z","+00:00")) - timedelta(hours=4)
        horario = horario.strftime("%H:%M")

        fixture_id = fixture["fixture"]["id"]

        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return None

        jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

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

        if len(gols) < 5:
            return None

        total = len(gols)

        prob_over25 = sum(g >= 3 for g in gols) / total
        prob_under25 = sum(g <= 2 for g in gols) / total
        prob_btts = btts / total
        prob_over15 = sum(g >= 2 for g in gols) / total

        opcoes = [
            ("Over 2.5", prob_over25),
            ("Under 2.5", prob_under25),
            ("Ambas marcam", prob_btts),
            ("Over 1.5", prob_over15)
        ]

        melhor = max(opcoes, key=lambda x: x[1])
        prob = int(melhor[1] * 100)

        return {
            "texto": f"""⚽ {home} x {away}
🏆 {liga}
⏰ {horario}

🎯 {melhor[0]}
📊 {prob}%""",
            "prob": prob,
            "id": fixture_id
        }

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

# ================= AUTOMÁTICO =================
def sistema_automatico():
    global jogos_enviados

    while True:
        jogos = buscar_jogos()
        picks = []

        for j in jogos:
            r = analisar(j)

            if r and r["prob"] >= 65 and r["id"] not in jogos_enviados:
                picks.append(r)

        picks.sort(key=lambda x: x["prob"], reverse=True)

        enviados = 0

        for p in picks:
            enviar("🔥 SINAL AUTOMÁTICO\n\n" + p["texto"])
            jogos_enviados.add(p["id"])
            enviados += 1

            if enviados >= 5:
                break

        time.sleep(1200)

# ================= MULTIPLA =================
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for j in jogos:
        r = analisar(j)
        if r and r["prob"] >= 65:
            picks.append(r)

    picks.sort(key=lambda x: x["prob"], reverse=True)

    if len(picks) < qtd:
        return "⚠️ Poucas oportunidades agora"

    msg = "🔥 MÚLTIPLA ELITE\n\n"

    for i, p in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣\n{p['texto']}\n\n"

    return msg

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ELITE ATIVO 🔥")

    while True:
        try:
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id},
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "").lower().strip()

                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(gerar_multipla(qtd))

                elif "x" in texto:
                    jogos = buscar_jogos()

                    for j in jogos:
                        home = normalizar_nome(j["teams"]["home"]["name"])
                        away = normalizar_nome(j["teams"]["away"]["name"])

                        if home in texto or away in texto:
                            r = analisar(j)
                            if r:
                                enviar("🔍 ANÁLISE\n\n" + r["texto"])
                                break
                    else:
                        enviar("⚠️ Jogo não encontrado nas próximas 12h")

                else:
                    enviar("⚠️ Use:\n- time x time\n- multipla 2")

        except:
            pass

        time.sleep(5)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=sistema_automatico).start()
    main()
