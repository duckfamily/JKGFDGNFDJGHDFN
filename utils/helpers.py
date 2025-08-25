import discord
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Union, List, Dict, Any
from config import Config
import aiohttp
import io

logger = logging.getLogger(__name__)

def format_embed(title: str, description: str = None, color: int = None, 
                emoji: str = None, **kwargs) -> discord.Embed:
    """Создание стандартизированного embed"""
    
    if emoji and title:
        title = f"{emoji} {title}"
    
    if not color:
        color = Config.COLORS.get('default', 0x7289da)
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        **kwargs
    )
    
    return embed

def format_user_info(user: Union[discord.User, discord.Member]) -> str:
    """Форматирование информации о пользователе"""
    if isinstance(user, discord.Member) and user.nick:
        return f"{user.nick} ({user.name}#{user.discriminator})"
    return f"{user.name}#{user.discriminator}"

def format_channel_info(channel: discord.TextChannel) -> str:
    """Форматирование информации о канале"""
    return f"#{channel.name} ({channel.guild.name})"

def format_time_delta(delta: timedelta) -> str:
    """Форматирование временной дельты в читаемый вид"""
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}м")
    if seconds or not parts:
        parts.append(f"{seconds}с")
    
    return " ".join(parts)

def format_file_size(bytes_size: int) -> str:
    """Форматирование размера файла"""
    for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} ТБ"

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Обрезание текста до указанной длины"""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def split_text(text: str, max_length: int = 2000) -> List[str]:
    """Разбивка длинного текста на части для Discord"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    for line in text.split('\n'):
        if len(current_part + line + '\n') > max_length:
            if current_part:
                parts.append(current_part.rstrip())
                current_part = ""
            
            # Если одна строка слишком длинная, разбиваем её
            while len(line) > max_length:
                parts.append(line[:max_length])
                line = line[max_length:]
            
            current_part = line + '\n' if line else ""
        else:
            current_part += line + '\n'
    
    if current_part:
        parts.append(current_part.rstrip())
    
    return parts

async def safe_send_message(channel: discord.TextChannel, content: str = None, 
                           embed: discord.Embed = None, file: discord.File = None,
                           delete_after: float = None) -> Optional[discord.Message]:
    """Безопасная отправка сообщения с обработкой ошибок"""
    try:
        return await channel.send(
            content=content, 
            embed=embed, 
            file=file,
            delete_after=delete_after
        )
    except discord.Forbidden:
        logger.warning(f"Нет прав для отправки сообщения в канал {channel.id}")
    except discord.HTTPException as e:
        logger.error(f"HTTP ошибка при отправке сообщения: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке сообщения: {e}")
    
    return None

async def safe_delete_message(message: discord.Message, delay: float = 0) -> bool:
    """Безопасное удаление сообщения"""
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        await message.delete()
        return True
    except discord.NotFound:
        pass  # Сообщение уже удалено
    except discord.Forbidden:
        logger.warning(f"Нет прав для удаления сообщения {message.id}")
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")
    
    return False

async def get_webhook_for_channel(channel: discord.TextChannel, name: str = "InterServer Bot") -> Optional[discord.Webhook]:
    """Получение или создание webhook для канала"""
    try:
        webhooks = await channel.webhooks()
        
        # Ищем существующий webhook бота
        for webhook in webhooks:
            if webhook.name == name:
                return webhook
        
        # Создаем новый webhook если нет
        if channel.permissions_for(channel.guild.me).manage_webhooks:
            return await channel.create_webhook(name=name, reason="Межсерверное общение")
            
    except discord.Forbidden:
        logger.warning(f"Нет прав для управления webhook в канале {channel.id}")
    except Exception as e:
        logger.error(f"Ошибка при работе с webhook: {e}")
    
    return None

async def send_via_webhook(webhook: discord.Webhook, content: str, 
                          username: str, avatar_url: str = None,
                          embed: discord.Embed = None, file: discord.File = None) -> Optional[discord.WebhookMessage]:
    """Отправка сообщения через webhook"""
    try:
        return await webhook.send(
            content=content,
            username=username,
            avatar_url=avatar_url,
            embed=embed,
            file=file,
            wait=True
        )
    except discord.HTTPException as e:
        logger.error(f"Ошибка при отправке через webhook: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка webhook: {e}")
    
    return None

def create_paginated_embed(items: List[str], title: str, per_page: int = 10, 
                          page: int = 1, color: int = None) -> discord.Embed:
    """Создание embed с пагинацией"""
    total_pages = (len(items) + per_page - 1) // per_page
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_items = items[start_idx:end_idx]
    
    embed = discord.Embed(
        title=title,
        description="\n".join(page_items) if page_items else "Нет элементов для отображения",
        color=color or Config.COLORS['info']
    )
    
    if total_pages > 1:
        embed.set_footer(text=f"Страница {page} из {total_pages}")
    
    return embed

def parse_duration(duration_str: str) -> Optional[int]:
    """Парсинг строки времени в секунды (например: '1h 30m', '2d', '45s')"""
    if not duration_str:
        return None
    
    duration_str = duration_str.lower().strip()
    
    # Регулярное выражение для парсинга времени
    import re
    pattern = r'(?:(\d+)\s*d(?:ays?)?)?(?:(\d+)\s*h(?:ours?)?)?(?:(\d+)\s*m(?:in(?:utes?)?)?)?(?:(\d+)\s*s(?:ec(?:onds?)?)?)?'
    match = re.match(pattern, duration_str)
    
    if not match:
        # Попробуем парсить как чистое число (секунды)
        try:
            return int(duration_str)
        except ValueError:
            return None
    
    days, hours, minutes, seconds = match.groups()
    
    total_seconds = 0
    if days:
        total_seconds += int(days) * 86400
    if hours:
        total_seconds += int(hours) * 3600
    if minutes:
        total_seconds += int(minutes) * 60
    if seconds:
        total_seconds += int(seconds)
    
    return total_seconds if total_seconds > 0 else None

def format_permissions(permissions: discord.Permissions) -> str:
    """Форматирование прав в читаемый вид"""
    perm_names = {
        'create_instant_invite': 'Создавать приглашения',
        'kick_members': 'Исключать участников',
        'ban_members': 'Банить участников',
        'administrator': 'Администратор',
        'manage_channels': 'Управлять каналами',
        'manage_guild': 'Управлять сервером',
        'add_reactions': 'Добавлять реакции',
        'view_audit_log': 'Просматривать аудит-лог',
        'priority_speaker': 'Приоритетный режим',
        'stream': 'Стримить',
        'read_messages': 'Читать сообщения',
        'send_messages': 'Отправлять сообщения',
        'send_tts_messages': 'Отправлять TTS',
        'manage_messages': 'Управлять сообщениями',
        'embed_links': 'Встраивать ссылки',
        'attach_files': 'Прикреплять файлы',
        'read_message_history': 'Читать историю',
        'mention_everyone': 'Упоминать всех',
        'external_emojis': 'Внешние эмодзи',
        'view_guild_insights': 'Статистика сервера',
        'connect': 'Подключаться',
        'speak': 'Говорить',
        'mute_members': 'Заглушать участников',
        'deafen_members': 'Отключать звук',
        'move_members': 'Перемещать участников',
        'use_voice_activation': 'Активация голосом',
        'change_nickname': 'Изменить ник',
        'manage_nicknames': 'Управлять никами',
        'manage_roles': 'Управлять ролями',
        'manage_webhooks': 'Управлять вебхуками',
        'manage_emojis': 'Управлять эмодзи'
    }
    
    active_perms = []
    for perm, value in permissions:
        if value and perm in perm_names:
            active_perms.append(perm_names[perm])
    
    return ', '.join(active_perms) if active_perms else 'Нет прав'

class RateLimiter:
    """Простой rate limiter для ограничения частоты действий"""
    
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = {}
    
    def is_allowed(self, key: str) -> bool:
        """Проверка, разрешено ли действие"""
        now = datetime.now()
        
        if key not in self.calls:
            self.calls[key] = []
        
        # Очищаем старые записи
        self.calls[key] = [
            call_time for call_time in self.calls[key]
            if (now - call_time).total_seconds() < self.time_window
        ]
        
        # Проверяем лимит
        if len(self.calls[key]) >= self.max_calls:
            return False
        
        # Добавляем новый вызов
        self.calls[key].append(now)
        return True
    
    def get_reset_time(self, key: str) -> Optional[datetime]:
        """Получение времени сброса лимита"""
        if key not in self.calls or not self.calls[key]:
            return None
        
        oldest_call = min(self.calls[key])
        return oldest_call + timedelta(seconds=self.time_window)

class MessageCache:
    """Кеш для хранения сообщений в памяти"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = {}
        self.access_times = {}
    
    def get(self, key: str) -> Any:
        """Получение элемента из кеша"""
        if key in self.cache:
            self.access_times[key] = datetime.now()
            return self.cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Добавление элемента в кеш"""
        # Если кеш переполнен, удаляем самый старый элемент
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.access_times.keys(), key=self.access_times.get)
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
        
        self.cache[key] = value
        self.access_times[key] = datetime.now()
    
    def delete(self, key: str) -> bool:
        """Удаление элемента из кеша"""
        if key in self.cache:
            del self.cache[key]
            del self.access_times[key]
            return True
        return False
    
    def clear(self) -> None:
        """Очистка кеша"""
        self.cache.clear()
        self.access_times.clear()
    
    def size(self) -> int:
        """Размер кеша"""
        return len(self.cache)

async def download_file(url: str, max_size: int = None) -> Optional[bytes]:
    """Скачивание файла по URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                
                if max_size and response.content_length and response.content_length > max_size:
                    return None
                
                data = await response.read()
                
                if max_size and len(data) > max_size:
                    return None
                
                return data
                
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла {url}: {e}")
        return None

def validate_channel_id(channel_id: str) -> Optional[int]:
    """Валидация ID канала"""
    try:
        channel_id_int = int(channel_id)
        # Discord snowflake должен быть в определенном диапазоне
        if 17 <= len(str(channel_id_int)) <= 19:
            return channel_id_int
    except ValueError:
        pass
    return None

def validate_user_id(user_id: str) -> Optional[int]:
    """Валидация ID пользователя"""
    return validate_channel_id(user_id)  # Используем ту же логику

def is_bot_owner(user_id: int) -> bool:
    """Проверка, является ли пользователь владельцем бота"""
    # Здесь можно добавить список ID владельцев
    owner_ids = []  # Добавьте сюда ID владельцев
    return user_id in owner_ids

def sanitize_filename(filename: str) -> str:
    """Очистка имени файла от недопустимых символов"""
    import re
    # Удаляем недопустимые символы
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Ограничиваем длину
    if len(sanitized) > 100:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        sanitized = name[:95] + ('.' + ext if ext else '')
    return sanitized

def create_progress_bar(current: int, total: int, length: int = 20) -> str:
    """Создание текстового прогресс-бара"""
    if total == 0:
        return "[" + "░" * length + "] 0%"
    
    filled = int(length * current / total)
    bar = "█" * filled + "░" * (length - filled)
    percentage = int(100 * current / total)
    
    return f"[{bar}] {percentage}%"

class AsyncContextManager:
    """Базовый класс для асинхронных контекстных менеджеров"""
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

def escape_markdown(text: str) -> str:
    """Экранирование Markdown символов"""
    if not text:
        return text
    
    markdown_chars = ['\\', '`', '*', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!']
    for char in markdown_chars:
        text = text.replace(char, '\\' + char)
    
    return text

def unescape_markdown(text: str) -> str:
    """Удаление экранирования Markdown символов"""
    if not text:
        return text
    
    markdown_chars = ['\\', '`', '*', '_', '{', '}', '[', ']', '(', ')', '#', '+', '-', '.', '!']
    for char in markdown_chars:
        text = text.replace('\\' + char, char)
    
    return text