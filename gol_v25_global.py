import requests
import time
from datetime import datetime

# 🔐 CONFIG
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None

# 🔥 REQUEST
def safe_request(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r
    except:
        return None
    return None

# 🧠 PERÍODO
def periodo_atual():
    h = datetime.now().hour
    if 0 <= h < 6: return "madrugada"
    if 6 <= h < 12: return "manha"
    if 12 <= h < 18: return "tarde"
    return "noite"

# ⏱️ NOVO LIMITE (CORRIGIDO)
def limite_horas():
    p = periodo_atual()
    if p == "madrugada": return 28800   # 8h (ANTES ERA 6)
    if p == "manha": return 43200       # 12h
    if p == "tarde": return 43200       # 12h
    if p == "noite": return 32400       # 9h

# 🏆 FILTRO DE LIGAS (MAIS ABERTO)
def nome_liga(liga, pais):
    liga = liga.lower()
    pais = pais.lower()

    ligas_validas = [
        "brazil","argentina","england","spain","italy","germany",
        "portugal","netherlands","belgium","mexico",
        "japan","korea","china","australia","usa"
    ]

    if any(l in pais for l in ligas_validas):
        return f"{liga.title()} ({pais.title()})"

    return None

# 🔍 TIME
def buscar_time(nome):
    res = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
    if not res:
        return None
    data = res.json()
    if data["response"]:
        return data["response"][0]["team"]["id"]
    return None

# 📊 HISTÓRICO
def pegar_jogos(team_id):
    res = safe_request(f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10")
    if not res:
        return []
    return res.json().get("response", [])

# 🧠 ANÁLISE PRO
def analisar(home, away):
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

            gols.append(g1 + g2)

            if g1 > 0 and g2 > 0:
                btts += 1
        except:
            continue

    if len(gols) < 6:
        return None

    total = len(gols)

    stats = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Ambas marcam": btts / total,
        "Under 3.5": sum(g <= 3 for g in gols) / total
    }

    melhor = max(stats, key=stats.get)
    prob = int(stats[melhor] * 100)

    # 🔥 FILTRO INTELIGENTE
    if prob < 70:
        return None

    forca = 10 if prob >= 85 else 9 if prob >= 80 else 8

    return stats, melhor, prob, forca

# ⚽ BUSCAR JOGOS
def buscar_jogos():
    jogos = []
    hoje = datetime.utcnow().strftime("%Y-%m-%d")

    res = safe_request(f"https://v3.football.api-sports.io/fixtures?date={hoje}")
    if not res:
        return []

    data = res.json()
    agora = datetime.now()
    limite = limite_horas()

    for j in data.get("response", []):

        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
        dt = dt.astimezone()

        # 🔥 FILTRO DE TEMPO CORRIGIDO
        diff = (dt - agora).total_seconds()

        if diff < 0 or diff > limite:
            continue

        liga = nome_liga(j["league"]["name"], j["league"]["country"])
        if not liga:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        jogos.append((home, away, dt.strftime("%d/%m"), dt.strftime("%H:%M")))

    return jogos

# 🔥 MULTIPLA CORRIGIDA
def gerar_multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for home, away, data, hora in jogos:
        resultado = analisar(home, away)
        if resultado:
            stats, melhor, prob, _ = resultado
            picks.append((home, away, melhor, prob, hora, data))

    # 🔥 ORDENAR POR PROBABILIDADE
    picks.sort(key=lambda x: x[3], reverse=True)

    if not picks:
        return "❌ Nenhuma múltipla encontrada (poucos jogos fortes agora)"

    picks = picks[:qtd]

    msg = "🔥 GOUVEA BET – MÚLTIPLA PRO\n\n"

    for i, (h, a, e, p, hr, dt) in enumerate(picks, 1):
        msg += f"{i}️⃣ {h} x {a}\n📅 {dt}\n⏰ {hr}\n🎯 {e} ({p}%)\n\n"

    return msg

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

# 🤖 BOT FINAL
def main():
    global last_update_id

    print("BOT PRO ONLINE 🚀")

    while True:
        try:
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 30, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()

                # 🔥 MULTIPLA
                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    enviar(gerar_multipla(qtd))
                    continue

        except Exception as e:
            print("ERRO:", e)

        time.sleep(3)

if __name__ == "__main__":
    main()
