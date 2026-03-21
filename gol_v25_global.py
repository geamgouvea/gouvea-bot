import requests
import time
import threading
from datetime import datetime, timedelta, timezone
from difflib import get_close_matches

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

# ================= LIGA FORMATADA =================
def nome_liga(liga):
    liga = liga.lower()

    if "brazil" in liga:
        return "🇧🇷 Brasileirão"
    elif "england" in liga:
        return "🏴 Premier League"
    elif "spain" in liga:
        return "🇪🇸 La Liga"
    elif "italy" in liga:
        return "🇮🇹 Serie A"
    elif "germany" in liga:
        return "🇩🇪 Bundesliga"
    elif "france" in liga:
        return "🇫🇷 Ligue 1"
    elif "japan" in liga:
        return "🇯🇵 J-League"
    elif "korea" in liga:
        return "🇰🇷 K League"
    else:
        return f"🌍 {liga.title()}"

# ================= REQUEST =================
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# ================= BUSCAR TIME =================
def buscar_time(nome):
    data = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]
    return None

# ================= HISTÓRICO =================
def pegar_jogos(team_id):
    data = safe_request("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    if data:
        return data.get("response", [])
    return []

# ================= ANÁLISE =================
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return "Over 1.5", 60, 0.10, 6

    jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

    gols = []
    btts = 0

    for j in jogos:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            if g1 is None or g2 is None:
                continue

            gols.append(g1 + g2)

            if g1 > 0 and g2 > 0:
                btts += 1
        except:
            continue

    if len(gols) < 5:
        return "Over 1.5", 60, 0.10, 6

    total = len(gols)

    over15 = sum(g >= 2 for g in gols) / total
    over25 = sum(g >= 3 for g in gols) / total
    ambas = btts / total
    under35 = sum(g <= 3 for g in gols) / total

    if over15 >= 0.60:
        return "Over 1.5", int(over15*100), 0.15, 7

    elif over25 >= 0.50:
        return "Over 2.5", int(over25*100), 0.20, 7

    elif ambas >= 0.50:
        return "Ambas marcam", int(ambas*100), 0.15, 7

    elif under35 >= 0.60:
        return "Under 3.5", int(under35*100), 0.12, 6

    else:
        return "Jogo equilibrado", 55, 0.05, 5

# ================= MÚLTIPLA =================
def gerar_multipla(qtd=2):
    data = safe_request("https://v3.football.api-sports.io/fixtures", {"next": 40})

    if not data:
        return "❌ Erro ao buscar jogos"

    picks = []

    for j in data.get("response", []):
        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        entrada, prob, ev, forca = analisar(home, away)

        if forca >= 6:
            picks.append((home, away, entrada, prob))

    picks.sort(key=lambda x: x[3], reverse=True)

    if not picks:
        return "❌ Nenhuma múltipla encontrada"

    msg = "🔥 MÚLTIPLA DO DIA\n\n"

    for i, (h, a, e, p) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🎯 {e} ({p}%)\n\n"

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

def ler(offset=None):
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset

    res = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        params=params
    ).json()

    return res.get("result", [])

# ================= AUTOMÁTICO =================
def modo_automatico():
    while True:
        try:
            data = safe_request("https://v3.football.api-sports.io/fixtures", {"next": 40})

            enviados = 0

            for j in data.get("response", []):
                if enviados >= 2:
                    break

                home = j["teams"]["home"]["name"]
                away = j["teams"]["away"]["name"]
                liga = j["league"]["name"]
                hora = j["fixture"]["date"]

                entrada, prob, ev, forca = analisar(home, away)

                if forca >= 6 and prob >= 60:
                    dt = datetime.fromisoformat(hora.replace("Z","+00:00"))

                    msg = f"""🔥 SINAL AUTOMÁTICO

⚽ {home} x {away}
🏆 {nome_liga(liga)}

🎯 {entrada}
📊 {prob}%
⭐ {forca}/10"""

                    enviar(msg)
                    enviados += 1

            time.sleep(1800)

        except Exception as e:
            print("Erro auto:", e)
            time.sleep(60)

# ================= BOT =================
def main():
    enviar("🤖 Gouvea Bet Inteligente Online!")

    last = None

    while True:
        updates = ler(last)

        for u in updates:
            last = u["update_id"] + 1

            try:
                texto = u["message"]["text"].lower().strip()

                # 🔥 MÚLTIPLA
                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 2
                    enviar(gerar_multipla(qtd))
                    continue

                # 🔍 ANÁLISE
                if " x " not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")

                entrada, prob, ev, forca = analisar(home, away)

                enviar(f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 {entrada}
📊 {prob}%
⭐ {forca}/10""")

            except Exception as e:
                print("Erro:", e)

        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=modo_automatico).start()
    main()
