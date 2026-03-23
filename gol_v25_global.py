import requests
import time
import threading
from datetime import datetime
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
enviados_ids = set()

# ================= FILTRO LIGAS =================
LIGAS_PERMITIDAS = [
    "brazil", "argentina", "england", "spain",
    "italy", "germany", "france",
    "netherlands", "portugal", "scotland",
    "saudi-arabia"
]

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
        else:
            print("ERRO API:", r.status_code)
    except Exception as e:
        print("ERRO REQUEST:", e)
    return None

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except Exception as e:
        print("ERRO TELEGRAM:", e)

# ================= BUSCAR TIME =================
def buscar_time(nome):
    nome = normalizar(nome)
    data = req("https://v3.football.api-sports.io/teams", {"search": nome})

    if data and data.get("response"):
        return data["response"][0]["team"]["id"]

    return None

# ================= HISTÓRICO =================
def historico(team_id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": team_id,
        "last": 10
    })
    return data.get("response", []) if data else []

# ================= ANALISE (MANUAL) =================
def analisar_manual(home, away):
    try:
        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return "❌ Times não encontrados"

        jogos = historico(home_id) + historico(away_id)

        gols = []
        for j in jogos:
            try:
                g1 = j["goals"]["home"]
                g2 = j["goals"]["away"]
                if g1 is not None and g2 is not None:
                    gols.append(g1 + g2)
            except:
                continue

        if not gols:
            return "❌ Sem dados"

        media = sum(gols) / len(gols)
        prob = sum(g >= 2 for g in gols) / len(gols)

        return f"""🔍 ANÁLISE

⚽ {home} x {away}

🎯 Over 1.5
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

    except Exception as e:
        print("ERRO ANALISE:", e)
        return "❌ Erro ao analisar"

# ================= ANALISE AUTO =================
def analisar_auto(fixture):
    try:
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        liga = fixture["league"]["name"]
        pais = fixture["league"]["country"].lower()
        fixture_id = fixture["fixture"]["id"]

        # filtro liga
        if not any(p in pais for p in LIGAS_PERMITIDAS):
            return None

        # bloquear base
        if "u21" in home.lower() or "u21" in away.lower():
            return None

        # horário
        dt = datetime.fromisoformat(
            fixture["fixture"]["date"].replace("Z","+00:00")
        )
        hora = dt.strftime("%H:%M")

        # análise estatística
        home_id = buscar_time(home)
        away_id = buscar_time(away)

        if not home_id or not away_id:
            return None

        jogos = historico(home_id) + historico(away_id)

        gols = []
        for j in jogos:
            try:
                g1 = j["goals"]["home"]
                g2 = j["goals"]["away"]
                if g1 is not None and g2 is not None:
                    gols.append(g1 + g2)
            except:
                continue

        if not gols:
            return None

        media = sum(gols) / len(gols)
        prob = sum(g >= 2 for g in gols) / len(gols)

        if prob < 0.65:
            return None

        msg = f"""🔥 SINAL PRO

⚽ {home} x {away}
🏆 {liga}
⏰ {hora}

🎯 Over 1.5
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

        return msg, fixture_id

    except:
        return None

# ================= AUTO =================
def auto():
    global enviados_ids

    while True:
        try:
            print("AUTO rodando...")

            data = req("https://v3.football.api-sports.io/fixtures", {"next": 50})

            if data:
                enviados = 0

                for j in data["response"]:
                    fixture_id = j["fixture"]["id"]

                    if fixture_id in enviados_ids:
                        continue

                    res = analisar_auto(j)

                    if res:
                        msg, fid = res

                        enviar("🤖 AUTO\n\n" + msg)

                        enviados_ids.add(fid)
                        enviados += 1

                    if enviados >= 3:
                        break

        except Exception as e:
            print("ERRO AUTO:", e)

        time.sleep(1200)

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 BOT ATIVO COM SUCESSO")

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

                if "x" in texto:
                    try:
                        h, a = texto.split("x")
                        enviar(analisar_manual(h.strip(), a.strip()))
                    except:
                        enviar("⚠️ Use: time x time")

                else:
                    enviar("⚠️ Use: time x time")

        except Exception as e:
            print("ERRO MAIN:", e)

        time.sleep(5)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
