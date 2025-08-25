#!/usr/bin/env python3
"""
Скрипт запуска InterServer Bot с предварительными проверками
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
import asyncio

# Настройка логирования для скрипта запуска
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_python_version():
    """Проверка версии Python"""
    if sys.version_info < (3, 8):
        logger.error("Требуется Python 3.8 или выше")
        logger.error(f"Текущая версия: {sys.version}")
        return False
    
    logger.info(f"Python версия: {sys.version}")
    return True

def check_dependencies():
    """Проверка установленных зависимостей"""
    try:
        import discord
        logger.info(f"discord.py версия: {discord.__version__}")
        
        if discord.version_info < (2, 3, 0):
            logger.warning("Рекомендуется discord.py версии 2.3.0 или выше")
        
        # Проверяем другие критические зависимости
        import aiosqlite
        import dotenv
        
        logger.info("Все основные зависимости установлены")
        return True
        
    except ImportError as e:
        logger.error(f"Отсутствует зависимость: {e}")
        logger.error("Установите зависимости командой: pip install -r requirements.txt")
        return False

def check_environment():
    """Проверка переменных окружения"""
    # Проверяем наличие .env файла
    env_path = Path('.env')
    if not env_path.exists():
        logger.warning(".env файл не найден")
        logger.info("Скопируйте .env.example в .env и настройте переменные")
        
        example_path = Path('.env.example')
        if example_path.exists():
            logger.info("Найден .env.example файл")
            return False
        else:
            logger.error("Отсутствуют файлы конфигурации")
            return False
    
    # Загружаем переменные окружения
    from dotenv import load_dotenv
    load_dotenv()
    
    # Проверяем критические переменные
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN не установлен в .env файле")
        return False
    
    if bot_token == 'your_discord_bot_token_here':
        logger.error("Необходимо установить реальный токен бота в BOT_TOKEN")
        return False
    
    logger.info("Переменные окружения настроены корректно")
    return True

def check_directories():
    """Создание необходимых директорий"""
    directories = [
        'data',
        'logs', 
        'cogs',
        'utils'
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True)
            logger.info(f"Создана директория: {directory}")
    
    return True

def check_permissions():
    """Проверка прав доступа"""
    # Проверяем права на запись в директорию данных
    data_dir = Path('data')
    if not os.access(data_dir, os.W_OK):
        logger.error(f"Нет прав на запись в директорию {data_dir}")
        return False
    
    # Проверяем права на запись в директорию логов
    logs_dir = Path('logs')
    if not os.access(logs_dir, os.W_OK):
        logger.error(f"Нет прав на запись в директорию {logs_dir}")
        return False
    
    logger.info("Права доступа в порядке")
    return True

def create_init_files():
    """Создание __init__.py файлов для пакетов"""
    packages = ['cogs', 'utils']
    
    for package in packages:
        init_file = Path(package) / '__init__.py'
        if not init_file.exists():
            init_file.touch()
            logger.info(f"Создан файл: {init_file}")

def show_startup_info():
    """Отображение информации о запуске"""
    print("\n" + "="*60)
    print("🤖 InterServer Bot - Запуск")
    print("="*60)
    print("Бот для межсерверного общения в Discord")
    print("Версия: 1.0.0")
    print("Автор: @yourusername")
    print("="*60 + "\n")

def show_help():
    """Отображение справки"""
    print("""
Использование: python start.py [опции]

Опции:
  --help, -h     Показать эту справку
  --check        Только проверить конфигурацию без запуска
  --install      Установить зависимости
  --setup        Первоначальная настройка
  --version      Показать версию

Примеры:
  python start.py              # Обычный запуск
  python start.py --check      # Проверка конфигурации
  python start.py --setup      # Первоначальная настройка
    """)

def install_dependencies():
    """Установка зависимостей"""
    logger.info("Установка зависимостей...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
        logger.info("Зависимости успешно установлены")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Ошибка при установке зависимостей: {e}")
        return False

def setup_bot():
    """Первоначальная настройка бота"""
    logger.info("Начало первоначальной настройки...")
    
    # Создаем .env файл из примера
    env_example = Path('.env.example')
    env_file = Path('.env')
    
    if env_example.exists() and not env_file.exists():
        import shutil
        shutil.copy('.env.example', '.env')
        logger.info("Создан .env файл из .env.example")
        print("\n⚠️  ВАЖНО: Отредактируйте .env файл и установите ваш BOT_TOKEN!")
        print("Получить токен можно на https://discord.com/developers/applications")
    
    # Устанавливаем зависимости
    if not install_dependencies():
        return False
    
    # Создаем директории
    check_directories()
    create_init_files()
    
    logger.info("Первоначальная настройка завершена")
    print("\nТеперь отредактируйте .env файл и запустите бота командой:")
    print("python start.py")
    
    return True

async def start_bot():
    """Запуск бота"""
    logger.info("Запуск Discord бота...")
    
    try:
        # Импортируем и запускаем основной модуль
        from main import main
        await main()
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise

def main():
    """Основная функция"""
    # Парсинг аргументов командной строки
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ['--help', '-h']:
            show_help()
            return
        elif arg == '--version':
            print("InterServer Bot v1.0.0")
            return
        elif arg == '--install':
            install_dependencies()
            return
        elif arg == '--setup':
            setup_bot()
            return
        elif arg == '--check':
            show_startup_info()
            checks_passed = all([
                check_python_version(),
                check_dependencies(),
                check_environment(),
                check_directories(),
                check_permissions()
            ])
            
            if checks_passed:
                print("✅ Все проверки пройдены успешно!")
            else:
                print("❌ Некоторые проверки не пройдены")
                sys.exit(1)
            return
    
    # Обычный запуск бота
    show_startup_info()
    
    # Выполняем предварительные проверки
    logger.info("Выполнение предварительных проверок...")
    
    checks = [
        ("Версия Python", check_python_version),
        ("Зависимости", check_dependencies),
        ("Переменные окружения", check_environment),
        ("Директории", check_directories),
        ("Права доступа", check_permissions)
    ]
    
    failed_checks = []
    
    for check_name, check_func in checks:
        try:
            if not check_func():
                failed_checks.append(check_name)
        except Exception as e:
            logger.error(f"Ошибка при проверке {check_name}: {e}")
            failed_checks.append(check_name)
    
    if failed_checks:
        logger.error("Не пройдены проверки:")
        for check in failed_checks:
            logger.error(f"  - {check}")
        
        print("\nДля первоначальной настройки выполните:")
        print("python start.py --setup")
        sys.exit(1)
    
    # Создаем init файлы
    create_init_files()
    
    logger.info("Все проверки пройдены успешно!")
    logger.info("Запуск бота...")
    
    # Запускаем бота
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()