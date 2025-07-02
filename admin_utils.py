#!/usr/bin/env python3
"""
Административные утилиты для FTP Bridge v2.0.0
Управление токенами, мониторинг системы, обслуживание
"""

import os
import sys
import json
import time
import shutil
import argparse
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

def get_settings():
    """Получение настроек приложения"""
    try:
        from config import settings
        return settings
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        print("💡 Убедитесь что файл .env настроен правильно")
        sys.exit(1)

class TokenManager:
    """Управление токенами доступа"""
    
    def __init__(self):
        self.settings = get_settings()
    
    def list_tokens(self, output_format: str = "table") -> Dict:
        """Список всех токенов"""
        tokens_info = []
        
        for token, client_name in self.settings.client_tokens.items():
            # Оценка качества токена
            quality = self._assess_token_quality(token)
            
            tokens_info.append({
                "client_name": client_name,
                "token_preview": f"{token[:8]}{'*' * (len(token) - 8)}",
                "length": len(token),
                "quality": quality["level"],
                "issues": quality["issues"]
            })
        
        result = {
            "total_tokens": len(tokens_info),
            "tokens": tokens_info,
            "security_summary": self._get_security_summary()
        }
        
        if output_format == "json":
            return result
        else:
            self._print_tokens_table(result)
            return result
    
    def _assess_token_quality(self, token: str) -> Dict:
        """Оценка качества токена"""
        issues = []
        
        if len(token) < 16:
            issues.append("Слишком короткий (< 16 символов)")
        elif len(token) < 32:
            issues.append("Короткий (рекомендуется 32+ символов)")
        
        if token.lower() in ['password', 'secret', 'token', 'key']:
            issues.append("Слабый или предсказуемый")
        
        if len(set(token)) < len(token) * 0.6:
            issues.append("Низкая энтропия")
        
        # Определение уровня безопасности
        if not issues:
            level = "Отличный"
        elif len(issues) == 1 and "рекомендуется" in issues[0]:
            level = "Хороший"
        elif len(issues) <= 2:
            level = "Удовлетворительный"
        else:
            level = "Слабый"
        
        return {"level": level, "issues": issues}
    
    def _get_security_summary(self) -> Dict:
        """Сводка по безопасности токенов"""
        tokens = list(self.settings.client_tokens.keys())
        
        weak_tokens = sum(1 for token in tokens if len(token) < 16)
        short_tokens = sum(1 for token in tokens if 16 <= len(token) < 32)
        strong_tokens = sum(1 for token in tokens if len(token) >= 32)
        
        return {
            "total": len(tokens),
            "weak": weak_tokens,
            "short": short_tokens,
            "strong": strong_tokens,
            "recommendations": self._get_security_recommendations(weak_tokens, short_tokens)
        }
    
    def _get_security_recommendations(self, weak_count: int, short_count: int) -> List[str]:
        """Рекомендации по безопасности"""
        recommendations = []
        
        if weak_count > 0:
            recommendations.append(f"Замените {weak_count} слабых токенов")
        
        if short_count > 0:
            recommendations.append(f"Рассмотрите увеличение длины {short_count} коротких токенов")
        
        if not recommendations:
            recommendations.append("Конфигурация токенов безопасна")
        
        return recommendations
    
    def _print_tokens_table(self, data: Dict):
        """Вывод таблицы токенов"""
        print("🔑 ТОКЕНЫ ДОСТУПА")
        print("=" * 80)
        
        if not data["tokens"]:
            print("❌ Токены не найдены")
            return
        
        # Заголовок таблицы
        print(f"{'Клиент':<20} {'Токен':<20} {'Длина':<6} {'Качество':<15} {'Проблемы'}")
        print("-" * 80)
        
        # Данные токенов
        for token_info in data["tokens"]:
            issues_str = ", ".join(token_info["issues"]) if token_info["issues"] else "Нет"
            print(f"{token_info['client_name']:<20} "
                  f"{token_info['token_preview']:<20} "
                  f"{token_info['length']:<6} "
                  f"{token_info['quality']:<15} "
                  f"{issues_str}")
        
        # Сводка безопасности
        summary = data["security_summary"]
        print("\n📊 СВОДКА БЕЗОПАСНОСТИ:")
        print(f"   Всего токенов: {summary['total']}")
        print(f"   Сильных (32+ символов): {summary['strong']}")
        print(f"   Коротких (16-31 символ): {summary['short']}")
        print(f"   Слабых (< 16 символов): {summary['weak']}")
        
        if summary["recommendations"]:
            print("\n💡 РЕКОМЕНДАЦИИ:")
            for rec in summary["recommendations"]:
                print(f"   - {rec}")
    
    def generate_token(self, length: int = 32, client_name: str = None) -> str:
        """Генерация нового токена"""
        if length < 16:
            print("⚠️  Минимальная длина токена: 16 символов")
            length = 16
        
        token = secrets.token_hex(length // 2)
        
        print(f"🔑 Новый токен сгенерирован:")
        print(f"   Длина: {len(token)} символов")
        print(f"   Токен: {token}")
        
        if client_name:
            env_var = f"FTP_BRIDGE_TOKEN_{client_name.upper().replace(' ', '_')}"
            print(f"\n📝 Добавьте в .env:")
            print(f"   {env_var}={token}")
        
        print("\n🔒 ВАЖНО:")
        print("   - Сохраните токен в безопасном месте")
        print("   - Не передавайте токен по незащищенным каналам")
        print("   - Регулярно меняйте токены")
        
        return token
    
    def validate_token(self, token: str) -> bool:
        """Проверка валидности токена"""
        is_valid = self.settings.validate_token(token)
        client_name = self.settings.get_client_name(token) if is_valid else None
        
        print(f"🔍 Проверка токена: {token[:8]}***")
        print(f"   Статус: {'✅ Валидный' if is_valid else '❌ Неверный'}")
        if client_name:
            print(f"   Клиент: {client_name}")
        
        return is_valid

class SystemMonitor:
    """Мониторинг системы"""
    
    def __init__(self):
        self.settings = get_settings()
    
    def health_check(self, output_format: str = "table") -> Dict:
        """Проверка состояния системы"""
        checks = []
        
        # Проверка временного каталога
        temp_dir_check = self._check_temp_directory()
        checks.append(temp_dir_check)
        
        # Проверка файлов логов
        log_check = self._check_log_files()
        checks.append(log_check)
        
        # Проверка конфигурации
        config_check = self._check_configuration()
        checks.append(config_check)
        
        # Проверка безопасности
        security_check = self._check_security_settings()
        checks.append(security_check)
        
        # Проверка производительности
        performance_check = self._check_performance_settings()
        checks.append(performance_check)
        
        # Сводка
        passed = sum(1 for check in checks if check["status"] == "OK")
        warnings = sum(1 for check in checks if check["status"] == "WARNING")
        errors = sum(1 for check in checks if check["status"] == "ERROR")
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "ERROR" if errors > 0 else "WARNING" if warnings > 0 else "OK",
            "checks": checks,
            "summary": {
                "total": len(checks),
                "passed": passed,
                "warnings": warnings,
                "errors": errors
            }
        }
        
        if output_format == "json":
            return result
        else:
            self._print_health_report(result)
            return result
    
    def _check_temp_directory(self) -> Dict:
        """Проверка временного каталога"""
        temp_path = Path(self.settings.temp_dir)
        
        if not temp_path.exists():
            return {
                "name": "Временный каталог",
                "status": "ERROR",
                "message": f"Каталог не существует: {temp_path}",
                "details": {"path": str(temp_path), "exists": False}
            }
        
        if not temp_path.is_dir():
            return {
                "name": "Временный каталог",
                "status": "ERROR",
                "message": f"Путь не является каталогом: {temp_path}",
                "details": {"path": str(temp_path), "is_directory": False}
            }
        
        if not os.access(temp_path, os.W_OK):
            return {
                "name": "Временный каталог",
                "status": "ERROR",
                "message": f"Нет прав записи: {temp_path}",
                "details": {"path": str(temp_path), "writable": False}
            }
        
        # Проверка свободного места
        free_space = shutil.disk_usage(temp_path).free
        free_space_mb = free_space // (1024 * 1024)
        
        if free_space_mb < 100:  # Менее 100 MB
            status = "WARNING"
            message = f"Мало свободного места: {free_space_mb} MB"
        else:
            status = "OK"
            message = f"Каталог готов, свободно: {free_space_mb} MB"
        
        return {
            "name": "Временный каталог",
            "status": status,
            "message": message,
            "details": {
                "path": str(temp_path),
                "exists": True,
                "writable": True,
                "free_space_mb": free_space_mb
            }
        }
    
    def _check_log_files(self) -> Dict:
        """Проверка файлов логов"""
        log_path = Path(self.settings.log_file)
        log_dir = log_path.parent
        
        if not log_dir.exists():
            return {
                "name": "Файлы логов",
                "status": "ERROR",
                "message": f"Каталог логов не существует: {log_dir}",
                "details": {"log_dir": str(log_dir), "exists": False}
            }
        
        if not os.access(log_dir, os.W_OK):
            return {
                "name": "Файлы логов",
                "status": "ERROR",
                "message": f"Нет прав записи в каталог логов: {log_dir}",
                "details": {"log_dir": str(log_dir), "writable": False}
            }
        
        details = {
            "log_file": str(log_path),
            "log_dir": str(log_dir),
            "rotation_enabled": self.settings.log_rotation_enabled,
            "max_size_mb": self.settings.log_max_size // (1024 * 1024),
            "backup_count": self.settings.log_backup_count
        }
        
        # Проверка размера текущего лога
        if log_path.exists():
            log_size = log_path.stat().st_size
            log_size_mb = log_size // (1024 * 1024)
            details["current_size_mb"] = log_size_mb
            
            if log_size > self.settings.log_max_size and not self.settings.log_rotation_enabled:
                return {
                    "name": "Файлы логов",
                    "status": "WARNING",
                    "message": f"Лог файл большой ({log_size_mb} MB), но ротация отключена",
                    "details": details
                }
        
        return {
            "name": "Файлы логов",
            "status": "OK",
            "message": "Настройки логирования корректны",
            "details": details
        }
    
    def _check_configuration(self) -> Dict:
        """Проверка конфигурации"""
        issues = []
        
        # Проверка токенов
        if len(self.settings.client_tokens) == 0:
            issues.append("Нет настроенных токенов")
        
        # Проверка портов
        if not (1 <= self.settings.port <= 65535):
            issues.append(f"Неверный порт: {self.settings.port}")
        
        # Проверка лимитов
        if self.settings.max_file_size < 1024 * 1024:  # Менее 1 MB
            issues.append("Очень маленький лимит размера файла")
        
        if issues:
            return {
                "name": "Конфигурация",
                "status": "ERROR",
                "message": f"Найдены проблемы: {', '.join(issues)}",
                "details": {"issues": issues}
            }
        
        return {
            "name": "Конфигурация",
            "status": "OK",
            "message": "Конфигурация корректна",
            "details": {
                "tokens_count": len(self.settings.client_tokens),
                "port": self.settings.port,
                "max_file_size_mb": self.settings.max_file_size // (1024 * 1024),
                "debug_mode": self.settings.debug
            }
        }
    
    def _check_security_settings(self) -> Dict:
        """Проверка настроек безопасности"""
        issues = []
        warnings = []
        
        # Проверка токенов
        weak_tokens = [token for token in self.settings.client_tokens.keys() if len(token) < 16]
        if weak_tokens:
            issues.append(f"Слабые токены: {len(weak_tokens)} шт.")
        
        short_tokens = [token for token in self.settings.client_tokens.keys() if 16 <= len(token) < 32]
        if short_tokens:
            warnings.append(f"Короткие токены: {len(short_tokens)} шт.")
        
        # Проверка CORS
        if not self.settings.debug and "*" in self.settings.cors_origins:
            issues.append("CORS разрешает любые домены в продакшене")
        
        # Проверка Rate Limiting
        if not self.settings.rate_limit_enabled:
            warnings.append("Rate limiting отключен")
        
        # Проверка протокола по умолчанию
        if self.settings.default_protocol.value == "ftp" and not self.settings.use_ftps:
            warnings.append("Используется незашифрованный FTP")
        
        if issues:
            status = "ERROR"
            message = f"Критические проблемы безопасности: {', '.join(issues)}"
        elif warnings:
            status = "WARNING"
            message = f"Предупреждения безопасности: {', '.join(warnings)}"
        else:
            status = "OK"
            message = "Настройки безопасности корректны"
        
        return {
            "name": "Безопасность",
            "status": status,
            "message": message,
            "details": {
                "issues": issues,
                "warnings": warnings,
                "cors_origins": self.settings.cors_origins,
                "rate_limit_enabled": self.settings.rate_limit_enabled,
                "default_protocol": self.settings.default_protocol.value,
                "use_ftps": self.settings.use_ftps
            }
        }
    
    def _check_performance_settings(self) -> Dict:
        """Проверка настроек производительности"""
        warnings = []
        
        # Проверка размера чанков
        if self.settings.chunk_size < 4096:  # Менее 4 KB
            warnings.append("Маленький размер чанков может снизить производительность")
        elif self.settings.chunk_size > 1024 * 1024:  # Более 1 MB
            warnings.append("Большой размер чанков может увеличить использование памяти")
        
        # Проверка таймаутов
        if self.settings.ftp_timeout < 10:
            warnings.append("Короткий FTP таймаут может привести к обрывам соединения")
        elif self.settings.ftp_timeout > 300:
            warnings.append("Длинный FTP таймаут может замедлить обработку ошибок")
        
        # Проверка Rate Limiting
        if self.settings.rate_limit_enabled and self.settings.rate_limit_requests > 1000:
            warnings.append("Высокий лимит запросов может не защитить от атак")
        
        status = "WARNING" if warnings else "OK"
        message = f"Предупреждения производительности: {', '.join(warnings)}" if warnings else "Настройки производительности оптимальны"
        
        return {
            "name": "Производительность",
            "status": status,
            "message": message,
            "details": {
                "warnings": warnings,
                "chunk_size_kb": self.settings.chunk_size // 1024,
                "ftp_timeout": self.settings.ftp_timeout,
                "rate_limit_requests": self.settings.rate_limit_requests if self.settings.rate_limit_enabled else None
            }
        }
    
    def _print_health_report(self, data: Dict):
        """Вывод отчета о состоянии системы"""
        print("🏥 СОСТОЯНИЕ СИСТЕМЫ")
        print("=" * 60)
        print(f"Проверка: {data['timestamp']}")
        print(f"Общий статус: {self._get_status_emoji(data['overall_status'])} {data['overall_status']}")
        print()
        
        # Детальные проверки
        for check in data["checks"]:
            emoji = self._get_status_emoji(check["status"])
            print(f"{emoji} {check['name']}: {check['status']}")
            print(f"   {check['message']}")
            
            if check.get("details") and isinstance(check["details"], dict):
                for key, value in check["details"].items():
                    if key not in ["issues", "warnings"]:
                        print(f"   {key}: {value}")
            print()
        
        # Сводка
        summary = data["summary"]
        print("📊 СВОДКА:")
        print(f"   ✅ Пройдено: {summary['passed']}")
        print(f"   ⚠️  Предупреждений: {summary['warnings']}")
        print(f"   ❌ Ошибок: {summary['errors']}")
        print(f"   📋 Всего проверок: {summary['total']}")
    
    def _get_status_emoji(self, status: str) -> str:
        """Эмодзи для статуса"""
        return {
            "OK": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌"
        }.get(status, "❓")

class MaintenanceTools:
    """Инструменты обслуживания"""
    
    def __init__(self):
        self.settings = get_settings()
    
    def cleanup_temp_files(self, max_age_hours: int = 24) -> Dict:
        """Очистка старых временных файлов"""
        temp_dir = Path(self.settings.temp_dir)
        
        if not temp_dir.exists():
            return {
                "status": "error",
                "message": f"Временный каталог не существует: {temp_dir}",
                "cleaned_files": 0,
                "freed_space_mb": 0
            }
        
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_files = 0
        freed_space = 0
        
        for file_path in temp_dir.glob("ftp_bridge_*"):
            try:
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    cleaned_files += 1
                    freed_space += file_size
            except Exception as e:
                print(f"⚠️  Не удалось удалить {file_path}: {e}")
        
        freed_space_mb = freed_space // (1024 * 1024)
        
        return {
            "status": "success",
            "message": f"Очищено {cleaned_files} файлов, освобождено {freed_space_mb} MB",
            "cleaned_files": cleaned_files,
            "freed_space_mb": freed_space_mb,
            "max_age_hours": max_age_hours
        }
    
    def validate_configuration(self) -> Dict:
        """Валидация конфигурации"""
        try:
            # Попытка создать новый экземпляр настроек
            from config import Settings
            test_settings = Settings()
            
            return {
                "status": "success",
                "message": "Конфигурация валидна",
                "details": {
                    "tokens_count": len(test_settings.client_tokens),
                    "protocols_available": ["ftp", "ftps"] + (["sftp"] if hasattr(test_settings, 'sftp_port') else [])
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Ошибка валидации: {str(e)}",
                "details": {"error": str(e)}
            }
    
    def backup_configuration(self, backup_dir: str = "backups") -> Dict:
        """Резервное копирование конфигурации"""
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_path / f"config_backup_{timestamp}.env"
        
        try:
            # Копирование .env файла
            env_file = Path(".env")
            if env_file.exists():
                shutil.copy2(env_file, backup_file)
                
                return {
                    "status": "success",
                    "message": f"Конфигурация сохранена в {backup_file}",
                    "backup_file": str(backup_file),
                    "timestamp": timestamp
                }
            else:
                return {
                    "status": "error",
                    "message": "Файл .env не найден",
                    "backup_file": None
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Ошибка создания резервной копии: {str(e)}",
                "backup_file": None
            }

def main():
    """Основная функция CLI"""
    parser = argparse.ArgumentParser(
        description="Административные утилиты FTP Bridge v2.0.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python admin_utils.py tokens list
  python admin_utils.py tokens generate --length 32 --client "Power BI"
  python admin_utils.py monitor health
  python admin_utils.py maintenance cleanup --max-age-hours 12
  python admin_utils.py maintenance validate
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")
    
    # Команды токенов
    tokens_parser = subparsers.add_parser("tokens", help="Управление токенами")
    tokens_subparsers = tokens_parser.add_subparsers(dest="tokens_action")
    
    # Список токенов
    list_parser = tokens_subparsers.add_parser("list", help="Список токенов")
    list_parser.add_argument("--json", action="store_true", help="Вывод в JSON формате")
    
    # Генерация токена
    generate_parser = tokens_subparsers.add_parser("generate", help="Генерация нового токена")
    generate_parser.add_argument("--length", type=int, default=32, help="Длина токена (по умолчанию: 32)")
    generate_parser.add_argument("--client", help="Имя клиента")
    
    # Валидация токена
    validate_parser = tokens_subparsers.add_parser("validate", help="Проверка токена")
    validate_parser.add_argument("token", help="Токен для проверки")
    
    # Команды мониторинга
    monitor_parser = subparsers.add_parser("monitor", help="Мониторинг системы")
    monitor_subparsers = monitor_parser.add_subparsers(dest="monitor_action")
    
    # Health check
    health_parser = monitor_subparsers.add_parser("health", help="Проверка состояния системы")
    health_parser.add_argument("--json", action="store_true", help="Вывод в JSON формате")
    
    # Команды обслуживания
    maintenance_parser = subparsers.add_parser("maintenance", help="Обслуживание системы")
    maintenance_subparsers = maintenance_parser.add_subparsers(dest="maintenance_action")
    
    # Очистка временных файлов
    cleanup_parser = maintenance_subparsers.add_parser("cleanup", help="Очистка временных файлов")
    cleanup_parser.add_argument("--max-age-hours", type=int, default=24, help="Максимальный возраст файлов в часах")
    
    # Валидация конфигурации
    maintenance_subparsers.add_parser("validate", help="Валидация конфигурации")
    
    # Резервное копирование
    backup_parser = maintenance_subparsers.add_parser("backup", help="Резервное копирование конфигурации")
    backup_parser.add_argument("--dir", default="backups", help="Каталог для резервных копий")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        # Выполнение команд
        if args.command == "tokens":
            token_manager = TokenManager()
            
            if args.tokens_action == "list":
                token_manager.list_tokens("json" if args.json else "table")
            elif args.tokens_action == "generate":
                token_manager.generate_token(args.length, args.client)
            elif args.tokens_action == "validate":
                token_manager.validate_token(args.token)
            else:
                tokens_parser.print_help()
        
        elif args.command == "monitor":
            monitor = SystemMonitor()
            
            if args.monitor_action == "health":
                result = monitor.health_check("json" if args.json else "table")
                if args.json:
                    print(json.dumps(result, indent=2))
            else:
                monitor_parser.print_help()
        
        elif args.command == "maintenance":
            maintenance = MaintenanceTools()
            
            if args.maintenance_action == "cleanup":
                result = maintenance.cleanup_temp_files(args.max_age_hours)
                print(f"🧹 {result['message']}")
            elif args.maintenance_action == "validate":
                result = maintenance.validate_configuration()
                emoji = "✅" if result["status"] == "success" else "❌"
                print(f"{emoji} {result['message']}")
            elif args.maintenance_action == "backup":
                result = maintenance.backup_configuration(args.dir)
                emoji = "✅" if result["status"] == "success" else "❌"
                print(f"{emoji} {result['message']}")
            else:
                maintenance_parser.print_help()
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\n👋 Операция прервана пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 