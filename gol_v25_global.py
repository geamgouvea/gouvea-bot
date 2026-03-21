import requests
import time
from datetime import datetime, timedelta

# 🔐 CONFIG
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
jogos_enviados = set()

# 🔥 REQUEST
def safe_request(url, params=None):
    try:
        return requests.get(url, headers=HEADERS, params=params, timeout=10)
    except:
        return None

# 🧠 PERÍODO ATUAL
def periodo_atual():
    h = datetime.now().hour
    if 0 <= h < 6: return "madrugada"
    if 6 <= h < 12: return "manha"
    if 12 <= h < 18: return "tarde"
    return "noite"

# ⏱️ LIMITE INTELIGENTE
def limite_horas():
    p = periodo_atual()
    if p == "madrugada": return 21600
    if p == "manha": return 43200
    if p == "tarde": return 43200
    if p == "noite": return 28800

# 🏆 LIGAS
def nome_liga(liga, pais):
    liga = liga.lower()
    pais = pais.lower()

    if "brazil" in pais:
        if "serie a" in liga: return "🇧🇷 Série A"
        if "serie b" in liga: return "🇧🇷 Série B"

    if "argentina" in pais: return "🇦🇷 Liga Argentina"
    if "england" in pais: return "🏴 Premier League"
    if "spain" in pais: return "🇪🇸 La Liga"
    if "italy" in pais: return "🇮🇹 Serie A"
    if "germany" in pais: return "🇩🇪 Bundesliga"

    if "portugal" in pais: return "🇵🇹 Liga Portugal"
    if "netherlands" in pais: return "🇳🇱 Eredivisie"
    if "belgium" in pais: return "🇧🇪 Liga Belga"
    if "mexico" in pais: return "🇲🇽 Liga MX"

    if "japan" in pais: return "🇯🇵 J-League"
    if "korea" in pais: return "🇰🇷 K-League"
    if "china" in pais: return "🇨🇳 China Super League"
    if "australia" in pais: return "🇦🇺 A-League"
    if "usa" in pais: return "🇺🇸 MLS"

    return None

# 🔍 TIME
def buscar_time(nome):
    try:
        res = safe_request("https://v3.football.api-sports.io/teams", {"search": nome})
        if not res: return None
        data = res.json()
        if data["response"]:
            return data["response"][0]["team"]["id"]
    except:
        return None

# 📊 HISTÓRICO
def pegar_jogos(team_id):
    try:
        res = safe_request(f"https://v3.football.api-sports.io/fixtures?team={team_id}&last=10")
        if not res: return []
        return res.json().get("response", [])
    except:
        return []

# 🧠 ANÁLISE COMPLETA
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    jogos = pegar_jogos(home_id) + pegar_jogos(away_id)

    gols = []
    btts = 0
    home_win = 0
    away_win = 0

    for j in jogos:
        try:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            gols.append(g1 + g2)

            if g1 > 0 and g2 > 0:
                btts += 1

            if g1 > g2:
                home_win += 1
            elif g2 > g1:
                away_win += 1

        except:
            continue

    if len(gols) < 8:
        return None

    total = len(gols)

    stats = {
        "Over 1.5": sum(g >= 2 for g in gols) / total,
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Ambas marcam": btts / total,
        "Under 3.5": sum(g <= 3 for g in gols) / total,
        "Casa vence": home_win / total,
        "Fora vence": away_win / total
    }

    # 🔥 prioridade inteligente
    prioridade = ["Over 2.5", "Under 3.5", "Ambas marcam", "Casa vence", "Fora vence", "Over 1.5"]

    melhor = None
    maior = 0

    for p in prioridade:
        if stats[p] > maior:
            melhor = p
            maior = stats[p]

    prob = int(maior * 100)

    if prob < 75:
        return None

    forca = 9 if prob >= 80 else 8

    return stats, melhor, prob, forca

# ⚽ BUSCAR JOGOS
def buscar_jogos(periodo=None):
    jogos = []
    hoje = datetime.utcnow().strftime("%Y-%m-%d")

    res = safe_request(f"https://v3.football.api-sports.io/fixtures?date={hoje}")
    if not res: return []

    data = res.json()
    agora = datetime.now()
    limite = limite_horas()

    for j in data.get("response", []):

        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
        dt = dt.astimezone()

        if (dt - agora).total_seconds() > limite:
            continue

        hora = dt.hour

        if periodo == "madrugada" and not (0 <= hora < 6): continue
        if periodo == "manha" and not (6 <= hora < 12): continue
        if periodo == "tarde" and not (12 <= hora < 18): continue
        if periodo == "noite" and not (18 <= hora <= 23): continue

        liga = nome_liga(j["league"]["name"], j["league"]["country"])
        if not liga:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        chave = f"{home}-{away}-{dt.strftime('%H:%M')}"
        if chave in jogos_enviados:
            continue

        jogos.append((home, away, liga,
                      dt.strftime("%d/%m"),
                      dt.strftime("%H:%M"),
                      chave))

    return jogos

# 🔥 MULTIPLA PRO
def gerar_multipla(qtd=3, periodo=None):
    jogos = buscar_jogos(periodo)
    picks = []

    for home, away, liga, data, hora, chave in jogos:

        resultado = analisar(home, away)
        if not resultado:
            continue

        stats, melhor, prob, _ = resultado

        picks.append((home, away, melhor, prob, hora, data))

    picks.sort(key=lambda x: x[3], reverse=True)
    picks = picks[:min(qtd, 4)]

    if not picks:
        return "❌ Nenhuma múltipla encontrada"

    msg = "🔥 GOUVEA BET – MÚLTIPLA PRO\n\n"

    for i, (h, a, e, p, hr, dt) in enumerate(picks, 1):
        msg += f"{i}️⃣ {h} x {a}\n📅 {dt}\n⏰ {hr}\n🎯 {e} ({p}%)\n\n"

    return msg

# 📊 ANÁLISE MANUAL
def analisar_manual(texto):
    try:
        home, away = texto.split(" x ")
    except:
        return "Formato correto: Time A x Time B"

    resultado = analisar(home.strip(), away.strip())

    if not resultado:
        return "❌ Não consegui analisar esse jogo"

    stats, melhor, prob, forca = resultado

    msg = f"""📊 ANÁLISE

{home.title()} x {away.title()}

📊 Over 1.5: {int(stats["Over 1.5"]*100)}%
📊 Over 2.5: {int(stats["Over 2.5"]*100)}%
📊 Ambas marcam: {int(stats["Ambas marcam"]*100)}%
📊 Under 3.5: {int(stats["Under 3.5"]*100)}%
📊 Casa vence: {int(stats["Casa vence"]*100)}%
📊 Fora vence: {int(stats["Fora vence"]*100)}%

🎯 Melhor: {melhor}
📊 Probabilidade: {prob}%
⭐ Força: {forca}/10
"""
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

# 🤖 BOT
def main():
    global last_update_id

    print("BOT PRO ONLINE...")

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

                # MULTIPLA
                if texto.startswith("multipla"):
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes) > 1 else 3
                    periodo = partes[2] if len(partes) > 2 else None
                    enviar(gerar_multipla(qtd, periodo))
                    continue

                # ANALISE MANUAL
                if " x " in texto:
                    enviar(analisar_manual(texto))
                    continue

                enviar("Use:\n- multipla 3 madrugada\n- time a x time b")

        except Exception as e:
            print("ERRO:", e)

        time.sleep(3)

if __name__ == "__main__":
    main()
