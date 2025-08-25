import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import Config

logger = logging.getLogger(__name__)

class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self):
        self.db_path = Config.DATABASE_URL
        self.connection = None
        
    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        self.connection = await aiosqlite.connect(self.db_path)
        
        # Включаем поддержку foreign keys
        await self.connection.execute("PRAGMA foreign_keys = ON")
        
        # Создание таблиц
        await self._create_tables()
        await self.connection.commit()
        
        logger.info("База данных инициализирована")
        
    async def _create_tables(self):
        """Создание всех необходимых таблиц"""
        
        # Таблица соединений
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server1_id INTEGER NOT NULL,
                channel1_id INTEGER NOT NULL,
                server2_id INTEGER NOT NULL,
                channel2_id INTEGER NOT NULL,
                connection_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                description TEXT
            )
        ''')
        
        # Таблица истории сообщений
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_message_id INTEGER NOT NULL,
                forwarded_message_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                connection_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content_hash TEXT,
                FOREIGN KEY (connection_id) REFERENCES connections (id)
            )
        ''')
        
        # Таблица настроек серверов
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS server_settings (
                server_id INTEGER PRIMARY KEY,
                prefix TEXT DEFAULT '!',
                enabled BOOLEAN DEFAULT TRUE,
                mod_role_id INTEGER,
                log_channel_id INTEGER,
                spam_protection BOOLEAN DEFAULT TRUE,
                profanity_filter BOOLEAN DEFAULT TRUE,
                auto_delete_commands BOOLEAN DEFAULT FALSE,
                webhook_notifications BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица спам-защиты
        await self.connection.execute('''
            CREATE TABLE IF NOT EXISTS spam_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                server_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_count INTEGER DEFAULT 1,
                first_message_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_blocked BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # Создание индексов для оптимизации
        await self.connection.execute('''
            CREATE INDEX IF NOT EXISTS idx_connections_active 
            ON connections (is_active)
        ''')
        
        await self.connection.execute('''
            CREATE INDEX IF NOT EXISTS idx_connections_channels 
            ON connections (channel1_id, channel2_id)
        ''')
        
        await self.connection.execute('''
            CREATE INDEX IF NOT EXISTS idx_message_history_connection 
            ON message_history (connection_id)
        ''')
        
        await self.connection.execute('''
            CREATE INDEX IF NOT EXISTS idx_spam_tracking_user 
            ON spam_tracking (user_id, server_id)
        ''')
    
    # === МЕТОДЫ ДЛЯ СОЕДИНЕНИЙ ===
    
    async def create_connection(self, server1_id: int, channel1_id: int, 
                              server2_id: int, channel2_id: int, 
                              name: str, created_by: int, description: str = None) -> int:
        """Создание нового соединения"""
        cursor = await self.connection.execute('''
            INSERT INTO connections 
            (server1_id, channel1_id, server2_id, channel2_id, connection_name, created_by, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (server1_id, channel1_id, server2_id, channel2_id, name, created_by, description))
        
        await self.connection.commit()
        return cursor.lastrowid
    
    async def get_connection_by_id(self, connection_id: int) -> Optional[Dict[str, Any]]:
        """Получение соединения по ID"""
        cursor = await self.connection.execute('''
            SELECT * FROM connections WHERE id = ? AND is_active = TRUE
        ''', (connection_id,))
        
        row = await cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return None
    
    async def get_connections_by_channel(self, channel_id: int) -> List[Dict[str, Any]]:
        """Получение всех соединений для канала"""
        cursor = await self.connection.execute('''
            SELECT * FROM connections 
            WHERE (channel1_id = ? OR channel2_id = ?) AND is_active = TRUE
        ''', (channel_id, channel_id))
        
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def get_all_connections(self, server_id: int = None) -> List[Dict[str, Any]]:
        """Получение всех соединений (опционально для конкретного сервера)"""
        if server_id:
            cursor = await self.connection.execute('''
                SELECT * FROM connections 
                WHERE (server1_id = ? OR server2_id = ?) AND is_active = TRUE
                ORDER BY created_at DESC
            ''', (server_id, server_id))
        else:
            cursor = await self.connection.execute('''
                SELECT * FROM connections WHERE is_active = TRUE ORDER BY created_at DESC
            ''')
        
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def delete_connection(self, connection_id: int) -> bool:
        """Удаление соединения (мягкое удаление)"""
        cursor = await self.connection.execute('''
            UPDATE connections SET is_active = FALSE WHERE id = ?
        ''', (connection_id,))
        
        await self.connection.commit()
        return cursor.rowcount > 0
    
    async def get_server_connection_count(self, server_id: int) -> int:
        """Подсчет активных соединений сервера"""
        cursor = await self.connection.execute('''
            SELECT COUNT(*) FROM connections 
            WHERE (server1_id = ? OR server2_id = ?) AND is_active = TRUE
        ''', (server_id, server_id))
        
        result = await cursor.fetchone()
        return result[0] if result else 0
    
    # === МЕТОДЫ ДЛЯ ИСТОРИИ СООБЩЕНИЙ ===
    
    async def log_message(self, original_msg_id: int, forwarded_msg_id: int, 
                         author_id: int, connection_id: int, content_hash: str = None):
        """Логирование пересланного сообщения"""
        await self.connection.execute('''
            INSERT INTO message_history 
            (original_message_id, forwarded_message_id, author_id, connection_id, content_hash)
            VALUES (?, ?, ?, ?, ?)
        ''', (original_msg_id, forwarded_msg_id, author_id, connection_id, content_hash))
        
        await self.connection.commit()
    
    async def get_message_stats(self, connection_id: int = None, days: int = 7) -> Dict[str, Any]:
        """Получение статистики сообщений"""
        if connection_id:
            cursor = await self.connection.execute('''
                SELECT COUNT(*) as total_messages,
                       COUNT(DISTINCT author_id) as unique_users
                FROM message_history 
                WHERE connection_id = ? AND timestamp >= datetime('now', '-{} days')
            '''.format(days), (connection_id,))
        else:
            cursor = await self.connection.execute('''
                SELECT COUNT(*) as total_messages,
                       COUNT(DISTINCT author_id) as unique_users,
                       COUNT(DISTINCT connection_id) as active_connections
                FROM message_history 
                WHERE timestamp >= datetime('now', '-{} days')
            '''.format(days))
        
        result = await cursor.fetchone()
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, result)) if result else {}
    
    # === МЕТОДЫ ДЛЯ НАСТРОЕК СЕРВЕРОВ ===
    
    async def create_server_settings(self, server_id: int):
        """Создание настроек сервера по умолчанию"""
        await self.connection.execute('''
            INSERT OR IGNORE INTO server_settings (server_id) VALUES (?)
        ''', (server_id,))
        
        await self.connection.commit()
    
    async def get_server_settings(self, server_id: int) -> Dict[str, Any]:
        """Получение настроек сервера"""
        cursor = await self.connection.execute('''
            SELECT * FROM server_settings WHERE server_id = ?
        ''', (server_id,))
        
        row = await cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        
        # Если настроек нет, создаем их
        await self.create_server_settings(server_id)
        return await self.get_server_settings(server_id)
    
    async def update_server_setting(self, server_id: int, setting: str, value: Any):
        """Обновление настройки сервера"""
        await self.connection.execute(f'''
            UPDATE server_settings 
            SET {setting} = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE server_id = ?
        ''', (value, server_id))
        
        await self.connection.commit()
    
    # === МЕТОДЫ ДЛЯ СПАМ-ЗАЩИТЫ ===
    
    async def track_message_spam(self, user_id: int, server_id: int, channel_id: int):
        """Отслеживание сообщений для спам-защиты"""
        # Получаем или создаем запись отслеживания
        cursor = await self.connection.execute('''
            SELECT * FROM spam_tracking 
            WHERE user_id = ? AND server_id = ? AND channel_id = ?
            AND datetime(last_message_time, '+{} seconds') > datetime('now')
        '''.format(Config.SPAM_TIME_WINDOW), (user_id, server_id, channel_id))
        
        existing = await cursor.fetchone()
        
        if existing:
            # Обновляем существующую запись
            new_count = existing[4] + 1  # message_count
            await self.connection.execute('''
                UPDATE spam_tracking 
                SET message_count = ?, last_message_time = CURRENT_TIMESTAMP,
                    is_blocked = CASE WHEN ? >= ? THEN TRUE ELSE FALSE END
                WHERE user_id = ? AND server_id = ? AND channel_id = ?
            ''', (new_count, new_count, Config.SPAM_THRESHOLD, user_id, server_id, channel_id))
        else:
            # Создаем новую запись
            await self.connection.execute('''
                INSERT OR REPLACE INTO spam_tracking 
                (user_id, server_id, channel_id, message_count, first_message_time, last_message_time)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (user_id, server_id, channel_id))
        
        await self.connection.commit()
        
        # Возвращаем текущий счетчик
        cursor = await self.connection.execute('''
            SELECT message_count, is_blocked FROM spam_tracking 
            WHERE user_id = ? AND server_id = ? AND channel_id = ?
        ''', (user_id, server_id, channel_id))
        
        result = await cursor.fetchone()
        return result if result else (1, False)
    
    async def is_user_spam_blocked(self, user_id: int, server_id: int, channel_id: int) -> bool:
        """Проверка, заблокирован ли пользователь за спам"""
        cursor = await self.connection.execute('''
            SELECT is_blocked FROM spam_tracking 
            WHERE user_id = ? AND server_id = ? AND channel_id = ?
            AND datetime(last_message_time, '+{} seconds') > datetime('now')
        '''.format(Config.SPAM_TIME_WINDOW), (user_id, server_id, channel_id))
        
        result = await cursor.fetchone()
        return result[0] if result else False
    
    # === СЛУЖЕБНЫЕ МЕТОДЫ ===
    
    async def deactivate_server_connections(self, server_id: int):
        """Деактивация всех соединений сервера"""
        await self.connection.execute('''
            UPDATE connections SET is_active = FALSE 
            WHERE server1_id = ? OR server2_id = ?
        ''', (server_id, server_id))
        
        await self.connection.commit()
    
    async def cleanup_old_data(self, days: int = 30):
        """Очистка старых данных"""
        # Удаляем старые записи спам-отслеживания
        await self.connection.execute('''
            DELETE FROM spam_tracking 
            WHERE datetime(last_message_time, '+{} days') < datetime('now')
        '''.format(days))
        
        # Удаляем старую историю сообщений (если нужно)
        # await self.connection.execute('''
        #     DELETE FROM message_history 
        #     WHERE datetime(timestamp, '+{} days') < datetime('now')
        # '''.format(days))
        
        await self.connection.commit()
    
    async def get_database_stats(self) -> Dict[str, int]:
        """Получение общей статистики базы данных"""
        stats = {}
        
        # Количество соединений
        cursor = await self.connection.execute('SELECT COUNT(*) FROM connections WHERE is_active = TRUE')
        stats['active_connections'] = (await cursor.fetchone())[0]
        
        # Количество сообщений
        cursor = await self.connection.execute('SELECT COUNT(*) FROM message_history')
        stats['total_messages'] = (await cursor.fetchone())[0]
        
        # Количество серверов
        cursor = await self.connection.execute('SELECT COUNT(*) FROM server_settings')
        stats['total_servers'] = (await cursor.fetchone())[0]
        
        return stats
    
    async def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection:
            await self.connection.close()
            logger.info("Соединение с базой данных закрыто")