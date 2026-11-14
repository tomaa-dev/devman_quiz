import logging

import telegram


class MyLogsHandler(logging.Handler):
    def __init__(self, bot, chat_id):
        super().__init__()
        self.bot = bot
        self.chat_id = chat_id

    def emit(self, record):
        if record.name == 'telegram.ext.dispatcher' or record.name == 'MyLogsHandler':
            pass
        log_entry = self.format(record)
        try:
            self.bot.send_message(chat_id=self.chat_id, text=log_entry)
        except Exception:
            self.handleError(record)


def setup_logging(tg_token, chat_id):
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
    )

    bot = telegram.Bot(token=tg_token)

    handler = MyLogsHandler(bot, chat_id)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter('%(message)s'))

    logging.getLogger().addHandler(handler)
    logging.getLogger('telegram').addHandler(handler)

    return handler
