import asyncio
from playwright.async_api import async_playwright
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

async def scrape_precio_kayak(pagina):
    try:
        await pagina.wait_for_selector('div.e2GB-price-text', timeout=30000)
        precio_elemento = await pagina.query_selector('div.e2GB-price-text')
        precio_texto = await precio_elemento.inner_text()
        precio_num = int("".join(filter(str.isdigit, precio_texto)))
        return precio_num
    except Exception as e:
        print(f"Error scraping Kayak: {e}")
        return None

async def enviar_alerta_telegram(mensaje):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensaje}
    response = requests.post(url, data=data)
    if response.status_code != 200:
        print(f"Error enviando mensaje Telegram: {response.text}")

async def revisar_vuelo(origen, destino, fecha):
    url = f"https://www.kayak.com/flights/{origen}-{destino}/{fecha}?sort=bestflight_a"
    async with async_playwright() as p:
        navegador = await p.chromium.launch(headless=True)
        pagina = await navegador.new_page()
        await pagina.goto(url)
        
        if "kayak.com" in url:
            precio = await scrape_precio_kayak(pagina)
        else:
            precio = None  # Aquí irían otras funciones para otros sitios
        
        await navegador.close()
        return precio

async def main():
    ORIGENES = ["EZE", "SCL"]
    DESTINOS = ["ICN", "GMP"]
    FECHAS = ["2025-09-10", "2025-09-15", "2025-09-20"]
    PRECIO_UMBRAL = 1000  # ajustar según conveniencia
    
    for origen in ORIGENES:
        for destino in DESTINOS:
            for fecha in FECHAS:
                precio = await revisar_vuelo(origen, destino, fecha)
                if precio is None:
                    print(f"No se pudo obtener precio para {origen}-{destino} {fecha}")
                else:
                    print(f"[{origen} - {destino} - {fecha}] Precio más bajo: ${precio}")
                    if precio < PRECIO_UMBRAL:
                        mensaje = (f"🔥 Oferta detectada: {origen} → {destino}\n"
                                   f"Fecha: {fecha}\nPrecio: ${precio}\n{url}")
                        await enviar_alerta_telegram(mensaje)

if __name__ == "__main__":
    asyncio.run(main())

