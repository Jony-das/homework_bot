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
    # filename='bot.log',
    format='%(asctime)s, %(levelname)s, %(message)s',
    encoding='UTF-8',
    stream=sys.stdout
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
        logging.error(f'Сообщение не отправлено {message}')
        raise Exception(f'Ошибка {error}')


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
        raise Exception(f'Код ошибки: {response.status_code}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if 'homeworks' not in response.keys():
        logging.error(response.keys())
        raise not isinstance('Отсутствует ключ homeworks в response')
    if not isinstance(response, dict):
        logging.error(response)
        raise TypeError('response не соответствует типу')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        logging.error(response)
        raise TypeError('homeworks не соответствует типу')
    if response.get('homeworks') is None:
        logging.error(response.get('homeworks'))
        raise KeyError('Список пустой')
    return homeworks


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работе."""
    if not isinstance(homework, dict):
        raise TypeError('Переменная не словарь')
    homework_status = homework('status')
    homework_name = homework('homework_name')
    if homework_name not in homework:
        logging.error('Отсутствует ключ homework_name в ответе API')
        raise KeyError('Отсутствует ключ homework_name в ответе API')
    if homework_status not in homework:
        logging.error('Отсутствует ключ homework_status в ответе API')
        raise KeyError('Отсутствует ключ status в ответе API')
    if not None and homework_status not in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        logging.error(f'Неожиданный статус работы: {homework_status}')
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    raise Exception(f'Неизвестный статус работы {homework_status}')


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    # timestamp: int = 1674806817
    timestamp = int(time.time())
    recent_status_homework = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if response.get('homework'):
                new_status = response.get('homework')[0]
                if recent_status_homework != new_status.get('status'):
                    recent_status_homework = new_status.get(
                        'status')
                    message = parse_status(recent_status_homework)
                    send_message(bot, message)
                else:
                    logging.debug('Нет новых статусов')
                    raise Exception(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
