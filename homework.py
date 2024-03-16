import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram.error import TelegramError

from exceptions import HomeworkStatusError, KeyError, TokenError, URLError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    source = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    token_list = [key for key, value in source.items() if not value]
    if token_list:
        error_message = 'Предоставьте необходимые данные:{tokens}'
        logger.critical(error_message.format(tokens=token_list))
        return token_list


def send_message(bot, message):
    """Отправляет сообщение в Telegram."""
    logger.info('Отправка сообщения')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except TelegramError:
        logger.error('Ошибка отправки сообщения')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    logger.info(f'Запрос к {ENDPOINT} c {params}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise URLError(f'Сбой запроса к {ENDPOINT}')
        logger.info(f'Запрос к {ENDPOINT} c {params} выполнен успешно')
        return response.json()
    except requests.RequestException:
        raise ConnectionError(f'Сбой запроса к {ENDPOINT} c {params}')


def check_response(response):
    """Проверяет API-ответ на корректность."""
    logger.info('Проверка API-ответа')
    if not isinstance(response, dict):
        raise TypeError('Структура данных не соответствует заданной')
    if 'homeworks' not in response:
        raise KeyError('В API-ответе отсутствует ключ "homeworks"')
    if 'current_date' not in response:
        raise KeyError('В API-ответе отсутствует ключ "current_date"')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Полученная структура данных не '
                        'соответствует заданной')
    logger.info('Проверака API-ответа выполнена успешно')
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    logger.info('Проверка статуса домашней работы')
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Отсутствует ключ "homework_name"')
    status = homework.get('status')
    if not status:
        raise KeyError('Отсутствует ключ "status"')
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        raise HomeworkStatusError('Неизвестный статус проверки работы')
    logger.info('Успешная проверка статуса домашней работы')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens():
        raise ValueError('Отсутсвуют необходимые данные')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_message(bot, 'Привет!')
    start_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not homework:
                logger.debug('Отсутствует статус домашней работы')
            else:
                homework_status = parse_status(homework[0])
                send_message(bot, homework_status)
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            if start_error_message != message:
                send_message(bot, message)
                start_error_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        encoding='utf-8',
        format='%(asctime)s [%(levelname)s] [функция %(funcName)s '
               'стр.%(lineno)d] - %(message)s'
    )
    logging.StreamHandler(sys.stdout)
    main()
