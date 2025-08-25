import discord
from discord.ext import commands
import logging
import asyncio
import os
from dotenv import load_dotenv
from database import Database
from config import Config

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class InterServerBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(
            command_prefix=Config.PREFIX,
            intents=intents,
            help_command=None
        )
        
        self.db = None
        
    async def setup_hook(self):
        """Инициализация бота при запуске"""
        logger.info("Инициализация бота...")
        
        # Инициализация базы данных
        self.db = Database()
        await self.db.init_db()
        
        # Загрузка cogs
        await self.load_extension('cogs.interserver')
        await self.load_extension('cogs.admin')
        
        logger.info("Бот успешно инициализирован!")
        
    async def on_ready(self):
        """Событие готовности бота"""
        logger.info(f'{self.user} подключен к Discord!')
        logger.info(f'Бот активен на {len(self.guilds)} серверах')
        
        # Устанавливаем статус
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} серверов | {Config.PREFIX}help"
        )
        await self.change_presence(activity=activity)
        
    async def on_guild_join(self, guild):
        """Событие присоединения к серверу"""
        logger.info(f"Бот добавлен на сервер: {guild.name} (ID: {guild.id})")
        
        # Создаем настройки сервера по умолчанию
        await self.db.create_server_settings(guild.id)
        
        # Обновляем статус
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} серверов | {Config.PREFIX}help"
        )
        await self.change_presence(activity=activity)
        
    async def on_guild_remove(self, guild):
        """Событие удаления с сервера"""
        logger.info(f"Бот удален с сервера: {guild.name} (ID: {guild.id})")
        
        # Деактивируем все соединения этого сервера
        await self.db.deactivate_server_connections(guild.id)
        
        # Обновляем статус
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} серверов | {Config.PREFIX}help"
        )
        await self.change_presence(activity=activity)
        
    async def on_command_error(self, ctx, error):
        """Обработка ошибок команд"""
        if isinstance(error, commands.CommandNotFound):
            return
            
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Недостаточно прав",
                description="У вас нет прав для выполнения этой команды.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=10)
            
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="❌ У бота недостаточно прав",
                description=f"Боту не хватает прав: {', '.join(error.missing_permissions)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=10)
            
        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                title="❌ Пользователь не найден",
                description="Указанный пользователь не найден на сервере.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=10)
            
        elif isinstance(error, commands.ChannelNotFound):
            embed = discord.Embed(
                title="❌ Канал не найден",
                description="Указанный канал не найден.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=10)
            
        else:
            logger.error(f"Необработанная ошибка команды: {error}")
            embed = discord.Embed(
                title="❌ Произошла ошибка",
                description="Произошла неожиданная ошибка. Попробуйте позже.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=10)

async def main():
    """Основная функция запуска бота"""
    bot = InterServerBot()
    
    try:
        await bot.start(Config.BOT_TOKEN)
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        if bot.db:
            await bot.db.close()
        await bot.close()
        logger.info("Бот остановлен.")

if __name__ == "__main__":
    asyncio.run(main())