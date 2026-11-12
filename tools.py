import os
import random

from telegram import Update


def load_quiz_data(folder="quiz-questions"):
    quiz_data = {}
    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        with open(filepath, "r", encoding="KOI8-R") as my_file:
            file_contents = my_file.read()
        blocks = file_contents.split("\n\n")

        question = None
        answer = None

        for block in blocks:
            block = block.strip()
            if block.startswith("Вопрос"):
                lines = block.split("\n")
                question = " ".join(lines[1:]).strip()
                answer = None

            elif block.startswith("Ответ"):
                lines = block.split("\n")
                answer = lines[1].strip()

                if question and answer:
                    quiz_data[question] = answer
                    question = None
                    answer = None

    return quiz_data


def send_new_question_tg(update, chat_id, quiz_data, r):
    question = random.choice(list(quiz_data.keys()))
    answer = quiz_data[question]

    r.set(f"quiz:{chat_id}", answer, ex=3600)
    update.message.reply_text(f"Вопрос:\n{question}")


def send_new_question_vk(api, user_id, quiz_data, r, keyboard, send_message):
    question = random.choice(list(quiz_data.keys()))
    answer = quiz_data[question]
    r.set(f"quiz:{user_id}", answer, ex=3600)
    send_message(api, user_id, f"Вопрос:\n{question}", keyboard)
