"""
FTP Bridge v2.1.0 - FastAPI версия
Безопасный мост для интеграции FTP-серверов с Power BI и другими аналитическими системами.
Реализует современную архитектуру с разделением ответственности и усиленной безопасностью.
"""

import os
import tempfile
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import uvicorn

from config import settings
from storage_backend import (
    StorageBackendFactory, 
    sanitize_path, 
    mask_user_info, 
    auto_tune_chunk_size
)

# SFTP поддержка
try:
    import paramiko
    SFTP_AVAILABLE = True
except ImportError:
    SFTP_AVAILABLE = False
    print("⚠️  Paramiko не установлен, SFTP поддержка отключена")

# Настройка логирования с ротацией
def setup_logging():
    """Настройка логирования с ротацией файлов"""
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, settings.log_level.value))
    
    # Очистка существующих handlers
    logger.handlers.clear()
    
    # Форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler с ротацией
    if settings.log_rotation_enabled:
        file_handler = RotatingFileHandler(
            settings.log_file,
            maxBytes=settings.log_max_size,
            backupCount=settings.log_backup_count,
            encoding='utf-8'
        )
    else:
        file_handler = logging.FileHandler(settings.log_file, encoding='utf-8')
    
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()

# Rate Limiting с дефолтными лимитами
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"]  # Дефолтный лимит 100 запросов в минуту
)

# Безопасность
security = HTTPBearer()

# Создание временного каталога при запуске
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Создание временного каталога
    os.makedirs(settings.temp_dir, exist_ok=True)
    logger.info(f"Временный каталог создан: {settings.temp_dir}")
    
    # Проверка режима деградации
    if settings.degraded_mode:
        logger.warning("🔶 DEGRADED MODE: Сервис запущен в режиме деградации - FTP функции отключены")
    else:
        logger.info(f"FTP Bridge v2.1.0 запущен в полном режиме")
    
    logger.info(f"Загружено токенов: {len(settings.client_tokens)}")
    logger.info(f"Rate limiting: {'включен' if settings.rate_limit_enabled else 'отключен'}")
    logger.info(f"SFTP поддержка: {'доступна' if SFTP_AVAILABLE else 'недоступна'}")
    
    # Предупреждения безопасности
    if settings.default_protocol.value == "ftp":
        logger.warning("⚠️  Unsafe legacy mode: FTP enabled - рекомендуется использовать FTPS или SFTP")
    
    yield
    # Очистка при завершении работы
    logger.info("Приложение завершает работу")

app = FastAPI(
    title="FTP Bridge",
    description="Безопасный мост для интеграции FTP-серверов с Power BI",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Rate Limiting Middleware
if settings.rate_limit_enabled:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    logger.info(f"Rate limiting включен с дефолтными лимитами: 100/minute")

# CORS настройки с безопасной конфигурацией
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=["Authorization", "Content-Type"],
)

def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка токена доступа"""
    token = credentials.credentials
    if not settings.validate_token(token):
        logger.warning(f"Попытка доступа с неверным токеном: {token[:8]}***")
        raise HTTPException(status_code=403, detail="Access Denied: Invalid token")
    
    client_name = settings.get_client_name(token)
    logger.info(f"Успешная аутентификация для клиента: {client_name}")
    return token

def validate_required_params(
    host: str = Query(..., description="FTP/SFTP сервер", example="ftp.example.com"),
    user: str = Query(..., description="Имя пользователя", example="username"),
    password: str = Query(..., description="Пароль", example="password"),
    path: str = Query(..., description="Путь к файлу на сервере", example="/reports/data.xlsx"),
    protocol: str = Query(default="auto", description="Протокол: auto, ftp, ftps, sftp", example="auto")
):
    """Проверка и валидация обязательных параметров"""
    
    # Проверка режима деградации
    if settings.degraded_mode:
        raise HTTPException(
            status_code=503, 
            detail="Сервис запущен в режиме деградации - FTP функции недоступны"
        )
    
    # Санитация пути - защита от path traversal
    try:
        sanitized_path = sanitize_path(path)
    except ValueError as e:
        logger.warning(f"Отклонен небезопасный путь: {path} - {e}")
        raise HTTPException(status_code=400, detail=f"Недопустимый путь: {e}")
    
    # Извлечение имени файла из пути
    file_name = Path(sanitized_path).name
    if not file_name:
        raise HTTPException(status_code=400, detail="Имя файла не указано в пути")
    
    # Проверка разрешенных расширений
    if not settings.is_file_allowed(file_name):
        raise HTTPException(
            status_code=400, 
            detail=f"Недопустимое расширение файла. Разрешены: {', '.join(settings.allowed_extensions)}"
        )
    
    # Определение протокола
    if protocol == "auto":
        protocol = settings.default_protocol.value
    elif protocol not in ["ftp", "ftps", "sftp"]:
        raise HTTPException(status_code=400, detail="Недопустимый протокол. Используйте: ftp, ftps, sftp")
    
    # Проверка доступности SFTP
    if protocol == "sftp" and not SFTP_AVAILABLE:
        raise HTTPException(status_code=400, detail="SFTP поддержка недоступна. Установите paramiko.")
    
    return {
        "host": host,
        "user": user,
        "password": password,
        "path": sanitized_path,
        "file_name": file_name,
        "protocol": protocol
    }

async def download_with_storage_backend(params: dict) -> tuple[str, int]:
    """
    Универсальная загрузка файла через StorageBackend
    Возвращает (temp_file_path, file_size)
    """
    temp_file = None
    
    try:
        # Создание временного файла
        temp_fd, temp_file = tempfile.mkstemp(
            dir=settings.temp_dir,
            prefix=f'ftp_bridge_{params["protocol"]}_',
            suffix=f'_{params["file_name"]}'
        )
        os.close(temp_fd)
        
        # Маскирование пользовательских данных для логов
        masked_user = mask_user_info(params['user'])
        logger.info(f"Подключение к {params['protocol'].upper()} серверу: {params['host']} для пользователя: {masked_user}")
        
        def storage_operations():
            """Операции с хранилищем в executor"""
            # Создание бэкенда
            backend = StorageBackendFactory.create_backend(
                protocol=params['protocol'],
                host=params['host'],
                port=None,  # Будет использован порт по умолчанию
                user=params['user'],
                password=params['password'],
                timeout=settings.ftp_timeout,
                known_hosts_path=settings.known_hosts_path
            )
            
            with backend:
                # Получение размера файла
                file_size = backend.get_file_size(params['path'])
                
                # Проверка размера файла
                if file_size > settings.max_file_size:
                    raise ValueError(f"Файл слишком большой: {file_size} байт (максимум: {settings.max_file_size})")
                
                # Загрузка файла в поток
                with open(temp_file, 'wb') as local_stream:
                    downloaded_bytes = backend.download_to_stream(params['path'], local_stream)
                
                return downloaded_bytes
        
        # Выполнение операций в executor
        loop = asyncio.get_running_loop()
        downloaded_bytes = await loop.run_in_executor(None, storage_operations)
        
        # Финальная проверка размера файла
        actual_file_size = os.path.getsize(temp_file)
        if actual_file_size == 0:
            raise HTTPException(status_code=500, detail="Загруженный файл пуст")
        
        logger.info(f"Файл успешно загружен: {params['file_name']} ({actual_file_size} байт, протокол: {params['protocol']})")
        return temp_file, actual_file_size
        
    except HTTPException:
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)
        raise
    except Exception as e:
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)
        
        masked_user = mask_user_info(params['user'])
        logger.error(f"Ошибка загрузки файла '{params['file_name']}' для пользователя {masked_user}: {str(e)}")
        
        # Обработка различных типов ошибок
        if "Name or service not known" in str(e) or "Connection refused" in str(e):
            raise HTTPException(status_code=500, detail=f"Не удалось подключиться к серверу: {params['host']}")
        elif "530" in str(e) or "Login incorrect" in str(e) or "Authentication" in str(e):
            raise HTTPException(status_code=401, detail=f"Ошибка авторизации на сервере: {params['host']}")
        elif "550" in str(e) or "No such file" in str(e):
            raise HTTPException(status_code=404, detail=f"Файл не найден: {params['path']}")
        elif "not found in known_hosts" in str(e):
            raise HTTPException(status_code=400, detail="Ключ хоста не найден в known_hosts. Настройте KNOWN_HOSTS_PATH или добавьте ключ хоста.")
        else:
            raise HTTPException(status_code=500, detail=f"Ошибка {params['protocol'].upper()}: {str(e)}")

def file_streamer(file_path: str, file_size: int):
    """Генератор для стриминга файла по частям с автоматической настройкой chunk size"""
    # Автоматическая настройка размера чанка
    chunk_size = auto_tune_chunk_size(file_size, settings.chunk_size)
    
    logger.info(f"Стриминг файла с chunk_size: {chunk_size} байт (размер файла: {file_size} байт)")
    
    try:
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    finally:
        # Удаление временного файла после отправки
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
                logger.info(f"Временный файл удален: {file_path}")
            except Exception as e:
                logger.error(f"Ошибка удаления временного файла {file_path}: {e}")

@app.get("/")
async def root():
    """Корневой эндпоинт с информацией о сервисе"""
    return {
        "service": "FTP Bridge",
        "version": "2.1.0",
        "description": "Безопасный мост для интеграции FTP-серверов с Power BI",
        "endpoints": {
            "download": "/download",
            "head": "/download (HEAD method)",
            "health": "/health",
            "docs": "/docs"
        },
        "config": {
            "max_file_size_mb": settings.max_file_size // (1024 * 1024),
            "default_chunk_size_kb": settings.chunk_size // 1024,
            "protocols": ["ftp", "ftps"] + (["sftp"] if SFTP_AVAILABLE else []),
            "rate_limit_enabled": settings.rate_limit_enabled,
            "cors_origins": settings.cors_origins,
            "degraded_mode": settings.degraded_mode
        }
    }

@app.get("/health")
async def health_check():
    """Проверка состояния сервиса с расширенной диагностикой"""
    temp_dir_exists = os.path.exists(settings.temp_dir)
    temp_dir_writable = os.access(settings.temp_dir, os.W_OK) if temp_dir_exists else False
    
    # Определение общего статуса
    if settings.degraded_mode:
        status = "degraded"
    elif temp_dir_exists and temp_dir_writable:
        status = "healthy"
    else:
        status = "unhealthy"
    
    return {
        "status": status,
        "degraded_mode": settings.degraded_mode,
        "temp_dir": settings.temp_dir,
        "temp_dir_exists": temp_dir_exists,
        "temp_dir_writable": temp_dir_writable,
        "active_tokens": len(settings.client_tokens),
        "protocols_available": ["ftp", "ftps"] + (["sftp"] if SFTP_AVAILABLE else []),
        "rate_limit_enabled": settings.rate_limit_enabled,
        "default_protocol": settings.default_protocol.value,
        "sftp_host_key_verification": bool(settings.known_hosts_path)
    }

@app.head("/download")
async def head_download_file(
    request: Request,
    params: dict = Depends(validate_required_params),
    token: str = Depends(validate_token)
):
    """
    HEAD запрос для получения метаданных файла без его загрузки.
    Используется для preflight запросов от Power BI и других клиентов.
    """
    try:
        # Маскирование пользовательских данных для логов
        masked_user = mask_user_info(params['user'])
        logger.info(f"HEAD запрос к {params['protocol'].upper()} серверу: {params['host']} для пользователя: {masked_user}")
        
        def get_file_metadata():
            """Получение метаданных файла"""
            backend = StorageBackendFactory.create_backend(
                protocol=params['protocol'],
                host=params['host'],
                port=None,
                user=params['user'],
                password=params['password'],
                timeout=settings.ftp_timeout,
                known_hosts_path=settings.known_hosts_path
            )
            
            with backend:
                file_size = backend.get_file_size(params['path'])
                protocol_name = backend.get_protocol_name()
                return file_size, protocol_name
        
        # Выполнение операций в executor
        loop = asyncio.get_running_loop()
        file_size, protocol_name = await loop.run_in_executor(None, get_file_metadata)
        
        # Проверка размера файла
        if file_size > settings.max_file_size:
            raise HTTPException(
                status_code=413, 
                detail=f"Файл слишком большой: {file_size} байт (максимум: {settings.max_file_size})"
            )
        
        client_name = settings.get_client_name(token)
        logger.info(f"HEAD запрос обработан для клиента '{client_name}': {params['file_name']} "
                   f"(размер: {file_size} байт, протокол: {protocol_name})")
        
        # Возврат заголовков без тела ответа
        return StreamingResponse(
            iter([]),  # Пустой итератор для HEAD запроса
            status_code=200,
            headers={
                "X-File-Size": str(file_size),
                "X-Protocol": protocol_name,
                "X-File-Name": params['file_name'],
                "Content-Length": str(file_size),
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        masked_user = mask_user_info(params['user'])
        logger.error(f"Ошибка HEAD запроса для файла '{params['file_name']}' пользователя {masked_user}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения метаданных: {str(e)}")

# Rate limiting для основного эндпоинта (помимо дефолтного)
rate_limit_str = f"{settings.rate_limit_requests}/{settings.rate_limit_window}seconds" if settings.rate_limit_enabled else None

@app.get("/download")
@limiter.limit(rate_limit_str if rate_limit_str else "1000/second")  # Fallback если rate limiting отключен
async def download_file(
    request: Request,
    params: dict = Depends(validate_required_params),
    token: str = Depends(validate_token)
):
    """
    Загрузка файла с FTP/FTPS/SFTP сервера и отдача клиенту через стриминг
    
    Параметры:
    - host: FTP/SFTP сервер (например: ftp.example.com)
    - user: Имя пользователя
    - password: Пароль
    - path: Полный путь к файлу на сервере (например: /reports/data.xlsx)
    - protocol: Протокол (auto, ftp, ftps, sftp)
    - Authorization: Bearer токен в заголовке
    """
    
    try:
        # Загрузка файла через унифицированный бэкенд
        temp_file_path, file_size = await download_with_storage_backend(params)
        
        # Определение MIME типа
        file_extension = Path(params['file_name']).suffix.lower()
        mime_types = {
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.csv': 'text/csv',
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.zip': 'application/zip',
            '.json': 'application/json',
            '.xml': 'application/xml'
        }
        media_type = mime_types.get(file_extension, 'application/octet-stream')
        
        # Логирование успешной операции (с маскированием PII)
        client_name = settings.get_client_name(token)
        masked_user = mask_user_info(params['user'])
        logger.info(f"Отправка файла клиенту '{client_name}': {params['file_name']} "
                   f"(размер: {file_size} байт, протокол: {params['protocol']}, "
                   f"хост: {params['host']}, пользователь: {masked_user})")
        
        # Возврат стримингового ответа с оптимизированными заголовками
        return StreamingResponse(
            file_streamer(temp_file_path, file_size),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{params["file_name"]}"',
                "Content-Length": str(file_size),
                "Cache-Control": "no-cache",
                "X-File-Source": "FTP-Bridge",
                "X-File-Size": str(file_size),
                "X-Protocol-Used": params['protocol'],
                "X-Auto-Chunk-Tuned": "true" if file_size > 10 * 1024 * 1024 else "false",
                "Retry-After": "60"  # Для 429 ошибок rate limiting
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        masked_user = mask_user_info(params.get('user', 'unknown'))
        logger.error(f"Неожиданная ошибка при обработке файла '{params.get('file_name', 'unknown')}' "
                    f"для пользователя {masked_user}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.value.lower()
    ) 