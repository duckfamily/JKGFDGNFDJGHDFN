import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Класс конфигурации бота"""
    
    # Основные настройки
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    PREFIX = os.getenv('PREFIX', '!')
    
    # База данных
    DATABASE_URL = os.getenv('DATABASE_URL', 'interserver_bot.db')
    
    # Модерация
    ENABLE_PROFANITY_FILTER = os.getenv('ENABLE_PROFANITY_FILTER', 'true').lower() == 'true'
    ENABLE_SPAM_PROTECTION = os.getenv('ENABLE_SPAM_PROTECTION', 'true').lower() == 'true'
    SPAM_THRESHOLD = int(os.getenv('SPAM_THRESHOLD', '5'))
    SPAM_TIME_WINDOW = int(os.getenv('SPAM_TIME_WINDOW', '10'))  # секунды
    
    # Ограничения
    MAX_MESSAGE_LENGTH = int(os.getenv('MAX_MESSAGE_LENGTH', '2000'))
    MAX_CONNECTIONS_PER_SERVER = int(os.getenv('MAX_CONNECTIONS_PER_SERVER', '10'))
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '8388608'))  # 8 MB в байтах
    
    # Фильтрация контента
    BLOCKED_DOMAINS = [
        'bit.ly', 'tinyurl.com', 'grabify.link', 'iplogger.org',
        '2no.co', 'cutt.ly', 'discord.gift', 'discordnitro.info'
    ]
    
    # Нецензурная лексика (базовый список)
    PROFANITY_WORDS = [
        # Добавьте сюда слова, которые нужно фильтровать
        # Рекомендуется загружать из внешнего файла
    ]
    
    # Системные настройки
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    RETRY_DELAY = int(os.getenv('RETRY_DELAY', '1'))
    
    # Эмодзи для UI
    EMOJI = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
        'loading': '⏳',
        'link': '🔗',
        'server': '🏠',
        'channel': '📝',
        'user': '👤',
        'admin': '👑',
        'mod': '🛡️',
        'bot': '🤖',
        'stats': '📊',
        'settings': '⚙️',
        'trash': '🗑️'
    }
    
    # Цвета для embed
    COLORS = {
        'success': 0x00ff00,
        'error': 0xff0000,
        'warning': 0xffaa00,
        'info': 0x0099ff,
        'default': 0x7289da
    }
    
    # Проверка обязательных переменных
    @classmethod
    def validate(cls):
        """Проверка наличия обязательных переменных окружения"""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN не установлен")
            
        if errors:
            raise ValueError(f"Ошибки конфигурации: {', '.join(errors)}")
        
        return True

# Валидация конфигурации при импорте
try:
    Config.validate()
except ValueError as e:
    print(f"❌ {e}")
    exit(1)