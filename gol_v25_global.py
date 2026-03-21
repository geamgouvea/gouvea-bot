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
jogos_enviados = set()

# 🔥 REQUEST
def safe_request(url, params=None):
    try:
        return requests.get(url, headers=HEADERS, params=params, timeout=10)
    except:
        return None

# 🏆 LIGAS
def nome_liga(liga, pais):
    liga = liga.lower()
    pais = pais.lower()

    if "brazil" in pais:
        if "serie a" in liga: return "🇧🇷 Brasileirão Série A"
        if "serie b" in liga: return "🇧🇷 Série B"

    if "argentina" in pais: return "🇦🇷 Liga Argentina"

    if "england" in pais: return "🏴 Premier League"
    if "spain" in pais: return "🇪🇸 La Liga"
    if "italy" in pais: return "🇮🇹 Serie A"
    if "germany" in pais: return "🇩🇪 Bundesliga"

    if "portugal" in pais: return "🇵🇹 Liga Portugal"
    if "netherlands" in pais: return "🇳🇱 Eredivisie"

    # 🌙 madrugada
    if "japan" in pais: return "🇯🇵 J-League"
    if "korea" in pais: return "🇰🇷 K-League"
    if "china" in pais: return "🇨🇳 Super League"
    if "australia" in pais: return "🇦🇺 A-League"

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

# 🧠 ANÁLISE (SEM VENCEDOR)
def analisar(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    jogos_home = pegar_jogos(home_id)
    jogos_away = pegar_jogos(away_id)

    jogos = jogos_home + jogos_away

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
        return None

    total = len(gols)

    over15 = min(sum(g >= 2 for g in gols) / total, 0.88)
    over25 = min(sum(g >= 3 for g in gols) / total, 0.82)
    btts_p = min(btts / total, 0.80)
    under35 = min(sum(g <= 3 for g in gols) / total, 0.75)

    stats = {
        "Over 1.5": int(over15 * 100),
        "Over 2.5": int(over25 * 100),
        "Ambas marcam": int(btts_p * 100),
        "Under 3.5": int(under35 * 100)
    }

    # escolha padrão (SEM vencedor)
    if stats["Over 2.5"] >= 70:
        melhor = "Over 2.5"
        prob = stats["Over 2.5"]
    elif stats["Ambas marcam"] >= 65:
        melhor = "Ambas marcam"
        prob = stats["Ambas marcam"]
    elif stats["Under 3.5"] >= 68:
        melhor = "Under 3.5"
        prob = stats["Under 3.5"]
    else:
        return None

    forca = 8 if prob >= 75 else 7

    return stats, melhor, prob, forca, jogos_home, jogos_away

# 🧠 VENCEDOR (SÓ MULTIPLA)
def calcular_vencedor(jogos_home, jogos_away, home_id, away_id):
    try:
        v_home = sum(
            1 for j in jogos_home
            if j["teams"]["home"]["id"] == home_id and j["goals"]["home"] > j["goals"]["away"]
        )

        v_away = sum(
            1 for j in jogos_away
            if j["teams"]["away"]["id"] == away_id and j["goals"]["away"] > j["goals"]["home"]
        )

        p_home = int((v_home / len(jogos_home)) * 100) if jogos_home else 0
        p_away = int((v_away / len(jogos_away)) * 100) if jogos_away else 0

        if p_home >= 65 and p_home > p_away:
            return "Casa vence", p_home
        elif p_away >= 65 and p_away > p_home:
            return "Fora vence", p_away

        return None, 0
    except:
        return None, 0

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

        if (dt - agora).total_seconds() > 7200:
            continue

        liga = nome_liga(j["league"]["name"], j["league"]["country"])
        if not liga:
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]

        chave = f"{home}-{away}"
        if chave in jogos_enviados:
            continue

        dt -= timedelta(hours=4)

        jogos.append((home, away, liga,
                      dt.strftime("%d/%m"),
                      dt.strftime("%H:%M")))

    return jogos

# 🔥 MULTIPLA INTELIGENTE
def gerar_multipla(qtd=3, periodo=None):
    jogos = buscar_jogos()
    picks = []

    for home, away, liga, data, hora in jogos:

        resultado = analisar(home, away)
        if not resultado:
            continue

        stats, melhor, prob, _, jogos_home, jogos_away = resultado

        # tenta vencedor
        home_id = buscar_time(home)
        away_id = buscar_time(away)

        vencedor, prob_v = calcular_vencedor(jogos_home, jogos_away, home_id, away_id)

        # decide qual usar
        if vencedor and prob_v >= prob:
            entrada = vencedor
            prob_final = prob_v
        else:
            entrada = melhor
            prob_final = prob

        picks.append((home, away, entrada, prob_final, hora))

    picks.sort(key=lambda x: x[3], reverse=True)
    picks = picks[:qtd]

    if not picks:
        return "❌ Nenhuma múltipla encontrada"

    msg = "🔥 GOUVEA BET – MÚLTIPLA INTELIGENTE\n\n"

    for i, (h, a, e, p, hr) in enumerate(picks, 1):
        msg += f"{i}️⃣ {h} x {a}\n⏰ {hr}\n🎯 {e} ({p}%)\n\n"

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
    global last_update_id, ultimo_auto

    print("BOT V6 ONLINE...")

    while True:
        try:
            # 🔥 AUTO
            if time.time() - ultimo_auto > 1800:
                jogos = buscar_jogos()

                for home, away, liga, data, hora in jogos[:3]:

                    resultado = analisar(home, away)
                    if not resultado:
                        continue

                    stats, melhor, prob, forca, _, _ = resultado

                    msg = f"""GOUVEA BET

{home} x {away}

🏆 {liga}
📅 {data}
⏰ {hora}

📊 Over 1.5: {stats["Over 1.5"]}%
📊 Over 2.5: {stats["Over 2.5"]}%
📊 Ambas marcam: {stats["Ambas marcam"]}%
📊 Under 3.5: {stats["Under 3.5"]}%

🎯 Melhor entrada: {melhor}

📊 Prob: {prob}%
⭐ Força: {forca}/10

{"✅ ENTRAR" if forca >= 8 else "⚠️ OBSERVAR"}
"""
                    enviar(msg)
                    jogos_enviados.add(f"{home}-{away}")

                ultimo_auto = time.time()

            # TELEGRAM
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"timeout": 30, "offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"]["text"].lower().strip()

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
