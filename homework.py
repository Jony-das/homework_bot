import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from requests import exceptions

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    level=logging.DEBUG,
    filename='bot.log',
    format='%(asctime)s, %(levelname)s, %(message)s',
    encoding='UTF-8'
)

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
    if PRACTICUM_TOKEN is None:
        logging.critical('Нет practicum token')
        sys.exit()
    if TELEGRAM_TOKEN is None:
        logging.critical('Нет telegram token')
        sys.exit()
    if TELEGRAM_CHAT_ID is None:
        logging.critical('Нет telegram chat id')
        sys.exit()


def send_message(bot, message):
    """Отправляет сообщение в Телеграм чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Сообщение отправлено {message}')
    except Exception as error:
        logging.error(f'Сообщение не отправлено: {message}')
        raise Exception(f'Ошибка {error}') from error


def get_api_answer(timestamp):
    """Делает запрос к endpoint API-сервиса и получает ответ."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            logging.error(response.status_code)
            raise exceptions.InvalidResponseCod(
                f'Неверный HTTPStatus {response.status_code}'
            )
    except requests.RequestException as error:
        logging.error(f'Не удалось получить значение из константы {error}')
        raise Exception(f'Код ошибки: {response.status_code}') from error
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if 'homeworks' not in response:
        logging.error(response)
        raise not isinstance('Отсутствует ключ homeworks в response')
    if not isinstance(response, dict):
        logging.error(response)
        raise TypeError('response не соответствует типу')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        logging.error(homeworks)
        raise TypeError('homeworks не соответствует типу')
    if response.get('homeworks') is None:
        logging.error(response.get('homeworks'))
        raise KeyError('Список пустой')
    return homeworks


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работе."""
    if not isinstance(homework, dict):
        logging.error(homework)
        raise TypeError('Переменная не словарь')
    if 'homework_name' not in homework:
        logging.error('Отсутствует ключ homework_name в ответе API')
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        logging.error('Отсутствует ключ status в ответе API')
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        logging.error('Неожиданный статус работы')
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
            homework_status = parse_status(homeworks[0])
            if homework_status == recent_status_homework:
                logging.debug('Нет новых статусов')
            else:
                recent_status_homework = homework_status
                message = homework_status
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
