# FTP Bridge - Docker образ
FROM python:3.11-slim

# Метаданные
LABEL maintainer="FTP Bridge Team"
LABEL description="Безопасный мост для интеграции FTP-серверов с Power BI"
LABEL version="2.0.0"

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя приложения (безопасность)
RUN useradd --create-home --shell /bin/bash app

# Установка рабочей директории
WORKDIR /app

# Копирование зависимостей и их установка
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY . .

# Создание временного каталога
RUN mkdir -p ./temp && chown -R app:app ./temp

# Создание каталога для логов
RUN mkdir -p ./logs && chown -R app:app ./logs

# Изменение владельца файлов приложения
RUN chown -R app:app /app

# Переключение на пользователя приложения
USER app

# Настройка переменных окружения
ENV FTP_BRIDGE_HOST=0.0.0.0
ENV FTP_BRIDGE_PORT=8000
ENV FTP_BRIDGE_TEMP_DIR=./temp
ENV FTP_BRIDGE_LOG_FILE=./logs/ftp_bridge.log

# Экспозиция порта
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Запуск приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 