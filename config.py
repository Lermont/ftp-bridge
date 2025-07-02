"""
Конфигурация для FTP Bridge - Pydantic v2 BaseSettings
ВНИМАНИЕ: Все токены должны быть настроены через переменные окружения!
"""

import os
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Set
from enum import Enum

from pydantic import BaseSettings, Field, validator
from pydantic_settings import BaseSettings as PydanticBaseSettings

class LogLevel(str, Enum):
    """Уровни логирования"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ProtocolType(str, Enum):
    """Типы протоколов для подключения"""
    FTP = "ftp"
    FTPS = "ftps"
    SFTP = "sftp"

class Settings(PydanticBaseSettings):
    """Настройки приложения через Pydantic v2 BaseSettings"""
    
    # ====== ОСНОВНЫЕ НАСТРОЙКИ СЕРВЕРА ======
    host: str = Field(default="0.0.0.0", env="FTP_BRIDGE_HOST")
    port: int = Field(default=8000, ge=1, le=65535, env="FTP_BRIDGE_PORT")
    debug: bool = Field(default=False, env="FTP_BRIDGE_DEBUG")
    degraded_mode: bool = Field(default=False, env="FTP_BRIDGE_DEGRADED_MODE")
    
    # ====== БЕЗОПАСНОСТЬ И ТОКЕНЫ ======
    # КРИТИЧНО: Токены должны быть установлены через переменные окружения!
    client_tokens: Dict[str, str] = Field(default_factory=dict)
    min_token_length: int = Field(default=32, ge=16)
    
    # ====== CORS НАСТРОЙКИ ======
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        env="FTP_BRIDGE_CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, env="FTP_BRIDGE_CORS_CREDENTIALS")
    cors_allow_methods: List[str] = Field(default=["GET"], env="FTP_BRIDGE_CORS_METHODS")
    
    # ====== FTP/SFTP НАСТРОЙКИ ======
    default_protocol: ProtocolType = Field(default=ProtocolType.FTPS, env="FTP_BRIDGE_DEFAULT_PROTOCOL")
    use_ftps: bool = Field(default=True, env="FTP_BRIDGE_USE_FTPS")
    ftp_timeout: int = Field(default=30, ge=5, le=300, env="FTP_BRIDGE_FTP_TIMEOUT")
    ftp_port: int = Field(default=21, ge=1, le=65535, env="FTP_BRIDGE_FTP_PORT")
    sftp_port: int = Field(default=22, ge=1, le=65535, env="FTP_BRIDGE_SFTP_PORT")
    known_hosts_path: Optional[str] = Field(default=None, env="FTP_BRIDGE_KNOWN_HOSTS_PATH")
    
    # ====== ФАЙЛЫ И СТРИМИНГ ======
    temp_dir: str = Field(default="./temp", env="FTP_BRIDGE_TEMP_DIR")
    max_file_size: int = Field(default=1073741824, ge=1, env="FTP_BRIDGE_MAX_FILE_SIZE")  # 1GB
    chunk_size: int = Field(default=8192, ge=1024, le=1048576, env="FTP_BRIDGE_CHUNK_SIZE")  # 8KB
    cleanup_interval: int = Field(default=3600, ge=60, env="FTP_BRIDGE_CLEANUP_INTERVAL")  # 1 час
    
    # ====== RATE LIMITING ======
    rate_limit_enabled: bool = Field(default=True, env="FTP_BRIDGE_RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, ge=1, env="FTP_BRIDGE_RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=3600, ge=60, env="FTP_BRIDGE_RATE_LIMIT_WINDOW")  # 1 час
    
    # ====== ЛОГИРОВАНИЕ ======
    log_level: LogLevel = Field(default=LogLevel.INFO, env="FTP_BRIDGE_LOG_LEVEL")
    log_file: str = Field(default="ftp_bridge.log", env="FTP_BRIDGE_LOG_FILE")
    log_max_size: int = Field(default=10485760, ge=1048576, env="FTP_BRIDGE_LOG_MAX_SIZE")  # 10MB
    log_backup_count: int = Field(default=5, ge=1, le=20, env="FTP_BRIDGE_LOG_BACKUP_COUNT")
    log_rotation_enabled: bool = Field(default=True, env="FTP_BRIDGE_LOG_ROTATION")
    
    # ====== РАЗРЕШЕННЫЕ РАСШИРЕНИЯ ======
    allowed_extensions: Set[str] = Field(
        default={'.txt', '.csv', '.xlsx', '.xls', '.pdf', '.zip', '.json', '.xml', '.tsv', '.dat', '.log'},
        env="FTP_BRIDGE_ALLOWED_EXTENSIONS"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_client_tokens()
        self._validate_security_settings()
    
    def _load_client_tokens(self):
        """Загрузка токенов клиентов из переменных окружения"""
        tokens = {}
        
        # Загружаем токены из переменных окружения с префиксом FTP_BRIDGE_TOKEN_
        for key, value in os.environ.items():
            if key.startswith("FTP_BRIDGE_TOKEN_") and len(key) > 17:
                client_name = key[17:].replace("_", " ").title()  # FTP_BRIDGE_TOKEN_CLIENT1 -> Client1
                if len(value) >= self.min_token_length:
                    tokens[value] = client_name
                else:
                    raise ValueError(f"Токен для {client_name} слишком короткий (минимум {self.min_token_length} символов)")
        
        # Проверяем наличие токенов
        if not tokens:
            raise ValueError(
                "🚨 КРИТИЧЕСКАЯ ОШИБКА: Не найдено ни одного токена!\n"
                "Установите токены через переменные окружения:\n"
                "export FTP_BRIDGE_TOKEN_CLIENT1=your_secure_32_char_token_here\n"
                "export FTP_BRIDGE_TOKEN_POWERBI=another_secure_token_here\n\n"
                f"Минимальная длина токена: {self.min_token_length} символов\n"
                "Генерация токена: python -c \"import secrets; print(secrets.token_hex(16))\""
            )
        
        self.client_tokens = tokens
    
    def _validate_security_settings(self):
        """Валидация настроек безопасности"""
        issues = []
        
        # Проверка продакшен настроек
        if not self.debug:  # Продакшен режим
            if "*" in self.cors_origins or "http://localhost" in str(self.cors_origins):
                issues.append("В продакшене CORS должен быть ограничен конкретными доменами")
            
            if self.log_level == LogLevel.DEBUG:
                issues.append("В продакшене не следует использовать DEBUG уровень логирования")
        
        # Проверка токенов
        weak_tokens = [token for token in self.client_tokens.keys() if len(token) < 32]
        if weak_tokens:
            issues.append(f"Найдены токены короче 32 символов: {len(weak_tokens)} шт. Рекомендуется использовать более длинные токены")
        
        # Проверка протокола по умолчанию
        if self.default_protocol == ProtocolType.FTP:
            issues.append("⚠️  ВНИМАНИЕ: Включен небезопасный FTP протокол! Рекомендуется использовать FTPS или SFTP")
        
        # Проверка SFTP настроек
        if self.default_protocol == ProtocolType.SFTP and not self.known_hosts_path:
            issues.append("Для SFTP рекомендуется настроить KNOWN_HOSTS_PATH для проверки ключей хостов")
        
        if issues:
            print("⚠️  ПРЕДУПРЕЖДЕНИЯ БЕЗОПАСНОСТИ:")
            for issue in issues:
                print(f"   - {issue}")
            print()
    
    @validator('cors_origins', pre=True)
    def parse_cors_origins(cls, v):
        """Парсинг CORS origins из строки"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    @validator('cors_allow_methods', pre=True)
    def parse_cors_methods(cls, v):
        """Парсинг CORS методов из строки"""
        if isinstance(v, str):
            return [method.strip().upper() for method in v.split(',') if method.strip()]
        return v
    
    @validator('allowed_extensions', pre=True)
    def parse_allowed_extensions(cls, v):
        """Парсинг разрешенных расширений из строки"""
        if isinstance(v, str):
            extensions = [ext.strip().lower() for ext in v.split(',') if ext.strip()]
            return {ext if ext.startswith('.') else f'.{ext}' for ext in extensions}
        return v
    
    # ====== МЕТОДЫ ДЛЯ СОВМЕСТИМОСТИ ======
    
    @property
    def CLIENT_TOKENS(self) -> Dict[str, str]:
        """Совместимость со старым API"""
        return self.client_tokens
    
    @property
    def HOST(self) -> str:
        """Совместимость со старым API"""
        return self.host
    
    @property
    def PORT(self) -> int:
        """Совместимость со старым API"""
        return self.port
    
    @property
    def DEBUG(self) -> bool:
        """Совместимость со старым API"""
        return self.debug
    
    @property
    def USE_FTPS(self) -> bool:
        """Совместимость со старым API"""
        return self.use_ftps
    
    @property
    def FTP_TIMEOUT(self) -> int:
        """Совместимость со старым API"""
        return self.ftp_timeout
    
    @property
    def TEMP_DIR(self) -> str:
        """Совместимость со старым API"""
        return self.temp_dir
    
    @property
    def MAX_FILE_SIZE(self) -> int:
        """Совместимость со старым API"""
        return self.max_file_size
    
    @property
    def CHUNK_SIZE(self) -> int:
        """Совместимость со старым API"""
        return self.chunk_size
    
    @property
    def LOG_LEVEL(self) -> str:
        """Совместимость со старым API"""
        return self.log_level.value
    
    @property
    def LOG_FILE(self) -> str:
        """Совместимость со старым API"""
        return self.log_file
    
    def validate_token(self, token: str) -> bool:
        """Проверка валидности токена"""
        return token in self.client_tokens
    
    def get_client_name(self, token: str) -> str:
        """Получение имени клиента по токену"""
        return self.client_tokens.get(token, "Unknown Client")
    
    def is_file_allowed(self, filename: str) -> bool:
        """Проверка разрешенного расширения файла"""
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.allowed_extensions
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Генерация нового безопасного токена"""
        return secrets.token_hex(length // 2)  # hex дает в 2 раза больше символов


# Создание экземпляра настроек
try:
    settings = Settings()
except ValueError as e:
    print(f"❌ Ошибка конфигурации: {e}")
    exit(1)

# Создание необходимых каталогов
temp_path = Path(settings.temp_dir)
temp_path.mkdir(parents=True, exist_ok=True)

log_path = Path(settings.log_file).parent
log_path.mkdir(parents=True, exist_ok=True)

# Информация о загруженной конфигурации
if settings.debug:
    print(f"🔧 Конфигурация загружена:")
    print(f"   Токенов: {len(settings.client_tokens)}")
    print(f"   Протокол: {settings.default_protocol.value}")
    print(f"   CORS: {settings.cors_origins}")
    print(f"   Rate Limit: {settings.rate_limit_enabled}")
    print(f"   Макс. размер файла: {settings.max_file_size // (1024*1024)} MB") 