import logging
import os
from enum import Enum

import redis
import telegram
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (CallbackContext, CommandHandler, ConversationHandler,
                          Filters, MessageHandler, Updater)

from tools import load_quiz_data, send_new_question_tg
from logging_utils import setup_logging


logger = logging.getLogger(__name__)


class State(Enum):
    NEW_QUESTION = 1
    SOLUTION = 2


QUIZ_DATA = load_quiz_data()


def start(update: Update, context: CallbackContext):
    custom_keyboard = [['Новый вопрос', 'Сдаться'], ['Мой счёт']]

    user = update.effective_user
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    update.message.reply_markdown_v2(
        fr'Hi {user.mention_markdown_v2()}\!',
        reply_markup=reply_markup,
    )

    return State.NEW_QUESTION


def handle_new_question_request(update: Update, context: CallbackContext):
    text = update.message.text
    chat_id = update.message.chat_id
    redis = context.bot_data['redis']

    if text == 'Новый вопрос':
        send_new_question_tg(update, chat_id, QUIZ_DATA, redis)
        return State.SOLUTION

    return State.NEW_QUESTION


def handle_solution_attempt(update: Update, context: CallbackContext):
    text = update.message.text
    chat_id = update.message.chat_id
    redis = context.bot_data['redis']

    saved = redis.get(f"quiz:{chat_id}")

    logger.info("В Redis по id %s лежит: %s", chat_id, saved)

    if saved is None:
        update.message.reply_text("Я не задавал вам вопрос, или время вышло. Нажмите «Новый вопрос».")
        return State.NEW_QUESTION

    if text.strip().lower() == saved.strip().lower():
        update.message.reply_text("Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»")
        redis.incr(f"quiz:score:{chat_id}")
        redis.delete(f"quiz:{chat_id}")
        return State.NEW_QUESTION
    else:
        update.message.reply_text("Неправильно… Попробуешь ещё раз?")
        return State.SOLUTION


def handle_give_up(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    redis = context.bot_data['redis']

    saved_answer = redis.get(f"quiz:{chat_id}")

    if saved_answer is None:
        update.message.reply_text("У вас нет активного вопроса. Нажмите «Новый вопрос».")
        return State.NEW_QUESTION

    update.message.reply_text(f"Правильный ответ: {saved_answer}")
    redis.delete(f"quiz:{chat_id}")

    send_new_question_tg(update, chat_id, QUIZ_DATA, redis)
    return State.SOLUTION


def handle_get_score(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    redis = context.bot_data['redis']

    score = redis.get(f"quiz:score:{chat_id}") or 0
    update.message.reply_text(f"Твой счёт: {score}")
    return State.NEW_QUESTION


def stop(update: Update, context: CallbackContext):
    update.message.reply_text("Чтобы начать заново, нажми /start.")
    return ConversationHandler.END


def error_handler(update: Update, context: CallbackContext):
    logger.error("Произошла ошибка:", exc_info=context.error)


def main():
    load_dotenv()

    tg_token = os.environ['TG_BOT_TOKEN']
    tg_chat_id = os.environ['TG_CHAT_ID']

    setup_logging(tg_token, tg_chat_id)

    redis_client = redis.Redis(
        host=os.environ.get('REDIS_HOST'),
        port=int(os.environ.get('REDIS_PORT', 16261)),
        password=os.environ.get('REDIS_PASSWORD'),
        decode_responses=True
    )

    updater = Updater(tg_token)
    dispatcher = updater.dispatcher

    dispatcher.bot_data['redis'] = redis_client

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(Filters.regex('^Новый вопрос$'), handle_new_question_request),
            MessageHandler(Filters.regex('^Сдаться$'), handle_give_up),
            MessageHandler(Filters.regex('^Мой счёт$'), handle_get_score),
        ],

        states={
            State.NEW_QUESTION: [
                MessageHandler(Filters.regex('^Сдаться$'), handle_give_up),
                MessageHandler(Filters.regex('^Мой счёт$'), handle_get_score),
                MessageHandler(
                    Filters.text & ~Filters.command,
                    handle_new_question_request
                ),
            ],
            State.SOLUTION: [
                MessageHandler(Filters.regex('^Новый вопрос$'), handle_new_question_request),
                MessageHandler(Filters.regex('^Сдаться$'), handle_give_up),
                MessageHandler(Filters.regex('^Мой счёт$'), handle_get_score),
                MessageHandler(
                    Filters.text & ~Filters.command,
                    handle_solution_attempt
                ),
            ]
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("stop", stop)],
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
