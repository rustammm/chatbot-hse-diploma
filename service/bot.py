import telebot
import requests
import argparse
import logging


from client import ServiceRegistryClient

logger = logging.getLogger('TelegramBot')

class Bot:
    def __init__(self, token, service_registry_url):
        self.__chatbot_url = None
        registry = ServiceRegistryClient(None, service_registry_url, services_names='aggregator',
                                         callback=self.set_chatbot_url)
        registry.update_services()
        assert self.__chatbot_url, 'chatbot url has not been set'
        self.__bot = telebot.TeleBot(token)

    def set_chatbot_url(self, conf):
        logger.debug('Got conf from Service Registry %s', conf)
        self.__chatbot_url = conf[0]['url']

    def start(self):

        @self.__bot.message_handler(content_types=['text'])
        def get_text_messages(message):
            logger.debug('Got message %s', message)
            try:
                r = requests.post(self.__chatbot_url, json={'uid': str(message.from_user.id), 'query': message.text}).json()
                logger.debug('Got reply for %s, %s - %s', message.from_user.id, message.text, r)
                self.__bot.send_message(message.from_user.id, r['reply'])
            except Exception as e:
                logger.exception('Exception during getting answer, uid %s, text %s', message.from_user.id, message.text)
                self.__bot.send_message(message.from_user.id, "Что-то пошло не так :(")

        self.__bot.polling(none_stop=True, interval=0)

def main():
    parser = argparse.ArgumentParser('Telegrab chit-chat bot')
    parser.add_argument('--telegram_token')
    parser.add_argument('--service_registry_url')
    args = parser.parse_args()

    bot = Bot(args.telegram_token, args.service_registry_url)
    bot.start()


if __name__ == '__main__':
    main()
