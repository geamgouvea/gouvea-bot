import requests
import time
import threading
from datetime import datetime

# ================= CONFIG =================
TOKEN = "8650319652:AAFvJ8kJoMIoxFEq2XYVzF4P9KBpMPZ17ZA"
CHAT_ID = "2124226862"
API_KEY = "565ed1c1b1e85fefe0a5fa2995db9bd5"

HEADERS = {"x-apisports-key": API_KEY}

last_update_id = 0
jogos_enviados = set()
ultimo_envio = 0

# ================= LIGAS =================
LIGAS_OK = [
    "Brazil", "England", "Spain", "Italy", "Germany",
    "France", "Netherlands", "Portugal",
    "Japan", "South Korea", "Australia"
]

def liga_ok(nome):
    nome = nome.lower()
    return any(l.lower() in nome for l in LIGAS_OK)

# ================= REQUEST =================
def req(url, params=None):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        return None
    return None

# ================= TIMES =================
def buscar_time(nome):
    data = req("https://v3.football.api-sports.io/teams", {"search": nome})
    if data and data["response"]:
        return data["response"][0]["team"]["id"]
    return None

def jogos_time(id):
    data = req("https://v3.football.api-sports.io/fixtures", {
        "team": id, "last": 10
    })
    return data.get("response", []) if data else []

# ================= ANALISE =================
def analisar(home, away):
    h = buscar_time(home)
    a = buscar_time(away)

    if not h or not a:
        return None

    jogos = jogos_time(h) + jogos_time(a)
    gols = []

    for j in jogos:
        try:
            g = j["goals"]["home"] + j["goals"]["away"]
            gols.append(g)
        except:
            continue

    if len(gols) < 6:
        return None

    total = len(gols)
    media = sum(gols)/total
    over15 = sum(g>=2 for g in gols)/total
    over25 = sum(g>=3 for g in gols)/total

    # 🎯 EQUILÍBRIO REAL
    if over25 >= 0.55 and media >= 2.2:
        entrada = "Over 2.5"
        prob = over25
    elif over15 >= 0.65:
        entrada = "Over 1.5"
        prob = over15
    else:
        return None

    prob = int(prob*100)
    forca = 9 if prob >= 80 else 8 if prob >= 70 else 7

    return entrada, prob, forca

# ================= BUSCAR JOGOS =================
def buscar_jogos():
    data = req("https://v3.football.api-sports.io/fixtures", {"next": 50})
    if not data:
        return []

    jogos = []

    for j in data["response"]:
        if j["fixture"]["status"]["short"] != "NS":
            continue

        liga = j["league"]["country"]

        if not liga_ok(liga):
            continue

        home = j["teams"]["home"]["name"]
        away = j["teams"]["away"]["name"]
        hora = j["fixture"]["date"][11:16]

        jogos.append((home, away, hora))

    return jogos

# ================= TELEGRAM =================
def enviar(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

# ================= AUTO =================
def auto():
    global ultimo_envio

    while True:
        try:
            if time.time() - ultimo_envio > 600:
                jogos = buscar_jogos()
                enviados = 0

                for h, a, hora in jogos:
                    chave = h + a
                    if chave in jogos_enviados:
                        continue

                    res = analisar(h, a)

                    if res:
                        e, p, f = res

                        msg = f"""🔥 SINAL

⚽ {h} x {a}
⏰ {hora}

🎯 {e}
📊 {p}%
⭐ {f}/10
"""
                        enviar(msg)

                        jogos_enviados.add(chave)
                        enviados += 1

                    if enviados >= 3:
                        break

                ultimo_envio = time.time()

        except:
            pass

        time.sleep(10)

# ================= MULTIPLA =================
def multipla(qtd=3):
    jogos = buscar_jogos()
    picks = []

    for h, a, _ in jogos:
        res = analisar(h, a)
        if res:
            e, p, f = res
            if f >= 7:
                picks.append((h, a, e, p))

    if not picks:
        return "❌ Sem múltipla agora"

    picks.sort(key=lambda x: x[3], reverse=True)

    msg = "🔥 MÚLTIPLA\n\n"

    for i, (h, a, e, p) in enumerate(picks[:qtd], 1):
        msg += f"{i}️⃣ {h} x {a}\n🎯 {e} ({p}%)\n\n"

    return msg

# ================= MANUAL =================
def manual(texto):
    if "x" not in texto:
        enviar("Formato: Time A x Time B")
        return

    try:
        h, a = texto.split("x")
        h = h.strip()
        a = a.strip()
    except:
        return

    res = analisar(h, a)

    if not res:
        enviar("⚠️ Sem valor agora")
        return

    e, p, f = res

    enviar(f"""🔍 ANÁLISE

⚽ {h} x {a}

🎯 {e}
📊 {p}%
⭐ {f}/10
""")

# ================= MAIN =================
def main():
    global last_update_id

    enviar("🤖 Gouvea Bet FINAL Online!")

    while True:
        try:
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id}
            ).json()

            for u in res.get("result", []):
                last_update_id = u["update_id"] + 1

                if "message" not in u:
                    continue

                texto = u["message"].get("text","").lower()

                if "multipla" in texto:
                    partes = texto.split()
                    qtd = int(partes[1]) if len(partes)>1 else 3
                    enviar(multipla(qtd))

                elif "x" in texto:
                    manual(texto)

        except:
            pass

        time.sleep(2)

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=auto).start()
    main()
