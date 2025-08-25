import discord
from discord.ext import commands
import psutil
import logging
from datetime import datetime, timedelta
from config import Config

logger = logging.getLogger(__name__)

class Admin(commands.Cog):
    """Модуль команд администрирования"""
    
    def __init__(self, bot):
        self.bot = bot
        
    @commands.group(name='admin', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def admin(self, ctx):
        """Группа команд администрирования"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"{Config.EMOJI['admin']} Панель администратора",
                description="Доступные команды администрирования:",
                color=Config.COLORS['info']
            )
            
            embed.add_field(
                name="⚙️ Настройки",
                value=f"`{Config.PREFIX}admin settings` - Настройки сервера\n"
                      f"`{Config.PREFIX}admin set <параметр> <значение>` - Изменить настройку",
                inline=False
            )
            
            embed.add_field(
                name="📊 Статистика",
                value=f"`{Config.PREFIX}admin stats` - Общая статистика\n"
                      f"`{Config.PREFIX}admin serverstats` - Статистика сервера",
                inline=False
            )
            
            embed.add_field(
                name="🛠️ Обслуживание",
                value=f"`{Config.PREFIX}admin cleanup` - Очистка данных\n"
                      f"`{Config.PREFIX}admin test <ID>` - Тест соединения",
                inline=False
            )
            
            embed.set_footer(text="Команды доступны только администраторам")
            await ctx.send(embed=embed)
    
    @admin.command(name='stats')
    @commands.has_permissions(administrator=True)
    async def bot_stats(self, ctx):
        """Общая статистика бота"""
        
        # Получаем статистику из БД
        db_stats = await self.bot.db.get_database_stats()
        message_stats = await self.bot.db.get_message_stats()
        
        # Системная информация
        process = psutil.Process()
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        cpu_usage = process.cpu_percent()
        
        embed = discord.Embed(
            title=f"{Config.EMOJI['stats']} Статистика бота",
            color=Config.COLORS['info'],
            timestamp=datetime.utcnow()
        )
        
        # Основная статистика
        embed.add_field(
            name="🏠 Серверы и соединения",
            value=f"**Серверов:** {len(self.bot.guilds)}\n"
                  f"**Активных соединений:** {db_stats.get('active_connections', 0)}\n"
                  f"**Всего серверов в БД:** {db_stats.get('total_servers', 0)}",
            inline=True
        )
        
        # Статистика сообщений
        embed.add_field(
            name="📨 Сообщения",
            value=f"**За 7 дней:** {message_stats.get('total_messages', 0)}\n"
                  f"**Уникальных пользователей:** {message_stats.get('unique_users', 0)}\n"
                  f"**Всего в БД:** {db_stats.get('total_messages', 0)}",
            inline=True
        )
        
        # Системные ресурсы
        embed.add_field(
            name="💻 Система",
            value=f"**RAM:** {memory_usage:.1f} MB\n"
                  f"**CPU:** {cpu_usage:.1f}%\n"
                  f"**Пинг:** {round(self.bot.latency * 1000)} ms",
            inline=True
        )
        
        # Время работы
        uptime = datetime.utcnow() - self.bot.user.created_at
        embed.add_field(
            name="⏱️ Время работы",
            value=f"**Запущен:** <t:{int(process.create_time())}:R>\n"
                  f"**Аккаунт создан:** <t:{int(self.bot.user.created_at.timestamp())}:R>",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @admin.command(name='serverstats')
    @commands.has_permissions(administrator=True)
    async def server_stats(self, ctx):
        """Статистика текущего сервера"""
        
        # Статистика соединений
        connections = await self.bot.db.get_all_connections(ctx.guild.id)
        active_connections = len([c for c in connections if c['is_active']])
        
        # Статистика сообщений для соединений этого сервера
        total_messages = 0
        for connection in connections:
            stats = await self.bot.db.get_message_stats(connection['id'], days=30)
            total_messages += stats.get('total_messages', 0)
        
        embed = discord.Embed(
            title=f"{Config.EMOJI['server']} Статистика сервера",
            description=f"Статистика для **{ctx.guild.name}**",
            color=Config.COLORS['info']
        )
        
        embed.add_field(
            name="👥 Участники",
            value=f"**Всего:** {ctx.guild.member_count}\n"
                  f"**Людей:** {len([m for m in ctx.guild.members if not m.bot])}\n"
                  f"**Ботов:** {len([m for m in ctx.guild.members if m.bot])}",
            inline=True
        )
        
        embed.add_field(
            name="🔗 Соединения",
            value=f"**Активных:** {active_connections}\n"
                  f"**Лимит:** {Config.MAX_CONNECTIONS_PER_SERVER}\n"
                  f"**Свободно:** {Config.MAX_CONNECTIONS_PER_SERVER - active_connections}",
            inline=True
        )
        
        embed.add_field(
            name="📊 Активность",
            value=f"**Сообщений (30 дней):** {total_messages}\n"
                  f"**Каналов:** {len(ctx.guild.text_channels)}\n"
                  f"**Ролей:** {len(ctx.guild.roles)}",
            inline=True
        )
        
        # Топ соединений по активности
        if connections:
            top_connections = []
            for connection in connections[:3]:  # Топ 3
                stats = await self.bot.db.get_message_stats(connection['id'], days=7)
                messages = stats.get('total_messages', 0)
                top_connections.append(f"**{connection['connection_name']}**: {messages} сообщений")
            
            embed.add_field(
                name="🏆 Топ соединения (7 дней)",
                value="\n".join(top_connections) if top_connections else "Нет активности",
                inline=False
            )
        
        embed.set_footer(text=f"Сервер создан {ctx.guild.created_at.strftime('%d.%m.%Y')}")
        await ctx.send(embed=embed)
    
    @admin.command(name='cleanup')
    @commands.has_permissions(administrator=True)
    async def cleanup_data(self, ctx, days: int = 30):
        """Очистка старых данных из базы"""
        
        if days < 7:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Неверный параметр",
                description="Минимальный период для очистки - 7 дней.",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Подтверждение
        confirm_embed = discord.Embed(
            title=f"{Config.EMOJI['warning']} Подтверждение очистки",
            description=f"Будут удалены данные старше **{days} дней**:\n"
                       "• Записи спам-отслеживания\n"
                       "• Неактивные соединения\n\n"
                       "Продолжить?",
            color=Config.COLORS['warning']
        )
        
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
                await self.bot.db.cleanup_old_data(days)
                
                embed = discord.Embed(
                    title=f"{Config.EMOJI['success']} Очистка завершена",
                    description=f"Данные старше {days} дней успешно удалены.",
                    color=Config.COLORS['success']
                )
            else:
                embed = discord.Embed(
                    title=f"{Config.EMOJI['info']} Очистка отменена",
                    description="Данные не были удалены.",
                    color=Config.COLORS['info']
                )
            
            await message.edit(embed=embed)
            await message.clear_reactions()
            
        except:
            embed = discord.Embed(
                title=f"{Config.EMOJI['warning']} Время истекло",
                description="Очистка отменена из-за истечения времени.",
                color=Config.COLORS['warning']
            )
            await message.edit(embed=embed)
            await message.clear_reactions()
    
    @admin.command(name='test')
    @commands.has_permissions(administrator=True)
    async def test_connection(self, ctx, connection_id: int):
        """Тестирование соединения"""
        
        connection = await self.bot.db.get_connection_by_id(connection_id)
        
        if not connection:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Соединение не найдено",
                description=f"Соединение с ID {connection_id} не существует.",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Проверяем доступ
        if ctx.guild.id not in [connection['server1_id'], connection['server2_id']]:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Нет доступа",
                description="Вы можете тестировать только соединения своего сервера.",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"{Config.EMOJI['loading']} Тестирование соединения...",
            description=f"Проверка соединения **{connection['connection_name']}**",
            color=Config.COLORS['info']
        )
        message = await ctx.send(embed=embed)
        
        # Результаты тестов
        results = []
        
        # Тест 1: Доступность каналов
        channel1 = self.bot.get_channel(connection['channel1_id'])
        channel2 = self.bot.get_channel(connection['channel2_id'])
        
        if channel1 and channel2:
            results.append("✅ Оба канала доступны")
        elif channel1 or channel2:
            results.append("⚠️ Один из каналов недоступен")
        else:
            results.append("❌ Оба канала недоступны")
        
        # Тест 2: Права бота
        perms_ok = True
        if channel1:
            perms1 = channel1.permissions_for(channel1.guild.me)
            if not all([perms1.send_messages, perms1.embed_links, perms1.attach_files]):
                perms_ok = False
        
        if channel2:
            perms2 = channel2.permissions_for(channel2.guild.me)
            if not all([perms2.send_messages, perms2.embed_links, perms2.attach_files]):
                perms_ok = False
        
        if perms_ok:
            results.append("✅ Права бота в порядке")
        else:
            results.append("❌ Недостаточно прав бота")
        
        # Тест 3: Настройки серверов
        settings1 = await self.bot.db.get_server_settings(connection['server1_id'])
        settings2 = await self.bot.db.get_server_settings(connection['server2_id'])
        
        if settings1.get('enabled', True) and settings2.get('enabled', True):
            results.append("✅ Бот включен на обоих серверах")
        else:
            results.append("⚠️ Бот отключен на одном из серверов")
        
        # Тест 4: Статус соединения
        if connection['is_active']:
            results.append("✅ Соединение активно")
        else:
            results.append("❌ Соединение неактивно")
        
        # Обновляем сообщение с результатами
        embed = discord.Embed(
            title=f"{Config.EMOJI['info']} Результаты тестирования",
            description=f"Тест соединения **{connection['connection_name']}** (ID: {connection_id})",
            color=Config.COLORS['info']
        )
        
        embed.add_field(
            name="Результаты",
            value="\n".join(results),
            inline=False
        )
        
        if channel1:
            embed.add_field(
                name="Канал 1",
                value=f"{channel1.mention}\n{channel1.guild.name}",
                inline=True
            )
        
        if channel2:
            embed.add_field(
                name="Канал 2", 
                value=f"{channel2.mention}\n{channel2.guild.name}",
                inline=True
            )
        
        await message.edit(embed=embed)
    
    @commands.command(name='invite')
    async def invite_bot(self, ctx):
        """Получить ссылку для приглашения бота"""
        
        permissions = discord.Permissions(
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            manage_messages=True,
            add_reactions=True,
            use_external_emojis=True,
            view_channel=True,
            manage_webhooks=True
        )
        
        invite_url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissions,
            scopes=['bot', 'applications.commands']
        )
        
        embed = discord.Embed(
            title=f"{Config.EMOJI['bot']} Пригласить бота",
            description="Используйте эту ссылку для добавления бота на другие серверы:",
            color=Config.COLORS['info']
        )
        
        embed.add_field(
            name="Ссылка приглашения",
            value=f"[Добавить бота на сервер]({invite_url})",
            inline=False
        )
        
        embed.add_field(
            name="Необходимые права",
            value="• Отправка сообщений\n"
                  "• Встраивание ссылок\n"
                  "• Прикрепление файлов\n"
                  "• Чтение истории сообщений\n"
                  "• Управление сообщениями\n"
                  "• Добавление реакций\n"
                  "• Использование внешних эмодзи\n"
                  "• Просмотр каналов\n"
                  "• Управление вебхуками",
            inline=False
        )
        
        embed.set_footer(text="Бот должен быть добавлен на оба сервера для создания соединения")
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """Автоудаление команд если включено"""
        settings = await self.bot.db.get_server_settings(ctx.guild.id)
        
        if settings.get('auto_delete_commands', False):
            try:
                await ctx.message.delete()
            except:
                pass  # Игнорируем ошибки удаления

async def setup(bot):
    await bot.add_cog(Admin(bot))d=embed)
    
    @admin.command(name='settings')
    @commands.has_permissions(administrator=True)
    async def show_settings(self, ctx):
        """Показать текущие настройки сервера"""
        
        settings = await self.bot.db.get_server_settings(ctx.guild.id)
        
        embed = discord.Embed(
            title=f"{Config.EMOJI['settings']} Настройки сервера",
            description=f"Текущие настройки для **{ctx.guild.name}**",
            color=Config.COLORS['info']
        )
        
        # Основные настройки
        embed.add_field(
            name="Основные",
            value=f"**Префикс:** `{settings.get('prefix', Config.PREFIX)}`\n"
                  f"**Включен:** {'🟢 Да' if settings.get('enabled', True) else '🔴 Нет'}",
            inline=True
        )
        
        # Модерация
        embed.add_field(
            name="Модерация",
            value=f"**Спам-защита:** {'🟢 Включена' if settings.get('spam_protection', True) else '🔴 Выключена'}\n"
                  f"**Фильтр мата:** {'🟢 Включен' if settings.get('profanity_filter', True) else '🔴 Выключен'}",
            inline=True
        )
        
        # Дополнительные настройки
        embed.add_field(
            name="Дополнительно",
            value=f"**Автоудаление команд:** {'🟢 Да' if settings.get('auto_delete_commands', False) else '🔴 Нет'}\n"
                  f"**Webhook уведомления:** {'🟢 Да' if settings.get('webhook_notifications', False) else '🔴 Нет'}",
            inline=True
        )
        
        # Роли и каналы
        mod_role = ctx.guild.get_role(settings.get('mod_role_id')) if settings.get('mod_role_id') else None
        log_channel = ctx.guild.get_channel(settings.get('log_channel_id')) if settings.get('log_channel_id') else None
        
        if mod_role or log_channel:
            embed.add_field(
                name="Роли и каналы",
                value=f"**Роль модератора:** {mod_role.mention if mod_role else 'Не установлена'}\n"
                      f"**Канал логов:** {log_channel.mention if log_channel else 'Не установлен'}",
                inline=False
            )
        
        # Статистика
        connection_count = await self.bot.db.get_server_connection_count(ctx.guild.id)
        embed.add_field(
            name="Статистика",
            value=f"**Активных соединений:** {connection_count}/{Config.MAX_CONNECTIONS_PER_SERVER}",
            inline=True
        )
        
        embed.set_footer(text=f"Используйте '{Config.PREFIX}admin set <параметр> <значение>' для изменения настроек")
        await ctx.send(embed=embed)
    
    @admin.command(name='set')
    @commands.has_permissions(administrator=True)
    async def set_setting(self, ctx, setting: str, *, value: str):
        """Изменить настройку сервера"""
        
        setting = setting.lower()
        valid_settings = {
            'prefix': str,
            'enabled': lambda x: x.lower() in ['true', '1', 'yes', 'on'],
            'spam_protection': lambda x: x.lower() in ['true', '1', 'yes', 'on'],
            'profanity_filter': lambda x: x.lower() in ['true', '1', 'yes', 'on'],
            'auto_delete_commands': lambda x: x.lower() in ['true', '1', 'yes', 'on'],
            'webhook_notifications': lambda x: x.lower() in ['true', '1', 'yes', 'on']
        }
        
        if setting not in valid_settings:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Неизвестная настройка",
                description=f"Доступные настройки: {', '.join(valid_settings.keys())}",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Преобразуем значение
        try:
            if valid_settings[setting] == str:
                converted_value = value
            else:
                converted_value = valid_settings[setting](value)
        except:
            embed = discord.Embed(
                title=f"{Config.EMOJI['error']} Неверное значение",
                description="Проверьте правильность введенного значения.",
                color=Config.COLORS['error']
            )
            return await ctx.send(embed=embed)
        
        # Сохраняем настройку
        await self.bot.db.update_server_setting(ctx.guild.id, setting, converted_value)
        
        embed = discord.Embed(
            title=f"{Config.EMOJI['success']} Настройка изменена",
            description=f"**{setting}** установлена в: `{converted_value}`",
            color=Config.COLORS['success']
        )
        
        await ctx.send(embe