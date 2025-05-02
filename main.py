import os
import requests
import time
from datetime import datetime
import pytz
import json

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
CITY = 'Moscow'
EXCHANGE_API_URL = 'https://www.cbr-xml-daily.ru/daily_json.js'
CRYPTO_API_URL = 'https://api.coingecko.com/api/v3/simple/price'

SUBSCRIBERS_FILE = 'subscribers.json'

def get_keyboard_markup(is_subscribed):
    buttons = [
        [{'text': '📊 Получить данные'}],
        [{'text': '❌ Отписаться' if is_subscribed else '✅ Подписаться'}]
    ]
    return {
        'keyboard': buttons,
        'resize_keyboard': True,
        'one_time_keyboard': False
    }

def load_subscribers():
    try:
        with open(SUBSCRIBERS_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, 'w') as file:
        json.dump(subscribers, file)

def get_weather():
    url = f'https://api.openweathermap.org/data/2.5/weather'
    params = {
        'q': CITY,
        'appid': WEATHER_API_KEY,
        'units': 'metric',
        'lang': 'ru'
    }
    response = requests.get(url, params=params)
    data = response.json()
    if response.status_code == 200:
        return {
            'temp': round(data['main']['temp']),
            'feels_like': round(data['main']['feels_like']),
            'description': data['weather'][0]['description'],
            'humidity': data['main']['humidity'],
            'wind_speed': data['wind']['speed']
        }
    else:
        raise Exception(f"Error fetching weather: {data.get('message', 'Unknown error')}")

def get_weather_tip(weather):
    description = weather['description'].lower()
    temp = weather['temp']

    if 'дождь' in description:
        return "☔️ Не забудьте взять зонт!"
    elif 'снег' in description:
        return "Оденьтесь потеплее! 🧤"
    elif temp > 25:
        return "🧴 Не забудьте солнцезащитный крем!"
    elif temp < 0:
        return "🧣 Наденьте шапку и шарф!"
    return ""

def get_exchange_rates():
    response = requests.get(EXCHANGE_API_URL)
    data = response.json()
    if response.status_code == 200 and 'Valute' in data:
        return {
            'USD': round(data['Valute']['USD']['Value'], 2),
            'EUR': round(data['Valute']['EUR']['Value'], 2),
            'GBP': round(data['Valute']['GBP']['Value'], 2)
        }
    else:
        raise Exception("Error fetching exchange rates")

def get_crypto_prices():
    params = {
        'ids': 'bitcoin,ethereum,dogecoin,solana,sui',
        'vs_currencies': 'usd'
    }
    response = requests.get(CRYPTO_API_URL, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception("Error fetching crypto prices")

def get_news():
    try:
        url = f'https://newsapi.org/v2/top-headlines'
        params = {
            'country': 'ru',
            'apiKey': NEWS_API_KEY,
            'pageSize': 3
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()['articles']
        else:
            print(f"⚠️ News API error: {response.status_code}")
            return []
    except Exception as e:
        print(f"⚠️ Error fetching news: {str(e)}")
        return []

def get_current_data():
    weather = get_weather()
    exchange_rates = get_exchange_rates()
    crypto_prices = get_crypto_prices()
    news = get_news()

    greeting = "👋 Вот актуальные данные:"
    return format_message(weather, exchange_rates, crypto_prices, news, greeting)

def format_message(weather, exchange_rates, crypto_prices, news, greeting):
    weather_tip = get_weather_tip(weather)
    message = (
        f"{greeting}\n\n"
        f"🏙 Погода в Москве:\n"
        f"🌡 Температура: {weather['temp']}°C\n"
        f"🤔 Ощущается как: {weather['feels_like']}°C\n"
        f"💨 Ветер: {weather['wind_speed']} м/с\n"
        f"💧 Влажность: {weather['humidity']}%\n"
        f"☁️ Описание: {weather['description']}\n"
    )
    if weather_tip:
        message += f"💡 {weather_tip}\n"
    message += (
        f"\n💰 Курсы валют к рублю:\n"
        f"💵 USD: {exchange_rates['USD']} ₽\n"
        f"💶 EUR: {exchange_rates['EUR']} ₽\n"
        f"💷 GBP: {exchange_rates['GBP']} ₽\n"
        f"\n📈 Криптовалюты:\n"
        f"Bitcoin: ${crypto_prices['bitcoin']['usd']:.2f}\n"
        f"Ethereum: ${crypto_prices['ethereum']['usd']:.2f}\n"
        f"Dogecoin: ${crypto_prices['dogecoin']['usd']:.4f}\n"
        f"Solana: ${crypto_prices['solana']['usd']:.2f}\n"
        f"Sui: ${crypto_prices['sui']['usd']:.2f}\n"
    )
    if news:
        message += f"\n📰 Главные новости:\n"
        for article in news:
            message += f"• {article['title']}\n"
    return message

def send_telegram_message(chat_id, message, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    if keyboard:
        payload['reply_markup'] = keyboard
    response = requests.post(url, json=payload)
    return response.status_code == 200

last_request_times = {}
last_update_id = 0

def handle_updates():
    global last_update_id
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {'offset': last_update_id + 1}
    response = requests.get(url, params=params)
    updates = response.json().get('result', [])
    if updates:
        for update in updates:
            last_update_id = update['update_id']
            if 'message' not in update:
                continue
            chat_id = update['message']['chat']['id']
            text = update['message'].get('text', '').lower()
            subscribers = load_subscribers()
            is_subscribed = chat_id in subscribers
            if text == '/start':
                welcome = (
                    "👋 Добро пожаловать!\n"
                    "Я отправляю вам свежие данные: погоду, валюты, крипту и новости.\n"
                    "Выберите действие:"
                )
                send_telegram_message(chat_id, welcome, get_keyboard_markup(is_subscribed))
            elif text == '✅ подписаться':
                if not is_subscribed:
                    subscribers.append(chat_id)
                    save_subscribers(subscribers)
                    send_telegram_message(chat_id, "✅ Вы подписались", get_keyboard_markup(True))
            elif text == '❌ отписаться':
                if is_subscribed:
                    subscribers.remove(chat_id)
                    save_subscribers(subscribers)
                    send_telegram_message(chat_id, "❌ Вы отписались", get_keyboard_markup(False))
            elif text == '📊 получить данные':
                now = time.time()
                if chat_id in last_request_times and now - last_request_times[chat_id] < 5:
                    continue
                try:
                    data = get_current_data()
                    send_telegram_message(chat_id, data, get_keyboard_markup(is_subscribed))
                    last_request_times[chat_id] = now
                except:
                    send_telegram_message(chat_id, "⚠️ Ошибка получения данных", get_keyboard_markup(is_subscribed))

def main():
    tz = pytz.timezone('Europe/Moscow')
    last_sent_time = None
    while True:
        try:
            now = datetime.now(tz)
            handle_updates()
            times = ['00:00', '06:00', '08:00', '10:00', '17:00']
            now_str = now.strftime('%H:%M')
            if now_str in times and now_str != last_sent_time:
                msg = get_current_data()
                for user in load_subscribers():
                    send_telegram_message(user, msg, get_keyboard_markup(True))
                last_sent_time = now_str
            time.sleep(30)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(60)

if __name__ == '__main__':
    main()
