import requests
import time
import threading
from datetime import datetime, timedelta
import unicodedata
import re

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

AUTO_INTERVALO = 1800
JANELA_MIN = 10
JANELA_MAX = 720

enviados_ids = set()
last_update_id = None

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    return nome.encode('ASCII', 'ignore').decode('ASCII')

# ================= REQUEST =================
def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)
    data = req("https://v3.football.api-sports.io/teams", {"search": nome})

    if not data or not data["response"]:
        return None

    return data["response"][0]["team"]["id"]

# ================= BUSCAR FIXTURE =================
def buscar_fixture(home, away):
    home_id = buscar_time(home)
    away_id = buscar_time(away)

    if not home_id or not away_id:
        return None

    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": home_id,
        "next": 15
    })

    if not data:
        return None

    for j in data["response"]:
        if j["teams"]["away"]["id"] == away_id:
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
    try:
        fixture = buscar_fixture(home, away)
        if not fixture:
            return None

        home_id = fixture["teams"]["home"]["id"]
        away_id = fixture["teams"]["away"]["id"]

        jogos = historico(home_id) + historico(away_id)

        gols = []
        btts = 0

        for j in jogos:
            g1 = j["goals"]["home"]
            g2 = j["goals"]["away"]

            if g1 is None or g2 is None:
                continue

            total = g1 + g2
            gols.append(total)

            if g1 > 0 and g2 > 0:
                btts += 1

        if len(gols) < 5:
            return None

        total = len(gols)
        media = sum(gols) / total

        probs = {
            "Over 1.5": sum(g >= 2 for g in gols) / total,
            "Over 2.5": sum(g >= 3 for g in gols) / total,
            "Under 2.5": sum(g <= 2 for g in gols) / total,
            "Ambas Marcam": btts / total
        }

        melhor = max(probs, key=probs.get)
        prob = probs[melhor]

        dt = datetime.fromisoformat(fixture["fixture"]["date"].replace("Z","+00:00"))
        dt_local = dt - timedelta(hours=4)

        liga = f'{fixture["league"]["name"]} ({fixture["league"]["country"]})'

        return {
            "texto": f"{fixture['teams']['home']['name']} x {fixture['teams']['away']['name']}",
            "mercado": melhor,
            "prob": prob,
            "msg": f"""⚽ {fixture['teams']['home']['name']} x {fixture['teams']['away']['name']}
🏆 {liga}
📅 {dt_local.strftime("%d/%m")} ⏰ {dt_local.strftime("%H:%M")}
🎯 {melhor} | {int(prob*100)}%"""
        }

    except:
        return None

# ================= MANUAL =================
def manual(texto):
    try:
        partes = re.split(r"x|vs|versus", texto.lower())

        if len(partes) != 2:
            return "⚠️ Use: time x time"

        h = partes[0].strip()
        a = partes[1].strip()

        res = analisar(h, a)

        if not res:
            return "❌ Jogo não encontrado"

        return "🧠 MANUAL\n\n" + res["msg"]

    except:
        return "⚠️ Erro"

# ================= AUTO + MULTIPLAS =================
def auto():
    while True:
        try:
            agora = datetime.utcnow()
            candidatos = []

            for i in range(2):
                data_busca = (agora + timedelta(days=i)).strftime("%Y-%m-%d")

                data = req("https://v3.football.api-sports.io/fixtures", {"date": data_busca})
                if not data:
                    continue

                for j in data["response"]:
                    dt = datetime.fromisoformat(j["fixture"]["date"].replace("Z","+00:00"))
                    diff = (dt - agora).total_seconds() / 60

                    if diff < JANELA_MIN or diff > JANELA_MAX:
                        continue

                    res = analisar(
                        j["teams"]["home"]["name"],
                        j["teams"]["away"]["name"]
                    )

                    if not res:
                        continue

                    if res["prob"] >= 0.70:
                        candidatos.append(res)

            candidatos.sort(key=lambda x: x["prob"], reverse=True)

            # 🔥 MULTIPLA 7
            if len(candidatos) >= 7:
                msg = "🎯 MÚLTIPLA (7 JOGOS)\n\n"
                for i, c in enumerate(candidatos[:7], 1):
                    msg += f"{i}. {c['texto']} → {c['mercado']}\n"
                enviar(msg)

            # 💣 MULTIPLA 10
            if len(candidatos) >= 10:
                msg = "\n💣 BINGO (10 JOGOS)\n\n"
                for i, c in enumerate(candidatos[:10], 1):
                    msg += f"{i}. {c['texto']} → {c['mercado']}\n"
                enviar(msg)

            if len(candidatos) == 0:
                enviar("⚠️ AUTO: Nenhum jogo qualificado")

        except Exception as e:
            enviar(f"❌ ERRO AUTO: {e}")

        time.sleep(AUTO_INTERVALO)

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ONLINE")

    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id or 0}
            ).json()

            for u in r.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text", "")
                enviar(manual(texto))

        except:
            pass

        time.sleep(3)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
