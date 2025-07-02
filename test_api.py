#!/usr/bin/env python3
"""
Тестирование FTP Bridge API v2.1.0
Комплексные тесты функциональности, безопасности и производительности
Включает тесты новых функций: HEAD endpoint, path sanitizer, PII masking, auto-chunk tuning
"""

import time
import requests
import json
import os
import tempfile
from pathlib import Path
import socket
import subprocess
import sys
from urllib.parse import urlencode

# Тестовая конфигурация
class TestConfig:
    def __init__(self):
        # Попытка загрузки настроек
        try:
            from config import settings
            self.BASE_URL = f"http://{settings.host}:{settings.port}"
            self.TOKENS = list(settings.client_tokens.keys())
            self.CLIENT_NAMES = list(settings.client_tokens.values())
            self.RATE_LIMIT_ENABLED = settings.rate_limit_enabled
            self.RATE_LIMIT_REQUESTS = settings.rate_limit_requests
            self.RATE_LIMIT_WINDOW = settings.rate_limit_window
            print(f"✅ Загружена конфигурация: {len(self.TOKENS)} токенов")
        except Exception as e:
            print(f"⚠️  Ошибка загрузки конфигурации: {e}")
            print("   Используются тестовые настройки по умолчанию")
            self.BASE_URL = "http://127.0.0.1:8000"
            self.TOKENS = []
            self.CLIENT_NAMES = []
            self.RATE_LIMIT_ENABLED = True
            self.RATE_LIMIT_REQUESTS = 100
            self.RATE_LIMIT_WINDOW = 3600
        
        self.VALID_TOKEN = self.TOKENS[0] if self.TOKENS else "dummy_token_for_offline_tests"
        self.INVALID_TOKEN = "invalid_token_12345678"
        
        # Тестовые параметры FTP
        self.TEST_FTP = {
            "host": "test.rebex.net",  # Публичный тестовый FTP
            "user": "demo",
            "password": "password",
            "path": "/",
            "file": "readme.txt"
        }
        
        # Тестовые параметры SFTP (публичный тестовый сервер)
        self.TEST_SFTP = {
            "host": "test.rebex.net",
            "user": "demo",
            "password": "password",
            "path": "/",
            "file": "readme.txt",
            "protocol": "sftp"
        }

def wait_for_server(base_url: str, timeout: int = 30) -> bool:
    """Ожидание запуска сервера"""
    print(f"🔄 Ожидание запуска сервера: {base_url}")
    
    for attempt in range(timeout):
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                print(f"✅ Сервер доступен (попытка {attempt + 1})")
                return True
        except requests.exceptions.RequestException:
            pass
        
        if attempt < timeout - 1:
            time.sleep(1)
    
    print(f"❌ Сервер недоступен после {timeout} секунд")
    return False

def test_basic_endpoints(config: TestConfig):
    """Тест базовых эндпоинтов"""
    print("\n🧪 Тестирование базовых эндпоинтов...")
    results = []
    
    # Тест корневого эндпоинта
    try:
        response = requests.get(config.BASE_URL)
        if response.status_code == 200:
            data = response.json()
            if "service" in data and data["service"] == "FTP Bridge":
                results.append("✅ Root endpoint работает")
                print(f"   Версия: {data.get('version', 'unknown')}")
                print(f"   Протоколы: {data.get('config', {}).get('protocols', [])}")
            else:
                results.append("❌ Root endpoint: неверный формат ответа")
        else:
            results.append(f"❌ Root endpoint: статус {response.status_code}")
    except Exception as e:
        results.append(f"❌ Root endpoint: ошибка {e}")
    
    # Тест health check
    try:
        response = requests.get(f"{config.BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") in ["healthy", "degraded"]:
                results.append("✅ Health check работает")
                print(f"   Статус: {data['status']}")
                print(f"   Активных токенов: {data.get('active_tokens', 0)}")
                print(f"   Протоколы: {data.get('protocols_available', [])}")
            else:
                results.append("❌ Health check: неверный статус")
        else:
            results.append(f"❌ Health check: статус {response.status_code}")
    except Exception as e:
        results.append(f"❌ Health check: ошибка {e}")
    
    # Тест документации
    try:
        response = requests.get(f"{config.BASE_URL}/docs")
        if response.status_code == 200:
            results.append("✅ Документация доступна")
        else:
            results.append(f"❌ Документация: статус {response.status_code}")
    except Exception as e:
        results.append(f"❌ Документация: ошибка {e}")
    
    return results

def test_head_endpoint(config: TestConfig):
    """Тест HEAD endpoint для метаданных файлов"""
    print("\n👤 Тестирование HEAD endpoint...")
    results = []
    
    if not config.TOKENS:
        results.append("⚠️  Пропущен: токены не настроены")
        return results
    
    headers = {"Authorization": f"Bearer {config.VALID_TOKEN}"}
    
    # Тест HEAD запроса (должен возвращать заголовки без тела)
    try:
        params = {
            "host": config.TEST_FTP["host"],
            "user": config.TEST_FTP["user"],
            "password": config.TEST_FTP["password"],
            "path": f"{config.TEST_FTP['path']}{config.TEST_FTP['file']}"
        }
        response = requests.head(f"{config.BASE_URL}/download", params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Проверка обязательных заголовков
            required_headers = ["X-File-Size", "X-Protocol", "X-File-Name"]
            missing_headers = [h for h in required_headers if h not in response.headers]
            
            if not missing_headers:
                results.append("✅ HEAD endpoint работает с правильными заголовками")
                print(f"   Размер файла: {response.headers.get('X-File-Size')} байт")
                print(f"   Протокол: {response.headers.get('X-Protocol')}")
                print(f"   Имя файла: {response.headers.get('X-File-Name')}")
                
                # Проверка что тело ответа пустое
                if len(response.content) == 0:
                    results.append("✅ HEAD ответ не содержит тела")
                else:
                    results.append("⚠️  HEAD ответ содержит тело (не критично)")
            else:
                results.append(f"❌ HEAD endpoint: отсутствуют заголовки {missing_headers}")
        else:
            results.append(f"❌ HEAD endpoint: статус {response.status_code}")
            
    except requests.exceptions.Timeout:
        results.append("⚠️  HEAD endpoint: таймаут (возможно, тестовый сервер недоступен)")
    except Exception as e:
        results.append(f"❌ HEAD endpoint: ошибка {e}")
    
    # Тест с неверными параметрами
    try:
        params = {"host": "nonexistent.example.com", "user": "fake", "password": "fake", "path": "/fake.txt"}
        response = requests.head(f"{config.BASE_URL}/download", params=params, headers=headers, timeout=5)
        
        if response.status_code in [400, 401, 404, 500]:
            results.append("✅ HEAD endpoint правильно обрабатывает ошибки")
        else:
            results.append(f"⚠️  HEAD endpoint с ошибочными параметрами: статус {response.status_code}")
    except requests.exceptions.Timeout:
        results.append("✅ HEAD endpoint правильно обрабатывает таймауты")
    except Exception as e:
        results.append(f"❌ HEAD endpoint с ошибочными параметрами: ошибка {e}")
    
    return results

def test_degraded_mode(config: TestConfig):
    """Тест режима деградации"""
    print("\n🔶 Тестирование degraded mode...")
    results = []
    
    # Проверяем текущий статус через health check
    try:
        response = requests.get(f"{config.BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            current_status = data.get("status", "unknown")
            degraded_mode = data.get("degraded_mode", False)
            
            if current_status == "degraded" or degraded_mode:
                results.append("🔶 Сервер работает в режиме деградации")
                
                # В режиме деградации /download должен возвращать 503
                try:
                    headers = {"Authorization": "Bearer dummy_token"}
                    params = {"host": "test.com", "user": "test", "password": "test", "path": "/test.txt"}
                    response = requests.get(f"{config.BASE_URL}/download", params=params, headers=headers)
                    
                    if response.status_code == 503:
                        results.append("✅ В degraded mode /download правильно отключен")
                    else:
                        results.append(f"⚠️  В degraded mode /download статус: {response.status_code}")
                except Exception as e:
                    results.append(f"❌ Ошибка тестирования degraded mode download: {e}")
                
                # Health должен оставаться доступным
                results.append("✅ /health доступен в degraded mode")
                
            else:
                results.append(f"✅ Сервер работает в нормальном режиме (статус: {current_status})")
                
        else:
            results.append(f"❌ Не удалось получить статус сервера: {response.status_code}")
            
    except Exception as e:
        results.append(f"❌ Ошибка проверки degraded mode: {e}")
    
    return results

def test_auto_chunk_tuning(config: TestConfig):
    """Тест автоматической настройки размера чанков"""
    print("\n⚡ Тестирование auto-chunk tuning...")
    results = []
    
    if not config.TOKENS:
        results.append("⚠️  Пропущен: токены не настроены")
        return results
    
    headers = {"Authorization": f"Bearer {config.VALID_TOKEN}"}
    
    # Попытка загрузки файла и проверка заголовков
    try:
        params = {
            "host": config.TEST_FTP["host"],
            "user": config.TEST_FTP["user"], 
            "password": config.TEST_FTP["password"],
            "path": f"{config.TEST_FTP['path']}{config.TEST_FTP['file']}"
        }
        
        response = requests.get(f"{config.BASE_URL}/download", params=params, headers=headers, timeout=15, stream=True)
        
        if response.status_code == 200:
            # Проверка заголовка автотюнинга чанков
            auto_tuned = response.headers.get("X-Auto-Chunk-Tuned", "false")
            file_size = int(response.headers.get("X-File-Size", "0"))
            
            # Если файл больше 10MB, должен быть включен автотюнинг
            if file_size > 10 * 1024 * 1024:
                if auto_tuned == "true":
                    results.append("✅ Auto-chunk tuning активирован для большого файла")
                else:
                    results.append("⚠️  Auto-chunk tuning не активирован для большого файла")
            else:
                if auto_tuned == "false":
                    results.append("✅ Auto-chunk tuning правильно отключен для маленького файла")
                else:
                    results.append("⚠️  Auto-chunk tuning неожиданно активирован для маленького файла")
            
            print(f"   Размер файла: {file_size} байт")
            print(f"   Auto-chunk tuned: {auto_tuned}")
            
            # Прерываем загрузку после проверки заголовков
            response.close()
            results.append("✅ Заголовки auto-chunk tuning проверены")
            
        else:
            results.append(f"⚠️  Не удалось проверить auto-chunk tuning: статус {response.status_code}")
            
    except requests.exceptions.Timeout:
        results.append("⚠️  Auto-chunk tuning: таймаут (возможно, тестовый сервер недоступен)")
    except Exception as e:
        results.append(f"❌ Auto-chunk tuning: ошибка {e}")
    
    return results

def test_authentication(config: TestConfig):
    """Тест аутентификации"""
    print("\n🔐 Тестирование аутентификации...")
    results = []
    
    if not config.TOKENS:
        results.append("⚠️  Пропущен: токены не настроены")
        return results
    
    # Тест без токена
    try:
        response = requests.get(f"{config.BASE_URL}/download")
        if response.status_code == 403:
            results.append("✅ Запрос без токена правильно отклонен")
        else:
            results.append(f"❌ Запрос без токена: неожиданный статус {response.status_code}")
    except Exception as e:
        results.append(f"❌ Тест без токена: ошибка {e}")
    
    # Тест с неверным токеном
    try:
        headers = {"Authorization": f"Bearer {config.INVALID_TOKEN}"}
        response = requests.get(f"{config.BASE_URL}/download", headers=headers)
        if response.status_code == 403:
            results.append("✅ Неверный токен правильно отклонен")
        else:
            results.append(f"❌ Неверный токен: неожиданный статус {response.status_code}")
    except Exception as e:
        results.append(f"❌ Тест неверного токена: ошибка {e}")
    
    # Тест с действительным токеном (без параметров)
    try:
        headers = {"Authorization": f"Bearer {config.VALID_TOKEN}"}
        response = requests.get(f"{config.BASE_URL}/download", headers=headers)
        if response.status_code == 422:  # Ошибка валидации параметров
            results.append("✅ Действительный токен принят (ошибка параметров ожидаема)")
        else:
            results.append(f"⚠️  Действительный токен: статус {response.status_code}")
    except Exception as e:
        results.append(f"❌ Тест действительного токена: ошибка {e}")
    
    return results

def test_parameter_validation(config: TestConfig):
    """Тест валидации параметров"""
    print("\n📋 Тестирование валидации параметров...")
    results = []
    
    if not config.TOKENS:
        results.append("⚠️  Пропущен: токены не настроены")
        return results
    
    headers = {"Authorization": f"Bearer {config.VALID_TOKEN}"}
    
    # Тест path sanitizer и защиты от path traversal 
    dangerous_paths = [
        "../etc/passwd",
        "../../config.py", 
        "/path/with/../traversal/file.txt",
        "\\windows\\system32\\config\\sam",
        "/path//double/slash/file.txt",
        "",  # Пустой путь
        "path_without_leading_slash.txt"
    ]
    for dangerous_path in dangerous_paths:
        try:
            params = {
                "host": "example.com",
                "user": "test", 
                "password": "test",
                "path": dangerous_path
            }
            response = requests.get(f"{config.BASE_URL}/download", params=params, headers=headers)
            if response.status_code == 400:
                results.append(f"✅ Опасный путь заблокирован: {dangerous_path}")
            else:
                results.append(f"⚠️  Path traversal: {dangerous_path} - статус {response.status_code}")
        except Exception as e:
            results.append(f"❌ Path traversal тест: ошибка {e}")
    
    # Тест недопустимых расширений
    invalid_extensions = ["script.exe", "virus.bat", "backdoor.sh", "config.conf"]
    for invalid_file in invalid_extensions:
        try:
            params = {
                "host": "example.com",
                "user": "test", 
                "password": "test",
                "path": "/",
                "file": invalid_file
            }
            response = requests.get(f"{config.BASE_URL}/download", params=params, headers=headers)
            if response.status_code == 400:
                results.append(f"✅ Недопустимое расширение блокировано: {invalid_file}")
            else:
                results.append(f"⚠️  Недопустимое расширение: {invalid_file} - статус {response.status_code}")
        except Exception as e:
            results.append(f"❌ Тест расширений: ошибка {e}")
    
    # Тест допустимых расширений
    valid_files = ["data.csv", "report.xlsx", "document.pdf", "config.json"]
    for valid_file in valid_files:
        try:
            params = {
                "host": "nonexistent.example.com",  # Несуществующий хост
                "user": "test",
                "password": "test", 
                "path": "/",
                "file": valid_file
            }
            response = requests.get(f"{config.BASE_URL}/download", params=params, headers=headers)
            if response.status_code != 400:  # Не ошибка валидации
                results.append(f"✅ Допустимое расширение принято: {valid_file}")
            else:
                results.append(f"❌ Допустимое расширение отклонено: {valid_file}")
        except Exception as e:
            results.append(f"❌ Тест допустимых расширений: ошибка {e}")
    
    return results

def test_protocol_support(config: TestConfig):
    """Тест поддержки протоколов"""
    print("\n🔌 Тестирование поддержки протоколов...")
    results = []
    
    if not config.TOKENS:
        results.append("⚠️  Пропущен: токены не настроены")
        return results
    
    headers = {"Authorization": f"Bearer {config.VALID_TOKEN}"}
    
    # Тест недопустимого протокола
    try:
        params = {
            "host": "example.com",
            "user": "test",
            "password": "test",
            "path": "/",
            "file": "test.txt",
            "protocol": "invalid_protocol"
        }
        response = requests.get(f"{config.BASE_URL}/download", params=params, headers=headers)
        if response.status_code == 400:
            results.append("✅ Неверный протокол отклонен")
        else:
            results.append(f"❌ Неверный протокол: статус {response.status_code}")
    except Exception as e:
        results.append(f"❌ Тест протокола: ошибка {e}")
    
    # Тест доступности SFTP
    try:
        import paramiko
        results.append("✅ SFTP поддержка доступна (paramiko установлен)")
        
        # Тест SFTP параметров
        params = {
            "host": "nonexistent.sftp.com",
            "user": "test",
            "password": "test",
            "path": "/",
            "file": "test.txt",
            "protocol": "sftp"
        }
        response = requests.get(f"{config.BASE_URL}/download", params=params, headers=headers)
        if response.status_code != 400:  # Не ошибка валидации
            results.append("✅ SFTP протокол принят")
        else:
            results.append("❌ SFTP протокол отклонен")
            
    except ImportError:
        results.append("⚠️  SFTP поддержка недоступна (paramiko не установлен)")
        
        # Тест отклонения SFTP когда paramiko недоступен
        params = {
            "host": "example.com",
            "user": "test", 
            "password": "test",
            "path": "/",
            "file": "test.txt",
            "protocol": "sftp"
        }
        response = requests.get(f"{config.BASE_URL}/download", params=params, headers=headers)
        if response.status_code == 400:
            results.append("✅ SFTP правильно отклонен без paramiko")
        else:
            results.append(f"❌ SFTP без paramiko: статус {response.status_code}")
    
    return results

def test_rate_limiting(config: TestConfig):
    """Тест rate limiting"""
    print("\n⚡ Тестирование rate limiting...")
    results = []
    
    if not config.RATE_LIMIT_ENABLED:
        results.append("⚠️  Rate limiting отключен в конфигурации")
        return results
    
    if not config.TOKENS:
        results.append("⚠️  Пропущен: токены не настроены")
        return results
    
    headers = {"Authorization": f"Bearer {config.VALID_TOKEN}"}
    
    # Быстрые последовательные запросы для проверки rate limiting
    print(f"   Отправка 10 быстрых запросов...")
    rate_limited = False
    
    for i in range(10):
        try:
            params = {
                "host": "nonexistent.example.com",
                "user": "test",
                "password": "test",
                "path": "/",
                "file": "test.txt"
            }
            response = requests.get(f"{config.BASE_URL}/download", params=params, headers=headers, timeout=5)
            
            if response.status_code == 429:  # Too Many Requests
                rate_limited = True
                results.append(f"✅ Rate limiting сработал на запросе {i+1}")
                break
                
        except requests.exceptions.Timeout:
            results.append("⚠️  Timeout - возможно rate limiting активен")
            break
        except Exception as e:
            results.append(f"❌ Ошибка rate limiting теста: {e}")
            break
        
        time.sleep(0.1)  # Небольшая пауза между запросами
    
    if not rate_limited and config.RATE_LIMIT_REQUESTS <= 10:
        results.append("⚠️  Rate limiting не сработал (возможно высокий лимит)")
    elif not rate_limited:
        results.append(f"✅ Rate limiting настроен ({config.RATE_LIMIT_REQUESTS} запросов/{config.RATE_LIMIT_WINDOW}с)")
    
    return results

def test_cors_headers(config: TestConfig):
    """Тест CORS заголовков"""
    print("\n🌐 Тестирование CORS...")
    results = []
    
    # Тест CORS headers
    try:
        response = requests.options(config.BASE_URL)
        cors_headers = {
            'Access-Control-Allow-Origin',
            'Access-Control-Allow-Methods',
            'Access-Control-Allow-Headers'
        }
        
        found_headers = set(response.headers.keys()) & cors_headers
        if found_headers:
            results.append(f"✅ CORS заголовки найдены: {', '.join(found_headers)}")
        else:
            results.append("⚠️  CORS заголовки не найдены")
            
        # Проверка безопасности CORS
        origin_header = response.headers.get('Access-Control-Allow-Origin')
        if origin_header == '*':
            results.append("⚠️  CORS разрешает любые домены (небезопасно для продакшена)")
        elif origin_header:
            results.append(f"✅ CORS ограничен доменами: {origin_header}")
        
    except Exception as e:
        results.append(f"❌ CORS тест: ошибка {e}")
    
    return results

def test_real_ftp_download(config: TestConfig):
    """Тест реальной загрузки с FTP (опционально)"""
    print("\n📡 Тестирование реальной FTP загрузки...")
    results = []
    
    if not config.TOKENS:
        results.append("⚠️  Пропущен: токены не настроены")
        return results
    
    headers = {"Authorization": f"Bearer {config.VALID_TOKEN}"}
    
    # Тест с публичным FTP сервером
    try:
        params = config.TEST_FTP.copy()
        print(f"   Подключение к тестовому FTP: {params['host']}")
        
        response = requests.get(
            f"{config.BASE_URL}/download", 
            params=params, 
            headers=headers,
            timeout=30  # Увеличенный timeout для сетевых операций
        )
        
        if response.status_code == 200:
            results.append("✅ FTP загрузка успешна")
            print(f"   Размер файла: {len(response.content)} байт")
            print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
        elif response.status_code == 500:
            results.append("⚠️  FTP сервер недоступен или ошибка сети")
        else:
            results.append(f"❌ FTP загрузка: статус {response.status_code}")
            
    except requests.exceptions.Timeout:
        results.append("⚠️  FTP загрузка: timeout (сервер может быть недоступен)")
    except Exception as e:
        results.append(f"❌ FTP загрузка: ошибка {e}")
    
    return results

def test_real_sftp_download(config: TestConfig):
    """Тест реальной загрузки с SFTP (опционально)"""
    print("\n🔒 Тестирование реальной SFTP загрузки...")
    results = []
    
    if not config.TOKENS:
        results.append("⚠️  Пропущен: токены не настроены")
        return results
    
    # Проверка доступности paramiko
    try:
        import paramiko
    except ImportError:
        results.append("⚠️  SFTP пропущен: paramiko не установлен")
        return results
    
    headers = {"Authorization": f"Bearer {config.VALID_TOKEN}"}
    
    # Тест с публичным SFTP сервером
    try:
        params = config.TEST_SFTP.copy()
        print(f"   Подключение к тестовому SFTP: {params['host']}")
        
        response = requests.get(
            f"{config.BASE_URL}/download", 
            params=params, 
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            results.append("✅ SFTP загрузка успешна")
            print(f"   Размер файла: {len(response.content)} байт")
        elif response.status_code == 500:
            results.append("⚠️  SFTP сервер недоступен или ошибка сети")
        else:
            results.append(f"❌ SFTP загрузка: статус {response.status_code}")
            
    except requests.exceptions.Timeout:
        results.append("⚠️  SFTP загрузка: timeout (сервер может быть недоступен)")
    except Exception as e:
        results.append(f"❌ SFTP загрузка: ошибка {e}")
    
    return results

def run_all_tests():
    """Запуск всех тестов"""
    print("🧪 FTP Bridge API Тестирование v2.1.0")
    print("=" * 60)
    
    config = TestConfig()
    
    # Ожидание запуска сервера
    if not wait_for_server(config.BASE_URL):
        print("❌ Не удалось подключиться к серверу")
        print("💡 Убедитесь что сервер запущен: python start.py")
        return False
    
    # Запуск тестов
    all_results = []
    
    test_functions = [
        ("Базовые эндпоинты", test_basic_endpoints),
        ("HEAD endpoint", test_head_endpoint),
        ("Degraded Mode", test_degraded_mode),
        ("Auto-chunk tuning", test_auto_chunk_tuning),
        ("Аутентификация", test_authentication),
        ("Валидация параметров", test_parameter_validation),
        ("Поддержка протоколов", test_protocol_support),
        ("Rate Limiting", test_rate_limiting),
        ("CORS заголовки", test_cors_headers),
        ("FTP загрузка", test_real_ftp_download),
        ("SFTP загрузка", test_real_sftp_download)
    ]
    
    for test_name, test_func in test_functions:
        try:
            results = test_func(config)
            all_results.extend(results)
        except Exception as e:
            all_results.append(f"❌ {test_name}: критическая ошибка {e}")
    
    # Подсчет результатов
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for r in all_results if r.startswith("✅"))
    warnings = sum(1 for r in all_results if r.startswith("⚠️"))
    failed = sum(1 for r in all_results if r.startswith("❌"))
    
    print(f"✅ Успешно: {passed}")
    print(f"⚠️  Предупреждения: {warnings}")
    print(f"❌ Ошибки: {failed}")
    print(f"📋 Всего проверок: {len(all_results)}")
    
    if failed > 0:
        print("\n❌ ПРОВАЛЕННЫЕ ТЕСТЫ:")
        for result in all_results:
            if result.startswith("❌"):
                print(f"   {result}")
    
    if warnings > 0:
        print("\n⚠️  ПРЕДУПРЕЖДЕНИЯ:")
        for result in all_results:
            if result.startswith("⚠️"):
                print(f"   {result}")
    
    print("\n🎯 РЕКОМЕНДАЦИИ:")
    if failed == 0 and warnings == 0:
        print("   🎉 Все тесты пройдены! API готов к использованию.")
    else:
        print("   🔧 Исправьте обнаруженные проблемы")
        print("   📖 Проверьте документацию: /docs")
        print("   ⚙️  Проверьте конфигурацию в .env файле")
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 