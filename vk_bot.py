import logging
import os
import random

import redis
import vk_api
from dotenv import load_dotenv
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkEventType, VkLongPoll

from logging_utils import setup_logging
from tools import load_quiz_data, send_new_question_vk


logger = logging.getLogger(__name__)


QUIZ_DATA = load_quiz_data()


def send_message(api, user_id, text, keyboard=None):
    params = {
        'user_id': user_id,
        'message': text,
        'random_id': random.randint(1, 1000),
    }
    if keyboard is not None:
        params['keyboard'] = keyboard.get_keyboard()
    api.messages.send(**params)


def handle_new_question(api, user_id, keyboard, redis_client):
    send_new_question_vk(api, user_id, QUIZ_DATA, redis_client, keyboard, send_message)


def handle_solution_attempt(api, user_id, text, keyboard, redis_client):
    saved = redis_client.get(f"quiz:{user_id}")

    logger.info("В Redis по id %s лежит: %s", user_id, saved)

    if saved is None:
        send_message(api, user_id, "Нажмите «Новый вопрос».", keyboard)
        return

    if text.strip().lower() == saved.strip().lower():
        send_message(api, user_id, "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»", keyboard)
        redis_client.incr(f"quiz:score:{user_id}")
        redis_client.delete(f"quiz:{user_id}")
    else:
        send_message(api, user_id, "Неправильно… Попробуешь ещё раз?", keyboard)


def handle_give_up(api, user_id, keyboard, redis_client):
    saved_answer = redis_client.get(f"quiz:{user_id}")

    if saved_answer is None:
        send_message(api, user_id, "У вас нет активного вопроса. Нажмите «Новый вопрос».", keyboard)
        return
    send_message(api, user_id, f"Правильный ответ: {saved_answer}", keyboard)
    redis_client.delete(f"quiz:{user_id}")

    send_new_question_vk(api, user_id, QUIZ_DATA, redis_client, keyboard, send_message)


def handle_get_score(api, user_id, keyboard, redis_client):
    score = redis_client.get(f"quiz:score:{user_id}") or 0
    send_message(api, user_id, f"Твой счёт: {score}", keyboard)


def handle_message(api, user_id, text, keyboard, redis_client):
    if text == 'Новый вопрос':
        handle_new_question(api, user_id, keyboard, redis_client)
    elif text == 'Сдаться':
        handle_give_up(api, user_id, keyboard, redis_client)
    elif text == 'Мой счёт':
        handle_get_score(api, user_id, keyboard, redis_client)
    else:
        handle_solution_attempt(api, user_id, text, keyboard, redis_client)


def main():
    load_dotenv()

    tg_token = os.environ['TG_BOT_TOKEN']
    tg_chat_id = os.environ['TG_CHAT_ID']
    vk_token = os.environ['VK_TOKEN']

    setup_logging(tg_token, tg_chat_id)

    redis_client = redis.Redis(
        host=os.environ.get('REDIS_HOST'),
        port=int(os.environ.get('REDIS_PORT', 16261)),
        password=os.environ.get('REDIS_PASSWORD'),
        decode_responses=True
    )

    vk_session = vk_api.VkApi(token=vk_token)
    api = vk_session.get_api()

    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('Новый вопрос', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('Сдаться', color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button('Мой счёт', color=VkKeyboardColor.SECONDARY)

    longpoll = VkLongPoll(vk_session)

    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            text = event.text
            handle_message(api, user_id, text, keyboard, redis_client)


if __name__ == "__main__":
    main()
