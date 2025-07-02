"""
Абстрактная архитектура для подключения к различным системам хранения файлов.
Устраняет дублирование кода между FTP, FTPS и SFTP реализациями.
"""

import os
import re
import tempfile
from abc import ABC, abstractmethod
from ftplib import FTP, FTP_TLS
from pathlib import Path
from typing import BinaryIO, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class StorageBackend(ABC):
    """Абстрактный базовый класс для систем хранения файлов"""
    
    def __init__(self, host: str, port: int, user: str, password: str, timeout: int = 30):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.timeout = timeout
        self.connection = None
    
    @abstractmethod
    def connect(self) -> None:
        """Установка соединения с сервером"""
        pass
    
    @abstractmethod
    def get_file_size(self, remote_path: str) -> int:
        """Получение размера файла на сервере"""
        pass
    
    @abstractmethod
    def download_to_stream(self, remote_path: str, local_stream: BinaryIO) -> int:
        """Загрузка файла в поток, возвращает количество байт"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Закрытие соединения"""
        pass
    
    @abstractmethod
    def get_protocol_name(self) -> str:
        """Возвращает название протокола"""
        pass
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class FTPBackend(StorageBackend):
    """Реализация для обычного FTP"""
    
    def connect(self) -> None:
        """Подключение к FTP серверу"""
        try:
            self.connection = FTP()
            self.connection.connect(self.host, self.port, self.timeout)
            self.connection.login(self.user, self.password)
            logger.info(f"⚠️  UNSAFE: Подключение к незащищенному FTP серверу {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Ошибка подключения к FTP серверу {self.host}:{self.port}: {e}")
            raise ConnectionError(f"Не удалось подключиться к FTP серверу: {e}")
    
    def get_file_size(self, remote_path: str) -> int:
        """Получение размера файла через FTP SIZE команду"""
        try:
            return self.connection.size(remote_path)
        except Exception as e:
            logger.warning(f"Не удалось получить размер файла {remote_path}: {e}")
            return 0
    
    def download_to_stream(self, remote_path: str, local_stream: BinaryIO) -> int:
        """Загрузка файла через FTP в поток"""
        total_bytes = 0
        
        def write_to_stream(data):
            nonlocal total_bytes
            bytes_written = local_stream.write(data)
            total_bytes += bytes_written
        
        try:
            self.connection.retrbinary(f'RETR {remote_path}', write_to_stream)
            return total_bytes
        except Exception as e:
            logger.error(f"Ошибка загрузки файла {remote_path}: {e}")
            raise
    
    def close(self) -> None:
        """Закрытие FTP соединения"""
        if self.connection:
            try:
                self.connection.quit()
            except Exception:
                # Игнорируем ошибки при закрытии
                pass
            finally:
                self.connection = None
    
    def get_protocol_name(self) -> str:
        return "ftp"

class FTPSBackend(StorageBackend):
    """Реализация для зашифрованного FTPS"""
    
    def connect(self) -> None:
        """Подключение к FTPS серверу"""
        try:
            self.connection = FTP_TLS()
            self.connection.connect(self.host, self.port, self.timeout)
            self.connection.login(self.user, self.password)
            # Переключение в защищенный режим для передачи данных
            self.connection.prot_p()
            logger.info(f"🔒 Безопасное подключение к FTPS серверу {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Ошибка подключения к FTPS серверу {self.host}:{self.port}: {e}")
            raise ConnectionError(f"Не удалось подключиться к FTPS серверу: {e}")
    
    def get_file_size(self, remote_path: str) -> int:
        """Получение размера файла через FTPS SIZE команду"""
        try:
            return self.connection.size(remote_path)
        except Exception as e:
            logger.warning(f"Не удалось получить размер файла {remote_path}: {e}")
            return 0
    
    def download_to_stream(self, remote_path: str, local_stream: BinaryIO) -> int:
        """Загрузка файла через FTPS в поток"""
        total_bytes = 0
        
        def write_to_stream(data):
            nonlocal total_bytes
            bytes_written = local_stream.write(data)
            total_bytes += bytes_written
        
        try:
            self.connection.retrbinary(f'RETR {remote_path}', write_to_stream)
            return total_bytes
        except Exception as e:
            logger.error(f"Ошибка загрузки файла {remote_path}: {e}")
            raise
    
    def close(self) -> None:
        """Закрытие FTPS соединения"""
        if self.connection:
            try:
                self.connection.quit()
            except Exception:
                # Игнорируем ошибки при закрытии
                pass
            finally:
                self.connection = None
    
    def get_protocol_name(self) -> str:
        return "ftps"

class SFTPClientWrapper:
    """Обертка для SFTP клиента с проверкой ключей хостов"""
    
    def __init__(self, host: str, port: int, user: str, password: str, timeout: int, known_hosts_path: Optional[str] = None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.timeout = timeout
        self.known_hosts_path = known_hosts_path
        self.client = None
        self.sftp = None
    
    def connect(self):
        """Подключение к SFTP серверу с проверкой ключей хостов"""
        try:
            import paramiko
        except ImportError:
            raise ImportError("Для SFTP требуется библиотека paramiko: pip install paramiko")
        
        try:
            self.client = paramiko.SSHClient()
            
            # Загрузка известных ключей хостов
            if self.known_hosts_path and os.path.exists(self.known_hosts_path):
                self.client.load_host_keys(self.known_hosts_path)
                logger.info(f"🔑 Загружены ключи хостов из {self.known_hosts_path}")
            else:
                # Загрузка системных известных ключей
                self.client.load_system_host_keys()
                logger.warning(f"⚠️  Используются системные ключи хостов. Рекомендуется настроить KNOWN_HOSTS_PATH")
            
            # Настройка политики для неизвестных ключей
            if self.known_hosts_path:
                # Строгая проверка - отклоняем неизвестные ключи
                self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
            else:
                # В режиме разработки можем добавлять новые ключи
                self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                logger.warning("⚠️  AutoAddPolicy включена. Не используйте в продакшене!")
            
            # Подключение
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                timeout=self.timeout,
                look_for_keys=False  # Не используем SSH ключи, только пароль
            )
            
            self.sftp = self.client.open_sftp()
            logger.info(f"🔐 Безопасное подключение к SFTP серверу {self.host}:{self.port}")
            
        except paramiko.AuthenticationException:
            raise ConnectionError(f"Ошибка аутентификации на SFTP сервере {self.host}")
        except paramiko.SSHException as e:
            if "not found in known_hosts" in str(e).lower():
                raise ConnectionError(f"Ключ хоста {self.host} не найден в known_hosts. Добавьте ключ или настройте KNOWN_HOSTS_PATH")
            raise ConnectionError(f"SSH ошибка при подключении к {self.host}: {e}")
        except Exception as e:
            raise ConnectionError(f"Не удалось подключиться к SFTP серверу {self.host}: {e}")
    
    def get_file_size(self, remote_path: str) -> int:
        """Получение размера файла через SFTP"""
        try:
            stat = self.sftp.stat(remote_path)
            return stat.st_size
        except Exception as e:
            logger.warning(f"Не удалось получить размер файла {remote_path}: {e}")
            return 0
    
    def download_to_stream(self, remote_path: str, local_stream: BinaryIO) -> int:
        """Загрузка файла через SFTP в поток"""
        try:
            with self.sftp.open(remote_path, 'rb') as remote_file:
                total_bytes = 0
                while True:
                    data = remote_file.read(65536)  # 64KB чанки
                    if not data:
                        break
                    bytes_written = local_stream.write(data)
                    total_bytes += bytes_written
                return total_bytes
        except Exception as e:
            logger.error(f"Ошибка загрузки файла {remote_path}: {e}")
            raise
    
    def close(self):
        """Закрытие SFTP соединения"""
        if self.sftp:
            try:
                self.sftp.close()
            except Exception:
                pass
            finally:
                self.sftp = None
        
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            finally:
                self.client = None

class SFTPBackend(StorageBackend):
    """Реализация для зашифрованного SFTP"""
    
    def __init__(self, host: str, port: int, user: str, password: str, timeout: int = 30, known_hosts_path: Optional[str] = None):
        super().__init__(host, port, user, password, timeout)
        self.known_hosts_path = known_hosts_path
        self.sftp_client = None
    
    def connect(self) -> None:
        """Подключение к SFTP серверу"""
        self.sftp_client = SFTPClientWrapper(
            self.host, self.port, self.user, self.password, self.timeout, self.known_hosts_path
        )
        self.sftp_client.connect()
        self.connection = self.sftp_client  # Для совместимости
    
    def get_file_size(self, remote_path: str) -> int:
        """Получение размера файла"""
        return self.sftp_client.get_file_size(remote_path)
    
    def download_to_stream(self, remote_path: str, local_stream: BinaryIO) -> int:
        """Загрузка файла в поток"""
        return self.sftp_client.download_to_stream(remote_path, local_stream)
    
    def close(self) -> None:
        """Закрытие SFTP соединения"""
        if self.sftp_client:
            self.sftp_client.close()
            self.sftp_client = None
            self.connection = None
    
    def get_protocol_name(self) -> str:
        return "sftp"

class StorageBackendFactory:
    """Фабрика для создания бэкендов хранения"""
    
    @staticmethod
    def create_backend(
        protocol: str,
        host: str,
        port: Optional[int],
        user: str,
        password: str,
        timeout: int = 30,
        known_hosts_path: Optional[str] = None
    ) -> StorageBackend:
        """Создание бэкенда на основе протокола"""
        
        if protocol.lower() == "ftp":
            actual_port = port or 21
            return FTPBackend(host, actual_port, user, password, timeout)
        
        elif protocol.lower() == "ftps":
            actual_port = port or 990
            return FTPSBackend(host, actual_port, user, password, timeout)
        
        elif protocol.lower() == "sftp":
            actual_port = port or 22
            return SFTPBackend(host, actual_port, user, password, timeout, known_hosts_path)
        
        else:
            raise ValueError(f"Неподдерживаемый протокол: {protocol}")

def sanitize_path(path: str) -> str:
    """
    Санитайзер пути для защиты от path traversal атак.
    Валидный путь: начинается с /, содержит только безопасные символы.
    """
    if not path:
        raise ValueError("Путь не может быть пустым")
    
    # Проверка на валидный путь
    valid_path_pattern = r"^\/[\w\-\.\/]*$"
    if not re.match(valid_path_pattern, path):
        raise ValueError(f"Недопустимый путь: {path}. Разрешены только буквы, цифры, дефисы, точки и слеши.")
    
    # Дополнительные проверки безопасности
    if ".." in path:
        raise ValueError("Обнаружена попытка path traversal (..) в пути")
    
    if "//" in path:
        raise ValueError("Двойные слеши не допускаются в пути")
    
    # Нормализация пути
    normalized = os.path.normpath(path)
    
    # Убеждаемся что путь все еще начинается с /
    if not normalized.startswith('/'):
        normalized = '/' + normalized.lstrip('/')
    
    return normalized

def mask_user_info(user_string: str) -> str:
    """
    Маскирование пользовательских данных для логов (защита от PII).
    john@example.com -> j***@example.com
    """
    if not user_string:
        return user_string
    
    # Проверка на email
    if "@" in user_string:
        local, domain = user_string.split("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "*"
        else:
            masked_local = local[0] + "*" * (len(local) - 1)
        return f"{masked_local}@{domain}"
    
    # Обычное имя пользователя
    if len(user_string) <= 2:
        return user_string[0] + "*"
    else:
        return user_string[0] + "*" * (len(user_string) - 2) + user_string[-1]

def auto_tune_chunk_size(file_size: int, default_chunk_size: int = 8192) -> int:
    """
    Автоматическая настройка размера чанка на основе размера файла.
    Для файлов > 10MB увеличиваем chunk_size до 64KB для лучшей производительности.
    """
    # 10 MB порог
    large_file_threshold = 10 * 1024 * 1024
    
    if file_size > large_file_threshold:
        # Для больших файлов используем 64KB чанки
        return 64 * 1024
    else:
        # Для маленьких файлов используем настройку по умолчанию
        return default_chunk_size 