# Защищённое облачное хранилище данных организации

Курсовая работа по дисциплине "Технология построения защищённых автоматизированных систем".

## Стек

- **Backend**: Python 3.11 + Django 4.2 + Django REST Framework
- **БД**: PostgreSQL
- **Аутентификация**: JWT (djangorestframework-simplejwt)
- **Шифрование файлов**: AES-128-CBC + HMAC (Fernet из библиотеки cryptography)

## Быстрый старт

```bash
# 1. Клонируем и создаём окружение
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Настраиваем окружение
cp .env.example .env
# Открываем .env и заполняем SECRET_KEY, данные БД

# 3. Создаём БД и применяем миграции
createdb secure_storage      # или через psql
python manage.py migrate

# 4. Создаём папки
mkdir -p logs media

# 5. Создаём суперпользователя
python manage.py createsuperuser

# 6. Запускаем сервер
python manage.py runserver
```

## API endpoints

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/v1/auth/register/` | Регистрация |
| POST | `/api/v1/auth/login/` | Вход (получение JWT) |
| POST | `/api/v1/auth/logout/` | Выход (инвалидация токена) |
| POST | `/api/v1/auth/token/refresh/` | Обновление access-токена |
| GET | `/api/v1/auth/me/` | Профиль текущего пользователя |
| GET | `/api/v1/auth/users/` | Список пользователей (admin) |
| GET | `/api/v1/files/` | Список доступных файлов |
| POST | `/api/v1/files/upload/` | Загрузка файла (с шифрованием) |
| GET | `/api/v1/files/<id>/` | Метаданные файла |
| GET | `/api/v1/files/<id>/download/` | Скачать файл (с расшифровкой) |
| DELETE | `/api/v1/files/<id>/delete/` | Удалить файл |
| POST | `/api/v1/files/<id>/share/` | Поделиться файлом |
| GET | `/api/v1/audit/` | Журнал аудита (admin) |

## Механизмы безопасности

1. **Аутентификация** — JWT с коротким временем жизни (60 мин) и rotate refresh tokens
2. **Авторизация** — RBAC: роли admin / manager / user
3. **Шифрование** — файлы шифруются AES перед сохранением на диск
4. **Целостность** — SHA-256 контрольная сумма каждого файла
5. **Аудит** — все действия пользователей записываются в неизменяемый журнал
6. **Rate limiting** — ограничение числа запросов (20/час для анонимов)
7. **Security headers** — XSS protection, HSTS, X-Frame-Options
8. **Blacklist токенов** — при logout refresh-токен блокируется

## Структура проекта

```
secure_storage/
├── config/          # Настройки Django (settings, urls, wsgi)
├── users/           # Пользователи, роли, аутентификация
├── files/           # Загрузка/скачивание файлов, шифрование
├── audit/           # Журнал аудита, middleware
├── logs/            # Лог-файлы (создать вручную)
├── media/           # Загруженные файлы (создать вручную)
├── .env.example     # Шаблон конфигурации
└── requirements.txt
```
