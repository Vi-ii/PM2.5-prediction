import aiohttp  # Асинхронная библиотека для работы с HTTP-запросами
import asyncio  # Модуль для асинхронного программирования
from aiogram import Bot, Dispatcher, types  # Библиотека для работы с Telegram API
from aiogram.types import Message  # Тип сообщений Telegram
from aiogram.filters import Command  # Фильтр для обработки команд

# Токен бота (скрыт для безопасности)
TOKEN = "***************************"

# Создание экземпляров бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()


async def get_coordinates(city):
    """
    Получает координаты города через OpenStreetMap Nominatim.

    :param city: Название города
    :return: Кортеж с широтой, долготой и названием найденного города или None, если город не найден
    """
    url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["name"]
            return None


async def get_weather(lat, lon):
    """
    Запрашивает текущую погоду через Open-Meteo.

    :param lat: Широта
    :param lon: Долгота
    :return: Словарь с данными о текущей погоде или None, если данные недоступны
    """
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data["current_weather"] if "current_weather" in data else None


async def get_quality(lat, lon):
    """
    Запрашивает качество воздуха (AQI и PM2.5) через IQAir.

    :param lat: Широта
    :param lon: Долгота
    :return: Кортеж с PM2.5, атмосферным давлением и влажностью или None, если данные недоступны
    """
    api_key = "*********************************"

    def aqi_to_pm25(aqi):
        """
        Конвертирует значение AQI в PM2.5 по стандартной таблице.

        :param aqi: Индекс качества воздуха (AQI)
        :return: Значение PM2.5
        """
        aqi_ranges = [
            (0, 50, 0.0, 9.0),  # Отличное
            (51, 100, 9.1, 35.4),  # Хорошее
            (101, 150, 35.5, 55.4),  # Умеренное
            (151, 200, 55.5, 125.4),  # Вредное для чувствительных групп
            (201, 300, 125.5, 225.4),  # Вредное
            (301, 400, 225.5, 350.4),  # Очень вредное
            (401, 500, 350.5, 500.4)  # Опасное
        ]
        for low_aqi, high_aqi, low_pm25, high_pm25 in aqi_ranges:
            if low_aqi <= aqi <= high_aqi:
                pm2_5 = low_pm25 + ((aqi - low_aqi) / (high_aqi - low_aqi)) * (high_pm25 - low_pm25)
                return round(pm2_5, 2)

    url = f'https://api.airvisual.com/v2/nearest_city?lat={lat}&lon={lon}&key={api_key}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            try:
                data = await response.json()
                pm2_5 = aqi_to_pm25(data['data']['current']['pollution']['aqius'])
                pr = data['data']['current']['weather']['pr']  # Атмосферное давление
                hu = data['data']['current']['weather']['hu']  # Влажность воздуха
            except:
                return None
            return pm2_5, pr, hu


async def get_elevation(lat, lon):
    """
    Запрашивает высоту над уровнем моря через Open-Elevation.

    :param lat: Широта
    :param lon: Долгота
    :return: Высота над уровнем моря или None, если данные недоступны
    """
    url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data["results"][0]["elevation"] if "results" in data else None


@dp.message(Command("start"))
async def start(message: Message):
    """
    Обработчик команды /start. Отправляет приветственное сообщение пользователю.
    """
    await message.answer("Привет! Напиши мне название города, и я скажу, какая там погода ☀️🌧️❄️")


@dp.message()
async def weather_request(message: Message):
    """
    Обработчик текстовых сообщений. Ищет город, получает погоду и качество воздуха, и отправляет ответ пользователю.
    """
    city = message.text.strip()  # Удаляем лишние пробелы
    coordinates = await get_coordinates(city)
    if not coordinates:
        await message.answer("Не могу найти этот город. Проверь название и попробуй снова! 😕")
        return

    lat, lon, found_location = coordinates
    weather = await get_weather(lat, lon)
    pm2_5_data = await get_quality(lat, lon)
    if not pm2_5_data:
        await message.answer(
            "Не удалось получить данные о качестве воздуха. Попробуй позже или в этом городе нет датчиков! 😕")
        return

    pm2_5, pr, hu = pm2_5_data
    elevation = await get_elevation(lat, lon)
    if not weather:
        await message.answer("Не удалось получить данные о погоде. Попробуй позже! 🤔")
        return

    # Оцениваем уровень загрязнённости PM2.5
    if pm2_5 < 12:
        pollution_status = "🟢 Чистый воздух"
    elif pm2_5 < 35:
        pollution_status = "🟡 Немного загрязнённый"
    elif pm2_5 < 55:
        pollution_status = "🟠 Загрязнённый, чувствительным людям осторожно!"
    elif pm2_5 < 150:
        pollution_status = "🔴 Вредный, лучше не выходить без маски!"
    else:
        pollution_status = "☠️ Очень вредный, оставайся дома!"

    response_text = (
        f"🌍 Погода в {found_location}:\n"
        f"🌡 Температура: {weather['temperature']}°C\n"
        f"💧 Влажность: {hu}%\n"
        f"💨 Ветер: {weather['windspeed']} км/ч\n"
        f"🧭 Направление ветра: {weather['winddirection']}°\n"
        f"💥 Атмосферное давление: {pr} мм рт. ст.\n"
        f"⛰ Высота над уровнем моря {round(elevation)} м\n\n"
        f"🌫 PM2.5 Загрязнение: {pm2_5} мкг/м³\n"
        f"{pollution_status}"
    )
    await message.answer(response_text)


async def main():
    """
    Главная функция. Запускает polling бота.
    """
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())  # Запускаем главную функцию



'''
get_coordinates(city) : Использует API OpenStreetMap для получения координат города.
get_weather(lat, lon) : Использует API Open-Meteo для получения данных о текущей погоде.
get_quality(lat, lon) : Использует API IQAir для получения данных о качестве воздуха (AQI и PM2.5).
get_elevation(lat, lon) : Использует API Open-Elevation для получения высоты над уровнем моря.
start(message: Message) : Обработчик команды /start, который отправляет приветственное сообщение.
weather_request(message: Message) : Обработчик текстовых сообщений, который запрашивает погоду и качество воздуха для указанного города.
main() : Запускает бота в режиме polling.

Использование

    Напишите /start, чтобы начать взаимодействие с ботом.

    Отправьте название города, и бот предоставит данные о погоде и качестве воздуха.

Примечания

    В случае ошибки API или отсутствия данных бот уведомляет пользователя.

    API-ключи необходимо получить и заменить в коде перед использованием.

    Асинхронные запросы обеспечивают высокую производительность работы бота.
'''