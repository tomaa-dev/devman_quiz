import os

folder = "quiz-questions"
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

print(quiz_data)