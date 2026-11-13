import logging
import os
import random

import redis
import vk_api
from dotenv import load_dotenv
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.longpoll import VkEventType, VkLongPoll

from tools import load_quiz_data, send_new_question_vk


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


load_dotenv()


QUIZ_DATA = load_quiz_data()


r = redis.Redis(
    host=os.environ.get('REDIS_HOST'),
    port=int(os.environ.get('REDIS_PORT', 16261)),
    password=os.environ.get('REDIS_PASSWORD'),
    decode_responses=True
)


def send_message(api, user_id, text, keyboard=None):
    params = {
        'user_id': user_id,
        'message': text,
        'random_id': random.randint(1, 1000),
    }
    if keyboard is not None:
        params['keyboard'] = keyboard.get_keyboard()
    api.messages.send(**params)


def handle_new_question(api, user_id, keyboard):
    send_new_question_vk(api, user_id, QUIZ_DATA, r, keyboard, send_message)


def handle_solution_attempt(api, user_id, text, keyboard):
    saved = r.get(f"quiz:{user_id}")

    logger.info("В Redis по id %s лежит: %s", user_id, saved)

    if saved is None:
        send_message(api, user_id, "Нажмите «Новый вопрос».", keyboard)
        return

    if text.strip().lower() == saved.strip().lower():
        send_message(api, user_id, "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»", keyboard)
        r.incr(f"quiz:score:{user_id}")
        r.delete(f"quiz:{user_id}")
    else:
        send_message(api, user_id, "Неправильно… Попробуешь ещё раз?", keyboard)


def handle_give_up(api, user_id, keyboard):
    saved_answer = r.get(f"quiz:{user_id}")

    if saved_answer is None:
        send_message(api, user_id, "У вас нет активного вопроса. Нажмите «Новый вопрос».", keyboard)
        return
    send_message(api, user_id, f"Правильный ответ: {saved_answer}", keyboard)
    r.delete(f"quiz:{user_id}")

    send_new_question_vk(api, user_id, QUIZ_DATA, r, keyboard, send_message)


def handle_get_score(api, user_id, keyboard):
    score = r.get(f"quiz:score:{user_id}") or 0
    send_message(api, user_id, f"Твой счёт: {score}", keyboard)


def handle_message(api, user_id, text, keyboard):
    if text == 'Новый вопрос':
        handle_new_question(api, user_id, keyboard)
    elif text == 'Сдаться':
        handle_give_up(api, user_id, keyboard)
    elif text == 'Мой счёт':
        handle_get_score(api, user_id, keyboard)
    else:
        handle_solution_attempt(api, user_id, text, keyboard)


def main():
    vk_token = os.environ['VK_TOKEN']

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
            handle_message(api, user_id, text, keyboard)


if __name__ == "__main__":
    main()
