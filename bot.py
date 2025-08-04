import asyncio
from playwright.async_api import async_playwright
import os
import requests

# Variables de entorno desde GitHub Secrets
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# -------- Función para enviar alertas a Telegram --------
async def enviar_alerta_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": mensaje}
    response = requests.post(url, data=data)
    if response.status_code != 200:
        print(f"Error enviando mensaje Telegram: {response.text}")

# -------- Scraping para Skyscanner --------
async def scrape_precio_skyscanner(pagina):
    try:
        # Esperar que aparezcan precios en los resultados
        await pagina.wait_for_selector('div[data-testid="price"]', timeout=45000)
        precio_elemento = await pagina.query_selector('div[data-testid="price"]')
        precio_texto = await precio_elemento.inner_text()

        # Convertir texto a número eliminando caracteres que no sean dígitos
        precio_num = int("".join(filter(str.isdigit, precio_texto)))
        return precio_num
    except Exception as e:
        print(f"Error scraping Skyscanner: {e}")
        return None

# -------- Revisión de vuelo --------
async def revisar_vuelo(origen, destino, fecha):
    fecha_formato = fecha.replace("-", "")[2:]  # 2025-09-10 -> 250910
    url = f"https://www.skyscanner.com/transport/flights/{origen.lower()}/{destino.lower()}/{fecha_formato}/"

    async with async_playwright() as p:
        navegador = await p.chromium.launch(headless=True)
        pagina = await navegador.new_page()

        # User-Agent para evitar bloqueos básicos
        await pagina.set_user_agent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )

        await pagina.goto(url)

        # Scraping de precio
        precio = await scrape_precio_skyscanner(pagina)

        await navegador.close()
        return precio, url

# -------- Main --------
async def main():
    ORIGENES = ["EZE", "SCL"]       # Ezeiza y Santiago de Chile
    DESTINOS = ["ICN", "GMP"]       # Seúl Incheon y Gimpo
    FECHAS = ["2025-09-10", "2025-09-15", "2025-09-20"]
    PRECIO_UMBRAL = 1000  # USD

    for origen in ORIGENES:
        for destino in DESTINOS:
            for fecha in FECHAS:
                precio, url = await revisar_vuelo(origen, destino, fecha)
                if precio is None:
                    print(f"No se pudo obtener precio para {origen}-{destino} {fecha}")
                else:
                    print(f"[{origen} - {destino} - {fecha}] Precio más bajo: ${precio}")
                    if precio < PRECIO_UMBRAL:
                        mensaje = (
                            f"🔥 Oferta detectada: {origen} → {destino}\n"
                            f"Fecha: {fecha}\nPrecio: ${precio}\n{url}"
                        )
                        await enviar_alerta_telegram(mensaje)

if __name__ == "__main__":
    asyncio.run(main())
