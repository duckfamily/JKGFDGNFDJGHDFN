import discord
from discord.ext import commands
import asyncio
import hashlib
import logging
from typing import Optional, List
from config import Config
from utils.filters import ContentFilter
from utils.helpers import format_embed, get_webhook_for_channel, safe_send_message

logger = logging.getLogger(__name__)

class InterServer(commands.Cog):
    """Основной модуль межсерверного общения"""
    
    def __init__(self, bot):
        self.bot = bot
        self.content_filter = ContentFilter()
        
    @commands.group(name='connect', aliases=['conn'], invoke_without_command=True)
    async def connect(self, ctx):
        """Группа команд для управления соединениями"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🔗 Межсерверные соединения",
                description="Доступные команды для управления соединениями:",
                color=Config.COLORS['info']
            )
            
            embed.add_field(
                name="Создание соединения",
                value=f"`{Config.PREFIX}connect create <ID_канала> <название>`",
                inline=False
            )
            
            embed.add_field(
                name="Список соединений",
                value=f"`{Config.PREFIX}connect list`",
                inline=False
            )
            
            embed.add_field(
                name="Информация о соединении",
                value=f"`{Config.PREFIX}connect info <ID>`",
                inline=False
            )
            
            embed.add_field(
                name="Удаление соединения",
                value=f"`{Config.PREFIX}connect remove <ID>`",
                inline=False
            )
            
            embed.set_footer(text="Для создания соединения нужны права 'Управление каналами'")
            
            await ctx.send(embed=embed)
    
    @connect.command(name='create', aliases=['add', 'new'])
    @commands.has_permissions(manage_channels=True)
    async def create_connection(self, ctx, target_channel: discord.TextChannel, *, name: str):
        """Создание нового межсерверного соединения"""
        
        # Проверяем лимит соединений на сервере
        current_count = await self.bot.db.get_server_connection_count(ctx.guild.id)
        if current_count >= Config.MAX_CONNECTIONS_PER_SERVER:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Превышен лимит",
                description=f"На сервере уже создано максимальное количество соединений ({Config.MAX_CONNECTIONS_PER_SERVER})",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Проверяем, что каналы не на одном сервере
        if target_channel.guild.id == ctx.guild.id:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Ошибка",
                description="Нельзя создать соединение между каналами одного сервера",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Проверяем права бота в целевом канале
        bot_permissions = target_channel.permissions_for(target_channel.guild.me)
        required_perms = ['send_messages', 'embed_links', 'attach_files', 'read_message_history']
        missing_perms = [perm for perm in required_perms if not getattr(bot_permissions, perm)]
        
        if missing_perms:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Недостаточно прав в целевом канале",
                description=f"Боту не хватает прав в канале {target_channel.mention}:\n" + 
                           "\n".join([f"• {perm}" for perm in missing_perms]),
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Проверяем, что соединение уже не существует
        existing_connections = await self.bot.db.get_connections_by_channel(ctx.channel.id)
        for conn in existing_connections:
            if (conn['channel1_id'] == target_channel.id or conn['channel2_id'] == target_channel.id):
                embed = discord.Embed(
                    title=f"{Config.EMOJI['warning']} Соединение уже существует",
                    description=f"Между этими каналами уже есть активное соединение: **{conn['connection_name']}** (ID: {conn['id']})",
                    color=Config.COLORS['warning']
                )
                return await ctx.send(embed=embed)
        
        # Создаем соединение
        try:
            connection_id = await self.bot.db.create_connection(
                server1_id=ctx.guild.id,
                channel1_id=ctx.channel.id,
                server2_id=target_channel.guild.id,
                channel2_id=target_channel.id,
                name=name,
                created_by=ctx.author.id,
                description=f"Соединение между {ctx.guild.name} и {target_channel.guild.name}"
            )
            
            # Отправляем подтверждение в оба канала
            embed = discord.Embed(
                title=f"{Config.EMOJI['success']} Соединение создано!",
                description=f"**{name}** (ID: {connection_id})",
                color=Config.COLORS['success']
            )
            
            embed.add_field(
                name="Канал 1", 
                value=f"{ctx.channel.mention} ({ctx.guild.name})", 
                inline=True
            )
            embed.add_field(
                name="Канал 2", 
                value=f"{target_channel.mention} ({target_channel.guild.name})", 
                inline=True
            )
            embed.add_field(
                name="Создал", 
                value=ctx.author.mention, 
                inline=True
            )
            
            embed.set_footer(text="Сообщения теперь будут пересылаться между каналами")
            
            await ctx.send(embed=embed)
            
            # Уведомление в целевом канале
            notification_embed = embed.copy()
            notification_embed.title = f"{Config.EMOJI['link']} Новое соединение установлено!"
            await target_channel.send(embed=notification_embed)
            
            logger.info(f"Создано соединение {connection_id}: {ctx.guild.name}#{ctx.channel.name} <-> {target_channel.guild.name}#{target_channel.name}")
            
        except Exception as e:
            logger.error(f"Ошибка создания соединения: {e}")
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Ошибка создания соединения",
                description="Произошла ошибка при создании соединения. Попробуйте позже.",
                color=Config.COLORS['error']
            )
            await ctx.send(embed=embed)
    
    @connect.command(name='list', aliases=['ls', 'show'])
    async def list_connections(self, ctx, page: int = 1):
        """Список всех соединений сервера"""
        
        connections = await self.bot.db.get_all_connections(ctx.guild.id)
        
        if not connections:
            embed = discord.Embed(
                title=f"{Config.EMOJI['info']} Нет активных соединений",
                description="На этом сервере пока нет межсерверных соединений.",
                color=Config.COLORS['info']
            )
            embed.add_field(
                name="Создать соединение",
                value=f"`{Config.PREFIX}connect create <ID_канала> <название>`",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        # Пагинация
        per_page = 5
        total_pages = (len(connections) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_connections = connections[start_idx:end_idx]
        
        embed = discord.Embed(
            title=f"{Config.EMOJI['link']} Межсерверные соединения",
            description=f"Страница {page}/{total_pages} • Всего: {len(connections)}",
            color=Config.COLORS['info']
        )
        
        for conn in page_connections:
            # Получаем информацию о каналах
            channel1 = self.bot.get_channel(conn['channel1_id'])
            channel2 = self.bot.get_channel(conn['channel2_id'])
            
            channel1_info = f"#{channel1.name}" if channel1 else f"ID: {conn['channel1_id']} (недоступен)"
            channel2_info = f"#{channel2.name}" if channel2 else f"ID: {conn['channel2_id']} (недоступен)"
            
            # Определяем, какой канал локальный, какой удаленный
            if conn['channel1_id'] == ctx.channel.id or conn['server1_id'] == ctx.guild.id:
                local_channel = channel1_info
                remote_channel = f"{channel2_info} ({self.bot.get_guild(conn['server2_id']).name if self.bot.get_guild(conn['server2_id']) else 'Неизвестный сервер'})"
            else:
                local_channel = channel2_info
                remote_channel = f"{channel1_info} ({self.bot.get_guild(conn['server1_id']).name if self.bot.get_guild(conn['server1_id']) else 'Неизвестный сервер'})"
            
            embed.add_field(
                name=f"{Config.EMOJI['server']} {conn['connection_name']} (ID: {conn['id']})",
                value=f"**Локальный:** {local_channel}\n**Удаленный:** {remote_channel}",
                inline=False
            )
        
        if total_pages > 1:
            embed.set_footer(text=f"Используйте '{Config.PREFIX}connect list <страница>' для навигации")
        
        await ctx.send(embed=embed)
    
    @connect.command(name='info', aliases=['details'])
    async def connection_info(self, ctx, connection_id: int):
        """Подробная информация о соединении"""
        
        connection = await self.bot.db.get_connection_by_id(connection_id)
        
        if not connection:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Соединение не найдено",
                description=f"Соединение с ID {connection_id} не существует или неактивно.",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Проверяем, что пользователь имеет доступ к этому соединению
        if ctx.guild.id not in [connection['server1_id'], connection['server2_id']]:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Нет доступа",
                description="Вы можете просматривать только соединения своего сервера.",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Получаем информацию о каналах и серверах
        channel1 = self.bot.get_channel(connection['channel1_id'])
        channel2 = self.bot.get_channel(connection['channel2_id'])
        guild1 = self.bot.get_guild(connection['server1_id'])
        guild2 = self.bot.get_guild(connection['server2_id'])
        creator = self.bot.get_user(connection['created_by'])
        
        embed = discord.Embed(
            title=f"{Config.EMOJI['info']} {connection['connection_name']}",
            description=connection.get('description', 'Описание отсутствует'),
            color=Config.COLORS['info']
        )
        
        embed.add_field(
            name="ID соединения",
            value=connection['id'],
            inline=True
        )
        
        embed.add_field(
            name="Статус",
            value="🟢 Активно" if connection['is_active'] else "🔴 Неактивно",
            inline=True
        )
        
        embed.add_field(
            name="Создано",
            value=f"<t:{int(connection['created_at'].timestamp())}:R>" if hasattr(connection['created_at'], 'timestamp') else connection['created_at'],
            inline=True
        )
        
        embed.add_field(
            name="Сервер 1",
            value=f"**{guild1.name}** ({guild1.id})\n{channel1.mention if channel1 else f'ID: {connection[\"channel1_id\"]} (недоступен)'}",
            inline=True
        )
        
        embed.add_field(
            name="Сервер 2",
            value=f"**{guild2.name}** ({guild2.id})\n{channel2.mention if channel2 else f'ID: {connection[\"channel2_id\"]} (недоступен)'}",
            inline=True
        )
        
        embed.add_field(
            name="Создатель",
            value=creator.mention if creator else f"ID: {connection['created_by']}",
            inline=True
        )
        
        # Получаем статистику сообщений
        stats = await self.bot.db.get_message_stats(connection['id'])
        if stats:
            embed.add_field(
                name="Статистика (7 дней)",
                value=f"Сообщений: {stats.get('total_messages', 0)}\nПользователей: {stats.get('unique_users', 0)}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @connect.command(name='remove', aliases=['delete', 'rm'])
    @commands.has_permissions(manage_channels=True)
    async def remove_connection(self, ctx, connection_id: int):
        """Удаление межсерверного соединения"""
        
        connection = await self.bot.db.get_connection_by_id(connection_id)
        
        if not connection:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Соединение не найдено",
                description=f"Соединение с ID {connection_id} не существует или уже удалено.",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Проверяем права на удаление (создатель или администратор)
        if (connection['created_by'] != ctx.author.id and 
            not ctx.author.guild_permissions.administrator and
            ctx.guild.id not in [connection['server1_id'], connection['server2_id']]):
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Недостаточно прав",
                description="Удалять соединение может только его создатель или администратор сервера.",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Подтверждение удаления
        confirm_embed = discord.Embed(
            title=f"{Config.EMOJI['warning']} Подтверждение удаления",
            description=f"Вы уверены, что хотите удалить соединение **{connection['connection_name']}**?",
            color=Config.COLORS['warning']
        )
        confirm_embed.add_field(
            name="Будет удалено",
            value=f"Соединение между серверами {connection['server1_id']} и {connection['server2_id']}",
            inline=False
        )
        confirm_embed.set_footer(text="Нажмите ✅ для подтверждения или ❌ для отмены")
        
        message = await ctx.send(embed=confirm_embed)
        await message.add_reaction('✅')
        await message.add_reaction('❌')
        
        def check(reaction, user):
            return (user == ctx.author and 
                   str(reaction.emoji) in ['✅', '❌'] and 
                   reaction.message.id == message.id)
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == '✅':
                # Удаляем соединение
                success = await self.bot.db.delete_connection(connection_id)
                
                if success:
                    embed = discord.Embed(
                        title=f"{Config.EMOJI['success']} Соединение удалено",
                        description=f"Соединение **{connection['connection_name']}** успешно удалено.",
                        color=Config.COLORS['success']
                    )
                    
                    # Уведомляем второй канал
                    other_channel_id = (connection['channel2_id'] if connection['channel1_id'] == ctx.channel.id 
                                      else connection['channel1_id'])
                    other_channel = self.bot.get_channel(other_channel_id)
                    
                    if other_channel:
                        notification = discord.Embed(
                            title=f"{Config.EMOJI['info']} Соединение разорвано",
                            description=f"Соединение **{connection['connection_name']}** было удалено.",
                            color=Config.COLORS['info']
                        )
                        await other_channel.send(embed=notification)
                    
                    logger.info(f"Удалено соединение {connection_id} пользователем {ctx.author}")
                    
                else:
                    embed = discord.Embed(
                        title=f"{Config.EMOJI['error']} Ошибка удаления",
                        description="Не удалось удалить соединение. Попробуйте позже.",
                        color=Config.COLORS['error']
                    )
            else:
                embed = discord.Embed(
                    title=f"{Config.EMOJI['info']} Удаление отменено",
                    description="Соединение не было удалено.",
                    color=Config.COLORS['info']
                )
            
            await message.edit(embed=embed)
            await message.clear_reactions()
            
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title=f"{Config.EMOJI['warning']} Время истекло",
                description="Время подтверждения истекло. Соединение не удалено.",
                color=Config.COLORS['warning']
            )
            await message.edit(embed=embed)
            await message.clear_reactions()
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Обработка сообщений для межсерверной пересылки"""
        
        # Игнорируем сообщения ботов и системные сообщения
        if message.author.bot or message.type != discord.MessageType.default:
            return
            
        # Игнорируем команды
        if message.content.startswith(Config.PREFIX):
            return
        
        # Получаем настройки сервера
        server_settings = await self.bot.db.get_server_settings(message.guild.id)
        if not server_settings.get('enabled', True):
            return
        
        # Проверяем спам-защиту
        if server_settings.get('spam_protection', True):
            message_count, is_blocked = await self.bot.db.track_message_spam(
                message.author.id, message.guild.id, message.channel.id
            )
            
            if is_blocked:
                return  # Пользователь заблокирован за спам
        
        # Получаем соединения для этого канала
        connections = await self.bot.db.get_connections_by_channel(message.channel.id)
        
        if not connections:
            return
        
        # Фильтрация контента
        if server_settings.get('profanity_filter', True):
            if self.content_filter.contains_profanity(message.content):
                return
        
        if self.content_filter.contains_blocked_links(message.content):
            return
        
        # Обрабатываем каждое соединение
        for connection in connections:
            await self._forward_message(message, connection)
    
    async def _forward_message(self, original_message, connection):
        """Пересылка сообщения через соединение"""
        
        try:
            # Определяем целевой канал
            target_channel_id = (connection['channel2_id'] if connection['channel1_id'] == original_message.channel.id 
                               else connection['channel1_id'])
            target_channel = self.bot.get_channel(target_channel_id)
            
            if not target_channel:
                logger.warning(f"Целевой канал {target_channel_id} недоступен для соединения {connection['id']}")
                return
            
            # Проверяем права бота
            if not target_channel.permissions_for(target_channel.guild.me).send_messages:
                return
            
            # Создаем embed для пересылки
            embed = discord.Embed(
                description=original_message.content if original_message.content else "*Сообщение без текста*",
                color=Config.COLORS['default'],
                timestamp=original_message.created_at
            )
            
            # Информация об авторе
            embed.set_author(
                name=f"{original_message.author.display_name} ({original_message.guild.name})",
                icon_url=original_message.author.display_avatar.url
            )
            
            # Добавляем информацию о соединении
            embed.set_footer(text=f"Соединение: {connection['connection_name']} • ID: {connection['id']}")
            
            # Обработка прикрепленных файлов
            files = []
            if original_message.attachments:
                for attachment in original_message.attachments:
                    if attachment.size <= Config.MAX_FILE_SIZE:
                        try:
                            file_data = await attachment.read()
                            files.append(discord.File(
                                fp=io.BytesIO(file_data),
                                filename=attachment.filename
                            ))
                        except Exception as e:
                            logger.warning(f"Не удалось прочитать файл {attachment.filename}: {e}")
            
            # Отправляем сообщение
            forwarded_message = await target_channel.send(embed=embed, files=files)
            
            # Логируем пересланное сообщение
            content_hash = hashlib.md5(original_message.content.encode()).hexdigest() if original_message.content else None
            await self.bot.db.log_message(
                original_message.id,
                forwarded_message.id,
                original_message.author.id,
                connection['id'],
                content_hash
            )
            
        except discord.Forbidden:
            logger.warning(f"Нет прав для отправки сообщения в канал {target_channel_id}")
        except discord.HTTPException as e:
            logger.error(f"Ошибка HTTP при пересылке сообщения: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при пересылке сообщения: {e}")

    @commands.command(name='help')
    async def help_command(self, ctx):
        """Справка по командам бота"""
        
        embed = discord.Embed(
            title=f"{Config.EMOJI['bot']} InterServer Bot - Справка",
            description="Бот для межсерверного общения между Discord серверами",
            color=Config.COLORS['info']
        )
        
        embed.add_field(
            name="🔗 Управление соединениями",
            value=f"`{Config.PREFIX}connect create <ID_канала> <название>` - Создать соединение\n"
                  f"`{Config.PREFIX}connect list` - Список соединений\n"
                  f"`{Config.PREFIX}connect info <ID>` - Информация о соединении\n"
                  f"`{Config.PREFIX}connect remove <ID>` - Удалить соединение",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Администрирование",
            value=f"`{Config.PREFIX}admin settings` - Настройки сервера\n"
                  f"`{Config.PREFIX}admin stats` - Статистика бота\n"
                  f"`{Config.PREFIX}invite` - Пригласить бота",
            inline=False
        )
        
        embed.add_field(
            name="📋 Требования",
            value="• Для создания соединений: право **Управление каналами**\n"
                  "• Для настроек: право **Администратор**\n"
                  "• Бот должен быть добавлен на оба сервера",
            inline=False
        )
        
        embed.set_footer(text="Используйте команды без < > и указывайте реальные значения")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(InterServer(bot))