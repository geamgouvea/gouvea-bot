import requests
import time
from datetime import datetime, timedelta, timezone

# 🔐 CONFIG
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
ultimo_auto = 0

# 🔥 REQUEST SEGURO
def safe_request(url, params=None):
    try:
        return requests.get(url, headers=HEADERS, params=params, timeout=10)
    except:
        return None

# 🏆 LIGAS FILTRADAS (QUALIDADE + MADRUGADA)
def nome_liga(liga, pais):
    liga = liga.lower()
    pais = pais.lower()

    if "brazil" in pais:
        if "serie a" in liga:
            return "🇧🇷 Campeonato Brasileiro – Série A"
        if "serie b" in liga:
            return "🇧🇷 Série B"

    if "england" in pais: return "🏴 Premier League"
    if "spain" in pais: return "🇪🇸 La Liga"
    if "italy" in pais: return "🇮🇹 Serie A"
    if "germany" in pais: return "🇩🇪 Bundesliga"

    if "argentina" in pais: return "🇦🇷 Liga Argentina"
    if "portugal" in pais: return "🇵🇹 Liga Portugal"
    if "netherlands" in pais: return "🇳🇱 Eredivisie"
    if "belgium" in pais: return "🇧🇪 Liga Belga"
    if "mexico" in pais: return "🇲🇽 Liga MX"

    # 🌙 madrugada
    if "japan" in pais: return "🇯🇵 J-League"
    if "korea" in pais: return "🇰🇷 K-League"
    if "china" in pais: return "🇨🇳 Super League China"
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

# 🧠 ANÁLISE
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
            gols.append(g1 + g2)
            if g1 > 0 and g2 > 0:
                btts += 1
        except:
            continue

    if len(gols) < 8:
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

    # 🔥 FILTRO PROFISSIONAL
    if melhor == "Over 1.5" and prob < 80:
        return None

    forca = 9 if prob >= 75 else 8 if prob >= 70 else 7

    return stats, melhor, prob, forca

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

# ⏰ FILTRO PERÍODO
def filtrar_periodo(hora, periodo):
    h = int(hora.split(":")[0])

    if periodo == "madrugada": return 0 <= h < 8
    if periodo == "manha": return 8 <= h < 12
    if periodo == "tarde": return 12 <= h < 18
    if periodo == "noite": return 18 <= h <= 23

    return True

# ⚽ BUSCAR JOGOS
def buscar_jogos():
    jogos = []
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    res = safe_request(f"https://v3.football.api-sports.io/fixtures?date={hoje}")
    if not res: return []

    data = res.json()
    agora = datetime.now(timezone.utc)

    for j in data.get("response", []):

        if j["fixture"]["status"]["short"] != "NS":
            continue

        dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))

        # 🔥 só pré-jogo até 2h
        if (dt - agora).total_seconds() > 7200:
            continue

        liga = nome_liga(j["league"]["name"], j["league"]["country"])
        if not liga:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        dt -= timedelta(hours=4)

        jogos.append((home, away, liga,
                      dt.strftime("%d/%m"),
                      dt.strftime("%H:%M")))

    return jogos

# 🔥 MULTIPLA
def gerar_multipla(qtd=3, periodo=None):
    jogos = buscar_jogos()
    picks = []

    for home, away, liga, data, hora in jogos:

        if periodo and not filtrar_periodo(hora, periodo):
            continue

        resultado = analisar(home, away)
        if not resultado:
            continue

        stats, melhor, prob, _ = resultado

        if prob < 70:
            continue

        picks.append((home, away, melhor, prob, hora))

    picks.sort(key=lambda x: x[3], reverse=True)

    picks = picks[:qtd]

    if not picks:
        return "❌ Nenhuma múltipla encontrada"

    msg = "🔥 GOUVEA BET – MÚLTIPLA\n\n"

    for i, (h, a, e, p, hr) in enumerate(picks, 1):
        msg += f"{i}️⃣ {h} x {a}\n⏰ {hr}\n🎯 {e} ({p}%)\n\n"

    return msg

# 🤖 BOT
def main():
    global last_update_id, ultimo_auto

    print("BOT ONLINE...")

    while True:
        try:
            # 🔥 AUTOMÁTICO
            if time.time() - ultimo_auto > 1800:
                jogos = buscar_jogos()

                for home, away, liga, data, hora in jogos[:3]:

                    resultado = analisar(home, away)
                    if not resultado:
                        continue

                    stats, melhor, prob, forca = resultado

                    if prob < 70:
                        continue

                    msg = f"""GOUVEA BET

{home} x {away}

🏆 {liga}
📅 {data}
⏰ {hora}

📊 Over 1.5: {int(stats["Over 1.5"]*100)}%
📊 Over 2.5: {int(stats["Over 2.5"]*100)}%
📊 Ambas marcam: {int(stats["Ambas marcam"]*100)}%
📊 Under 3.5: {int(stats["Under 3.5"]*100)}%

🎯 Melhor entrada: {melhor}

📊 Prob: {prob}%
⭐ Força: {forca}/10

{"✅ ENTRAR" if forca >= 8 else "⚠️ OBSERVAR"}
"""
                    enviar(msg)

                ultimo_auto = time.time()

            # 🔍 MANUAL
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

                # INDIVIDUAL
                if " x " not in texto:
                    enviar("Formato: Time A x Time B")
                    continue

                home, away = texto.split(" x ")

                resultado = analisar(home, away)

                if not resultado:
                    enviar("❌ Não consegui analisar esse jogo")
                    continue

                stats, melhor, prob, forca = resultado

                msg = f"""GOUVEA BET

{home.title()} x {away.title()}

📊 Over 1.5: {int(stats["Over 1.5"]*100)}%
📊 Over 2.5: {int(stats["Over 2.5"]*100)}%
📊 Ambas marcam: {int(stats["Ambas marcam"]*100)}%
📊 Under 3.5: {int(stats["Under 3.5"]*100)}%

🎯 Melhor entrada: {melhor}

📊 Prob: {prob}%
⭐ Força: {forca}/10

{"✅ ENTRAR" if forca >= 8 else "⚠️ OBSERVAR"}
"""
                enviar(msg)

        except Exception as e:
            print("ERRO:", e)

        time.sleep(3)

if __name__ == "__main__":
    main()
