import re
import logging
from urllib.parse import urlparse
from config import Config

logger = logging.getLogger(__name__)

class ContentFilter:
    """Класс для фильтрации контента сообщений"""
    
    def __init__(self):
        # Компилируем регулярные выражения для оптимизации
        self.url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            re.IGNORECASE
        )
        
        self.mention_pattern = re.compile(r'@(everyone|here)', re.IGNORECASE)
        
        # Паттерны для обнаружения Discord токенов и других чувствительных данных
        self.token_pattern = re.compile(
            r'[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}|mfa\.[\w-]{84}',
            re.IGNORECASE
        )
        
        # Паттерны для Discord Nitro/подарочных ссылок (часто фальшивых)
        self.fake_nitro_pattern = re.compile(
            r'discord(?:\.(?:gift|nitro|app)|app\.com/gifts?)',
            re.IGNORECASE
        )
        
        # Паттерн для IP адресов (потенциальные IP-логгеры)
        self.ip_pattern = re.compile(
            r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        )
        
        # Подозрительные домены (IP-логгеры, скамы и т.д.)
        self.suspicious_domains = set(Config.BLOCKED_DOMAINS + [
            # Добавим дополнительные подозрительные домены
            'discordnitro.info', 'discord-nitro.org', 'discordgift.site',
            'steamcommunity-net.org', 'steemcommunity.org', 'stemcommunity.org',
            'grabify.link', 'iplogger.org', 'iplogger.com', 'iplogger.net',
            '2no.co', 'yip.su', 'iplis.ru', 'iplogger.co', 'ip-api.io',
            'bmwforum.co', 'leancoding.co', 'quickmessage.io', 'spottyfly.com'
        ])
    
    def contains_profanity(self, text: str) -> bool:
        """Проверка на наличие нецензурной лексики"""
        if not text or not Config.PROFANITY_WORDS:
            return False
            
        text_lower = text.lower()
        
        # Простая проверка на наличие слов из списка
        for word in Config.PROFANITY_WORDS:
            if word.lower() in text_lower:
                logger.info(f"Обнаружена нецензурная лексика: {word}")
                return True
        
        return False
    
    def contains_blocked_links(self, text: str) -> bool:
        """Проверка на наличие заблокированных ссылок"""
        if not text:
            return False
        
        urls = self.url_pattern.findall(text)
        
        for url in urls:
            if self._is_suspicious_url(url):
                logger.info(f"Обнаружена подозрительная ссылка: {url}")
                return True
        
        return False
    
    def _is_suspicious_url(self, url: str) -> bool:
        """Проверка подозрительности URL"""
        try:
            parsed = urlparse(url.lower())
            domain = parsed.netloc.lower()
            
            # Убираем www. префикс
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Проверяем домен в списке заблокированных
            if domain in self.suspicious_domains:
                return True
            
            # Проверяем поддомены заблокированных доменов
            for blocked_domain in self.suspicious_domains:
                if domain.endswith('.' + blocked_domain):
                    return True
            
            # Проверяем на подозрительные паттерны в URL
            full_url = url.lower()
            
            # Фальшивые Discord Nitro ссылки
            if self.fake_nitro_pattern.search(full_url):
                return True
            
            # IP адреса вместо доменов (подозрительно)
            if self.ip_pattern.search(domain):
                return True
            
            # Подозрительно короткие домены с цифрами
            if len(domain) < 6 and any(char.isdigit() for char in domain):
                return True
            
            # Подозрительные паттерны в пути URL
            path = parsed.path.lower()
            if any(pattern in path for pattern in ['/logger', '/grab', '/track', '/ip']):
                return True
                
        except Exception as e:
            logger.warning(f"Ошибка при анализе URL {url}: {e}")
            # В случае ошибки парсинга, считаем ссылку безопасной
            return False
        
        return False
    
    def contains_mass_mentions(self, text: str, threshold: int = 3) -> bool:
        """Проверка на массовые упоминания (@everyone/@here)"""
        if not text:
            return False
        
        mentions = self.mention_pattern.findall(text)
        return len(mentions) >= threshold
    
    def contains_discord_token(self, text: str) -> bool:
        """Проверка на наличие Discord токенов (защита от кражи аккаунтов)"""
        if not text:
            return False
        
        return bool(self.token_pattern.search(text))
    
    def is_spam_pattern(self, text: str) -> bool:
        """Проверка на спам-паттерны"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Паттерны спама
        spam_patterns = [
            r'(.)\1{10,}',  # Повторение одного символа 10+ раз
            r'(.{1,5})\1{5,}',  # Повторение короткой строки 5+ раз
            r'\b(free|бесплатн).*(nitro|discord)',  # Бесплатный nitro
            r'\b(win|выигра).*(money|деньг|приз)',  # Выиграть деньги
            r'\b(click|кликн|переход).*(link|ссылк)',  # Клик по ссылке
        ]
        
        for pattern in spam_patterns:
            if re.search(pattern, text_lower):
                logger.info(f"Обнаружен спам-паттерн: {pattern}")
                return True
        
        return False
    
    def filter_message(self, text: str, check_profanity: bool = True, 
                      check_links: bool = True, check_spam: bool = True,
                      check_tokens: bool = True) -> tuple[bool, list]:
        """
        Комплексная фильтрация сообщения
        Возвращает (is_allowed, reasons)
        """
        if not text:
            return True, []
        
        reasons = []
        
        if check_profanity and self.contains_profanity(text):
            reasons.append("Нецензурная лексика")
        
        if check_links and self.contains_blocked_links(text):
            reasons.append("Подозрительные ссылки")
        
        if check_spam and self.is_spam_pattern(text):
            reasons.append("Спам-паттерн")
        
        if self.contains_mass_mentions(text):
            reasons.append("Массовые упоминания")
        
        if check_tokens and self.contains_discord_token(text):
            reasons.append("Discord токен")
        
        is_allowed = len(reasons) == 0
        return is_allowed, reasons
    
    def clean_text(self, text: str, max_length: int = None) -> str:
        """Очистка и нормализация текста"""
        if not text:
            return text
        
        # Удаляем лишние пробелы и переносы строк
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # Обрезаем до максимальной длины
        if max_length and len(cleaned) > max_length:
            cleaned = cleaned[:max_length-3] + "..."
        
        return cleaned
    
    def extract_urls(self, text: str) -> list:
        """Извлечение всех URL из текста"""
        if not text:
            return []
        
        return self.url_pattern.findall(text)
    
    def remove_urls(self, text: str) -> str:
        """Удаление всех URL из текста"""
        if not text:
            return text
        
        return self.url_pattern.sub('[ссылка удалена]', text)
    
    def is_text_safe(self, text: str, strict: bool = False) -> bool:
        """
        Быстрая проверка безопасности текста
        strict=True включает более строгие проверки
        """
        if not text:
            return True
        
        is_allowed, reasons = self.filter_message(
            text,
            check_profanity=True,
            check_links=True,
            check_spam=strict,
            check_tokens=True
        )
        
        return is_allowed