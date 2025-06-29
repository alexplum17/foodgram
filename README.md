# **Foodgram**

_Проект Foodgram — это веб-приложение для публикации кулинарных рецептов. Пользователи могут создавать рецепты, добавлять их в избранное, подписываться на других авторов и формировать список покупок для выбранных рецептов._

## **Описание проекта**
#### Foodgram позволяет пользователям:

- ###### Создавать, редактировать и удалять рецепты с изображениями и пошаговым описанием
- ###### Добавлять рецепты в избранное и список покупок
- ###### Подписываться на других пользователей
- ###### Скачивать список ингредиентов в форматах TXT, PDF или CSV
- ###### Использовать короткие ссылки для удобного доступа к рецептам

## **Стек технологий**
Проект реализован с использованием следующих технологий:

- **Python** (версия 3.9) — основной язык программирования
- **Django** (версия 4.2) — веб-фреймворк для создания API
- **Django REST framework** — для построения RESTful API
- **PostgreSQL** — реляционная база данных
- **Docker** — контейнеризация приложения
- **Nginx** — веб-сервер и прокси-сервер
- **React** — фронтенд-часть приложения
- **GitHub Actions** — CI/CD автоматизация

## **Развертывание проекта**
### **Локальная установка (для разработки)**

```
git clone https://git@github.com:alexplum17/foodgram.git
```

```
cd foodgram
```

```
cd backend
```

#### 2) Cоздать и активировать виртуальное окружение:

```
python -m venv venv
```

```
source venv/Scripts/activate 
```

#### 3) Установить зависимости из файла requirements.txt:

```
python.exe -m pip install --upgrade pip
```

```
pip install -r requirements.txt
```

#### 4) Выполнить миграции:

```
python manage.py migrate
```

#### 5) Запустить проект:

```
python manage.py runserver
```

### **Развертывание с Docker (production)**

#### 1) Установите Docker и Docker Compose на сервер
#### 2) Скопируйте файлы docker-compose.production.yml и .env на сервер в директорию проекта
#### 3) Запустите контейнеры:

```
docker compose -f docker-compose.production.yml up -d
```

#### 4) Выполните миграции и сбор статики:

```
docker compose -f docker-compose.production.yml exec backend python manage.py migrate
docker compose -f docker-compose.production.yml exec backend python manage.py collectstatic
```

# **Примеры запросов**:

### Создание нового рецепта:

```
POST /api/recipes/
{
 - "ingredients": [
   - {
        "id": 1123,
        "amount": 10
      }
 ],
 - "tags": [
    1,
    2
 ],
 - "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAgMAAABieywaAAAACVBMVEUAAAD///9fX1/S0ecCAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAACklEQVQImWNoAAAAggCByxOyYQAAAABJRU5ErkJggg==",
 - "name": "string",
 - "text": "string",
 - "cooking_time": 1
}
```
Этот запрос создаст новый рецепт с заданным названием, описанием, изображением, временем приготовления, ингредиентами, тегами, автором, а также иными полями.

### Добавление рецепта в избранное:

```
POST /api/recipes/{id}/favorite/

{
  "id": 0,
  "name": "string",
  "image": "http://foodgram.example.org/media/recipes/images/image.png",
  "cooking_time": 1
}
```
Замените {id} на id рецепта, чтобы добавить этот рецепт в избранное.


### Добавление рецепта в список покупок:

```
POST /api/recipes/{id}/shopping_cart/
```
Замените {id} на id рецепта, чтобы добавить этот рецепт в список покупок.


### Скачивание списка покупок в формате PDF:

```
GET /api/recipes/download_shopping_cart/?format=pdf
```
Этот запрос скачает список покупок в формате PDF. Также доступны запросы для скачивания списка покупок в форматах CSV и TXT.


### Подписка на пользователя:

```
POST /api/users/{id}/subscribe/
```
Замените {id} на id пользователя, чтобы подписаться на конкретного пользователя.


### Список всех запросов доступен по следующему адресу:*

```
/api/docs
```


# **CI/CD Pipeline**:

#### Проект использует GitHub Actions для автоматизации:

 - ###### Тестирование кода (flake8, unit-тесты)

 - ###### Сборка Docker-образов (бэкенд, фронтенд, nginx)

 - ###### Деплой на сервер при пуше в ветку main

 - ###### Уведомления в Telegram о успешном деплое

#### Конфигурация CI/CD находится в файле .github/workflows/main.yml и включает:

 - ###### Тестирование бэкенда с PostgreSQL

 - ###### Сборку и публикацию Docker-образов

 - ###### Деплой на сервер через SSH

 - ###### Отправку уведомлений в Telegram об успешном деплое


## *Требуемые Secrets для развертывания:*
```
DOCKER_USERNAME: Логин Docker Hub
DOCKER_PASSWORD: Пароль Docker Hub
HOST: IP/домен сервера
USER: SSH пользователь
SSH_KEY: Приватный ключ SSH
SSH_PASSPHRASE: Пароль для SSH ключа
TELEGRAM_TO: ID чата для уведомлений
TELEGRAM_TOKEN: Токен Telegram бота
```

## **Примечание**
Для работы с API необходимо использовать токены аутентификации. Убедитесь, что пользователь аутентифицирован перед выполнением операции.

Проект разработан **alexplum17**.
Ссылка на профиль в GitHub: **https://github.com/alexplum17**
Адрес сайта: **https://fdgrm.sytes.net/**