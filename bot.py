import asyncio
from playwright.async_api import async_playwright
import requests
import json
import os
import random

ORIGENES = ["EZE", "SCL"]
DESTINOS = ["ICN", "GMP"]
FECHAS = ["2025-09-10", "2025-09-15", "2025-09-20"]
PRECIO_UMBRAL = 900
ERROR_FARE_UMBRAL = 400
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
HISTORICO_FILE = "precios.json"

SITIOS = {
    "Kayak": "https://www.kayak.com/flights/{origen}-{destino}/{fecha}?sort=bestflight_a",
    "Skyscanner": "https://www.skyscanner.com/transport/flights/{origen}/{destino}/{fecha}/",
    "Google Flights": "https://www.google.com/travel/flights?q=flights%20from%20{origen}%20to%20{destino}%20on%20{fecha}"
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
]

# Cargar proxies
def cargar_proxies():
    if os.path.exists("proxies.txt"):
        with open("proxies.txt", "r") as f:
            return [p.strip() for p in f if p.strip()]
    return []

PROXIES = cargar_proxies()

def enviar_alerta(precio, fecha, origen, destino, url, tipo="normal"):
    if tipo == "error":
        mensaje = f"🚨 ERROR FARE 🚨\n{origen} → {destino}\nFecha: {fecha}\nPrecio: ${precio}\n¡COMPRA YA!\n{url}"
    elif tipo == "bajo":
        mensaje = f"🔥 Oferta detectada: {origen} → {destino}\nFecha: {fecha}\nPrecio: ${precio}\n{url}"
    else:
        mensaje = f"💰 Baja de precio: {origen} → {destino}\nFecha: {fecha}\nNuevo precio: ${precio}\n{url}"

    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                 params={"chat_id": CHAT_ID, "text": mensaje})

def cargar_historico():
    if os.path.exists(HISTORICO_FILE):
        with open(HISTORICO_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_historico(data):
    with open(HISTORICO_FILE, "w") as f:
        json.dump(data, f)

async def scrape_precio(url, navegador, proxy=None):
    try:
        user_agent = random.choice(USER_AGENTS)
        contexto_args = {"user_agent": user_agent}
        if proxy:
            contexto_args["proxy"] = {"server": proxy}
        contexto = await navegador.new_context(**contexto_args)
        pagina = await contexto.new_page()

        await pagina.goto(url, timeout=60000)
        await pagina.wait_for_selector(".price-text", timeout=30000)
        precios = await pagina.query_selector_all(".price-text")
        precio_texto = await precios[0].inner_text()
        precio = int("".join(filter(str.isdigit, precio_texto)))
        await pagina.close()
        return precio
    except:
        return None

async def obtener_precio_mas_bajo(origen, destino, fecha):
    async with async_playwright() as p:
        navegador = await p.chromium.launch(headless=True)
        tareas = []
        proxy = random.choice(PROXIES) if PROXIES else None
        for sitio, url_template in SITIOS.items():
            url = url_template.format(origen=origen, destino=destino, fecha=fecha)
            tareas.append(scrape_precio(url, navegador, proxy))
        resultados = await asyncio.gather(*tareas)
        await navegador.close()

        precios_validos = [p for p in resultados if p is not None]
        return min(precios_validos) if precios_validos else None

async def main():
    historico = cargar_historico()
    for origen in ORIGENES:
        for destino in DESTINOS:
            for fecha in FECHAS:
                await asyncio.sleep(random.uniform(5, 15))
                precio = await obtener_precio_mas_bajo(origen, destino, fecha)

                if precio is None:
                    print(f"No se pudo obtener precio para {origen}-{destino} {fecha}")
                    continue

                print(f"[{origen} - {destino} - {fecha}] Precio más bajo: ${precio}")
                clave = f"{origen}-{destino}-{fecha}"
                precio_anterior = historico.get(clave, 99999)

                if precio <= ERROR_FARE_UMBRAL:
                    enviar_alerta(precio, fecha, origen, destino, SITIOS["Kayak"].format(origen=origen, destino=destino, fecha=fecha), "error")
                elif precio <= PRECIO_UMBRAL:
                    enviar_alerta(precio, fecha, origen, destino, SITIOS["Kayak"].format(origen=origen, destino=destino, fecha=fecha), "bajo")
                elif precio < precio_anterior:
                    enviar_alerta(precio, fecha, origen, destino, SITIOS["Kayak"].format(origen=origen, destino=destino, fecha=fecha), "baja")

                historico[clave] = min(precio, precio_anterior)

    guardar_historico(historico)

if __name__ == "__main__":
    asyncio.run(main())
