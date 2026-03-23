import requests
import time
import threading
import json
from datetime import datetime
import unicodedata

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"
HEADERS = {"x-apisports-key": API_KEY}

last_update_id = None
enviados_ids = set()

# ================= LIGAS =================
LIGAS_TOP = [
    "brazil","argentina","england","spain","italy",
    "germany","france","netherlands","portugal",
    "scotland","saudi"
]

# ================= NORMALIZAR =================
def normalizar(nome):
    nome = nome.lower().strip()
    nome = unicodedata.normalize('NFKD', nome)
    nome = nome.encode('ASCII', 'ignore').decode('ASCII')
    return nome

# ================= PERSISTENCIA =================
def salvar_ids():
    with open("enviados.json","w") as f:
        json.dump(list(enviados_ids), f)

def carregar_ids():
    global enviados_ids
    try:
        with open("enviados.json") as f:
            enviados_ids = set(json.load(f))
    except:
        enviados_ids = set()

# ================= REQUEST =================
def req(url, params=None):
    try:
        time.sleep(0.3)
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            print("ERRO API:", r.status_code, r.text)
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

    for parte in nome.split():
        if len(parte) >= 4:
            data = req("https://v3.football.api-sports.io/teams", {"search": parte})
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

# ================= ANALISE =================
def analisar_jogo(home_id, away_id):
    jogos = historico(home_id) + historico(away_id)

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

    if not gols:
        return None

    total = len(gols)
    media = sum(gols) / total

    probs = {
        "Over 2.5": sum(g >= 3 for g in gols) / total,
        "Ambas Marcam": btts / total,
        "Under 2.5": sum(g <= 2 for g in gols) / total,
        "Over 1.5": sum(g >= 2 for g in gols) / total
    }

    # DECISÃO INTELIGENTE
    if probs["Over 2.5"] >= 0.65 and media >= 2.6:
        return "Over 2.5", probs["Over 2.5"], media

    if probs["Ambas Marcam"] >= 0.6 and media >= 2.4:
        return "Ambas Marcam", probs["Ambas Marcam"], media

    if probs["Under 2.5"] >= 0.65 and media <= 2.2:
        return "Under 2.5", probs["Under 2.5"], media

    if probs["Over 1.5"] >= 0.70 and media >= 2.3:
        return "Over 1.5", probs["Over 1.5"], media

    return None

# ================= FILTRO =================
def filtro_ruim(home, away, liga):
    txt = (home + away + liga).lower()

    bloqueios = ["u21","u23","reserves","women","femin","b","ii"]

    return any(b in txt for b in bloqueios)

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

                    pais = normalizar(j["league"]["country"])

                    if not any(p in pais for p in LIGAS_TOP):
                        continue

                    liga = j["league"]["name"]
                    home = j["teams"]["home"]["name"]
                    away = j["teams"]["away"]["name"]

                    if normalizar(home) == normalizar(away):
                        continue

                    if filtro_ruim(home, away, liga):
                        continue

                    home_id = buscar_time(home)
                    away_id = buscar_time(away)

                    if not home_id or not away_id:
                        continue

                    analise = analisar_jogo(home_id, away_id)

                    if not analise:
                        continue

                    melhor, prob, media = analise

                    if prob < 0.65:
                        continue

                    try:
                        dt = datetime.fromisoformat(
                            j["fixture"]["date"].replace("Z","+00:00")
                        )
                        hora = dt.strftime("%H:%M")
                    except:
                        hora = "--:--"

                    msg = f"""🔥 SINAL PRO

⚽ {home} x {away}
🏆 {liga}
⏰ {hora}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

                    enviar("🤖 AUTO\n\n" + msg)

                    enviados_ids.add(fixture_id)
                    salvar_ids()

                    enviados += 1

                    if enviados >= 3:
                        break

        except Exception as e:
            print("ERRO AUTO:", e)

        time.sleep(1200)

# ================= MANUAL =================
def analisar_manual(texto):
    partes = texto.split("x")

    if len(partes) != 2:
        return "⚠️ Use: time x time"

    h, a = partes

    if normalizar(h) == normalizar(a):
        return "❌ Times iguais inválidos"

    home_id = buscar_time(h.strip())
    away_id = buscar_time(a.strip())

    if not home_id or not away_id:
        return "❌ Times não encontrados"

    analise = analisar_jogo(home_id, away_id)

    if not analise:
        return "❌ Sem dados suficientes"

    melhor, prob, media = analise

    return f"""🔍 ANÁLISE

⚽ {h.strip()} x {a.strip()}

🎯 {melhor}
📊 {int(prob*100)}%
📈 Média gols: {round(media,2)}"""

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

                texto = u["message"].get("text", "")

                if not texto:
                    continue

                resposta = analisar_manual(texto.lower())

                enviar(resposta)

        except Exception as e:
            print("ERRO MAIN:", e)

        time.sleep(5)

# ================= START =================
if __name__ == "__main__":
    carregar_ids()
    t = threading.Thread(target=auto, daemon=True)
    t.start()
    main()
