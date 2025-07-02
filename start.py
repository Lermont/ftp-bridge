#!/usr/bin/env python3
"""
Скрипт запуска FTP Bridge с диагностикой и проверками безопасности
"""

import socket
import subprocess
import sys
import os
from pathlib import Path

def check_python_version():
    """Проверка версии Python"""
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        print(f"   Текущая версия: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def check_dependencies():
    """Проверка установки зависимостей"""
    required_packages = [
        'fastapi', 'uvicorn', 'pydantic', 'pydantic-settings', 
        'slowapi', 'python-multipart'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Отсутствуют пакеты: {', '.join(missing)}")
        print("   Установите: pip install -r requirements.txt")
        return False
    
    # Проверка опциональных пакетов
    try:
        import paramiko
        print("✅ SFTP поддержка (paramiko) доступна")
    except ImportError:
        print("⚠️  SFTP поддержка (paramiko) недоступна")
    
    print("✅ Все основные зависимости установлены")
    return True

def check_port_availability(host, port):
    """Проверка доступности порта"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result != 0
    except Exception:
        return False

def check_environment():
    """Проверка переменных окружения с поддержкой degraded mode"""
    print("\n🔍 Проверка конфигурации...")
    
    # Загрузка настроек
    try:
        from config import settings
        print("✅ Конфигурация успешно загружена")
        degraded_mode = False
    except ValueError as e:
        print(f"⚠️  Ошибка конфигурации: {e}")
        print("\n🔶 ВКЛЮЧЕНИЕ DEGRADED MODE:")
        print("   Сервис будет запущен в режиме ограниченной функциональности")
        print("   - /health endpoint доступен")
        print("   - FTP функции отключены")
        print("   - Документация доступна")
        print("\n💡 Для полной функциональности:")
        print("   1. Скопируйте env_example.txt как .env")
        print("   2. Установите токены через переменные окружения:")
        print("      export FTP_BRIDGE_TOKEN_CLIENT1=$(python -c 'import secrets; print(secrets.token_hex(16))')")
        print("   3. Перезапустите сервис")
        
        # Установка переменной окружения для degraded mode
        os.environ['FTP_BRIDGE_DEGRADED_MODE'] = 'true'
        
        # Установка минимальных переменных для работы FastAPI
        if 'FTP_BRIDGE_TOKEN_SYSTEM' not in os.environ:
            os.environ['FTP_BRIDGE_TOKEN_SYSTEM'] = 'degraded_mode_placeholder_token_32chars'
        
        try:
            from config import settings
            degraded_mode = True
            print("✅ Degraded mode настроен успешно")
        except Exception as e2:
            print(f"❌ Критическая ошибка даже в degraded mode: {e2}")
            return False, None
    except Exception as e:
        print(f"❌ Неожиданная ошибка загрузки конфигурации: {e}")
        return False, None
    
    # В режиме деградации пропускаем большинство проверок
    if degraded_mode:
        print("🔶 Режим деградации - базовые проверки...")
        
        # Минимальные проверки для degraded mode
        temp_dir = Path(settings.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        host = settings.host if settings.host != "0.0.0.0" else "127.0.0.1"
        if not check_port_availability(host, settings.port):
            print(f"❌ Порт {settings.port} уже используется")
            return False, degraded_mode
        
        print(f"✅ Базовая настройка для degraded mode завершена")
        print(f"   Хост: {settings.host}:{settings.port}")
        print(f"   Статус: DEGRADED (FTP функции отключены)")
        
        return True, degraded_mode
    
    # Полные проверки для нормального режима
    token_count = len(settings.client_tokens)
    if token_count == 0:
        print("❌ Не настроены токены доступа!")
        return False, False
    elif token_count < 2:
        print(f"⚠️  Настроен только {token_count} токен. Рекомендуется настроить больше для разных клиентов.")
    else:
        print(f"✅ Настроено токенов: {token_count}")
    
    # Проверка качества токенов
    weak_tokens = [token for token in settings.client_tokens.keys() if len(token) < 32]
    if weak_tokens:
        print(f"⚠️  Найдены короткие токены ({len(weak_tokens)} шт.). Рекомендуется использовать токены 32+ символов.")
    
    # Проверка настроек безопасности
    security_issues = []
    
    if not settings.debug and "*" in settings.cors_origins:
        security_issues.append("CORS разрешает любые домены в продакшене")
    
    if not settings.rate_limit_enabled:
        security_issues.append("Rate limiting отключен")
    
    if settings.default_protocol.value == "ftp":
        security_issues.append("Используется незашифрованный FTP протокол")
    
    if security_issues:
        print("⚠️  Предупреждения безопасности:")
        for issue in security_issues:
            print(f"   - {issue}")
    
    # Проверка каталогов
    temp_dir = Path(settings.temp_dir)
    if not temp_dir.exists():
        print(f"📁 Создание временного каталога: {temp_dir}")
        temp_dir.mkdir(parents=True, exist_ok=True)
    
    if not temp_dir.is_dir() or not os.access(temp_dir, os.W_OK):
        print(f"❌ Временный каталог недоступен для записи: {temp_dir}")
        return False, False
    
    print(f"✅ Временный каталог: {temp_dir}")
    
    # Проверка порта
    host = settings.host if settings.host != "0.0.0.0" else "127.0.0.1"
    if not check_port_availability(host, settings.port):
        print(f"❌ Порт {settings.port} уже используется")
        print(f"   Измените FTP_BRIDGE_PORT или остановите другой сервис")
        return False, False
    
    print(f"✅ Порт {settings.port} доступен")
    
    # Информация о конфигурации
    print(f"\n📊 Итоговая конфигурация:")
    print(f"   Хост: {settings.host}:{settings.port}")
    print(f"   Режим отладки: {settings.debug}")
    print(f"   Протокол по умолчанию: {settings.default_protocol.value}")
    print(f"   FTPS: {settings.use_ftps}")
    print(f"   Rate limiting: {settings.rate_limit_enabled}")
    if settings.rate_limit_enabled:
        print(f"   Лимит: {settings.rate_limit_requests} запросов/{settings.rate_limit_window}с")
    print(f"   CORS домены: {settings.cors_origins}")
    print(f"   Макс. размер файла: {settings.max_file_size // (1024*1024)} MB")
    print(f"   Ротация логов: {settings.log_rotation_enabled}")
    if settings.known_hosts_path:
        print(f"   SFTP host keys: {settings.known_hosts_path}")
    
    return True, False

def interactive_setup():
    """Интерактивная настройка при первом запуске"""
    print("\n🔧 ПЕРВОНАЧАЛЬНАЯ НАСТРОЙКА")
    print("=" * 50)
    
    # Проверка существования .env
    env_file = Path(".env")
    if env_file.exists():
        print("✅ Файл .env найден")
        return True
    
    print("📝 Файл .env не найден. Создание из шаблона...")
    
    # Копирование из шаблона
    example_file = Path("env_example.txt")
    if not example_file.exists():
        print("❌ Файл env_example.txt не найден!")
        return False
    
    # Генерация токенов
    print("\n🔐 Генерация токенов безопасности...")
    
    try:
        import secrets
        tokens = {
            "POWERBI": secrets.token_hex(16),
            "EXCEL": secrets.token_hex(16),
            "ANALYTICS": secrets.token_hex(16)
        }
        
        # Чтение шаблона
        with open(example_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Замена примеров токенов на реальные
        content = content.replace(
            "FTP_BRIDGE_TOKEN_POWERBI=aabbccdd11223344556677889900aabbccddee",
            f"FTP_BRIDGE_TOKEN_POWERBI={tokens['POWERBI']}"
        )
        content = content.replace(
            "FTP_BRIDGE_TOKEN_EXCEL=1122334455667788990011223344556677889900",
            f"FTP_BRIDGE_TOKEN_EXCEL={tokens['EXCEL']}"
        )
        content = content.replace(
            "FTP_BRIDGE_TOKEN_ANALYTICS=9988776655443322110099887766554433221100",
            f"FTP_BRIDGE_TOKEN_ANALYTICS={tokens['ANALYTICS']}"
        )
        
        # Сохранение .env файла
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Файл .env создан с новыми токенами:")
        print(f"   Power BI токен: {tokens['POWERBI']}")
        print(f"   Excel токен: {tokens['EXCEL']}")
        print(f"   Analytics токен: {tokens['ANALYTICS']}")
        print("\n💾 Сохраните эти токены в безопасном месте!")
        print("🔒 Не делитесь токенами и не добавляйте .env в Git!")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания .env файла: {e}")
        return False

def run_server():
    """Запуск сервера"""
    try:
        from config import settings
        
        print(f"\n🚀 Запуск FTP Bridge сервера...")
        print(f"   URL: http://{settings.host}:{settings.port}")
        print(f"   Документация: http://127.0.0.1:{settings.port}/docs")
        print(f"   Health check: http://127.0.0.1:{settings.port}/health")
        print("\n💡 Для остановки нажмите Ctrl+C")
        print("=" * 50)
        
        # Запуск через uvicorn
        import uvicorn
        uvicorn.run(
            "main:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
            log_level=settings.log_level.value.lower(),
            access_log=True
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 Сервер остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка запуска сервера: {e}")
        return False
    
    return True

def main():
    """Основная функция запуска"""
    print("=" * 60)
    print("🌉 FTP Bridge v2.1.0 - Система запуска")
    print("=" * 60)
    
    # Проверки системы
    if not check_python_version():
        sys.exit(1)
    
    if not check_dependencies():
        sys.exit(1)
    
    # Интерактивная настройка при необходимости
    if not Path(".env").exists():
        if not interactive_setup():
            sys.exit(1)
    
    # Проверка конфигурации с поддержкой degraded mode
    config_ok, degraded_mode = check_environment()
    if not config_ok:
        print("\n💡 Рекомендации:")
        print("   1. Проверьте переменные окружения")
        print("   2. Убедитесь что порт свободен")  
        print("   3. Перезапустите после исправления")
        sys.exit(1)
    
    if degraded_mode:
        print("\n🔶 Запуск в режиме деградации:")
        print("   - Доступны только /health и /docs эндпоинты")
        print("   - FTP функции отключены")
        print("   - Настройте токены для полной функциональности")
    else:
        print("\n🎯 Все проверки пройдены успешно!")
    
    # Запуск сервера
    if not run_server():
        sys.exit(1)

if __name__ == "__main__":
    main() 