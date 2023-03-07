import logging
import os
import sys
import time
from http import HTTPStatus
from urllib import response

import requests
import telegram
from dotenv import load_dotenv
from telegram import TelegramError

from exceptions import APIError, HTTPStatusError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD: int = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        message = 'Нет информации из констант'
        logging.critical(message)
        sys.exit(message)


def send_message(bot, message):
    """Отправляет сообщение в Телеграм чат."""
    logging.info(f'Попытка отправки сообщения {message}')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError as error:
        logging.error(
            f'Сообщение не отправлено: {message}',
            error,
            exc_info=True
        )
    else:
        logging.debug(f'Сообщение отправлено {message}')


def get_api_answer(timestamp):
    """Делает запрос к endpoint API-сервиса, и получает ответ."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except requests.RequestException as error:
        raise APIError(f'API недоступно {error}, {payload}') from error
    if response.status_code != HTTPStatus.OK:
        raise HTTPStatusError(
            f'Неверный HTTPStatus: {response.status_code}',
            f'Текст ошибки: {response.text}'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('response не соответствует типу')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks в response')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('homeworks не соответствует типу')
    if not response.get('current_date'):
        raise KeyError('Отсутствует ключ current date в response')
    return homeworks


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работе."""
    if not isinstance(homework, dict):
        raise TypeError('Переменная не словарь')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    recent_status_homework = ''

    while True:
        try:
            homework_response = get_api_answer(timestamp)
            homeworks = check_response(homework_response)
            if not homeworks:
                logging.debug('Список работ пуст')
            message = parse_status(homeworks[0])
            if message == recent_status_homework:
                logging.debug('Нет новых статусов')
            else:
                send_message(bot, message)
                recent_status_homework = message
            timestamp = response.get('timestamp')
            break

        except Exception as error:
            send_message(bot, message)
            recent_status_homework = message
            message = f'Сбой в работе программы: {error}.'
            logging.error(message, exc_info=True)
            break

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s',
        stream=sys.stdout
    )
    main()
