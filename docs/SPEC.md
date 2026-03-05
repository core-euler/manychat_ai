## 1. Обзор системы

### Цель
Заменить встроенный AI ManyChat на внешнюю языковую модель через CometAPI. Бот должен стабильно вести продажные диалоги на любом языке, держать контекст всей переписки и передавать клиента администратору в нужный момент.

### Каналы
- Instagram DM
- Facebook Messenger
- WhatsApp

### Стек
- **ManyChat Pro** — приём/отправка сообщений, триггеры
- **Backend сервер** — хранение истории, оркестрация запросов к LLM
- **CometAPI** — доступ к языковой модели (GPT-4 / Claude)
- **База данных** — хранение истории диалогов по contact_id

---

## 2. Архитектура

### ⚠️ Важно: асинхронная схема
ManyChat имеет жёсткий таймаут **10 секунд** на External Request. LLM отвечает дольше. Поэтому синхронная схема (ждём ответ LLM и возвращаем его в ManyChat) не работает.

Используется **асинхронная двухшаговая схема:**

```
[Клиент пишет сообщение]
        ↓
[ManyChat — Default Reply Флоу]
        ↓ External Request (POST)
[Backend — /webhook/manychat]
        ↓ немедленно отвечает 200 OK (< 1 сек)
        ↓ ManyChat отправляет клиенту "Секунду..."
        ↓ параллельно в фоне:
[Backend — собирает историю + system prompt]
        ↓
[CometAPI → LLM]
        ↓ ответ LLM (3–15 сек)
[Backend — обрабатывает ответ, проверяет HANDOFF]
        ↓ вызывает ManyChat API:
        ├── POST /fb/subscriber/setCustomField  (записывает ai_reply)
        └── POST /fb/sending/sendFlow           (триггерит флоу с ответом)
[ManyChat — Флоу "Send AI Reply"]
        ↓ отправляет {{ai_reply}} клиенту
[Клиент получает ответ]
```

### Два флоу в ManyChat
| Флоу | Назначение |
|------|-----------|
| `Default Reply` | Ловит входящее сообщение → External Request → отправляет "Секунду..." |
| `Send AI Reply` | Запускается через ManyChat API → отправляет `{{ai_reply}}` клиенту |

---

## 3. ManyChat — настройка

### 3.1 Флоу 1: Default Reply (входящие сообщения)

Настраивается на каждом канале (Instagram, FB, WhatsApp) как реакция на любое входящее сообщение.

**Шаги флоу:**
1. **Action: External Request** → POST на бэкенд (см. 3.2)
2. **Message block:** отправить текст `"Секунду, уже проверяю для вас информацию... 🖊️"` (или аналог на нужном языке — но т.к. язык неизвестен заранее, использовать нейтральный emoji или многоязычный текст)

> ⚠️ Response Mapping в этом флоу НЕ используется — бэкенд отвечает сразу и пусто, ответ придёт отдельно через API.

### 3.2 External Request (в Default Reply)

**Метод:** POST  
**URL:** `https://your-server.com/webhook/manychat`  
**Headers:** `Content-Type: application/json`

**Тело запроса (JSON):**
```json
{
  "contact_id": "{{contact.id}}",
  "channel": "{{channel}}",
  "first_name": "{{contact.first_name}}",
  "last_name": "{{contact.last_name}}",
  "last_input": "{{last_text_input}}"
}
```

**Response Mapping:** не настраивается (бэкенд возвращает `{"status": "ok"}`)

### 3.3 Флоу 2: Send AI Reply (отправка ответа)

Этот флоу **не имеет триггера** — запускается только через ManyChat API с бэкенда.

**Шаги флоу:**
1. **Message block:** отправить `{{ai_reply}}` (кастомное поле контакта)
2. **Условие:** если `{{handoff_flag}}` = `true` → передать диалог в Live Chat (Inbox)

### 3.4 Кастомные поля контакта

Создать в ManyChat (Settings → Custom Fields):

| Поле | Тип | Назначение |
|------|-----|-----------|
| `ai_reply` | Text | Ответ LLM для отправки клиенту |
| `handoff_flag` | Text | `true` если нужна передача администратору |

### 3.5 ManyChat API токен
Получить в: Settings → API → Generate Token  
Используется бэкендом для вызовов `/fb/subscriber/setCustomField` и `/fb/sending/sendFlow`

---

## 4. Backend — спецификация

### 4.1 Технологии
- **Runtime:** Node.js (или Python FastAPI — на выбор LLM)
- **БД:** SQLite (для простоты) или PostgreSQL
- **Хостинг:** любой VPS / Railway / Render

### 4.2 Эндпоинты

#### POST `/webhook/manychat`

**Входящие данные:**
```json
{
  "contact_id": "string",
  "channel": "instagram | facebook | whatsapp",
  "first_name": "string",
  "last_name": "string",
  "last_input": "string"
}
```

**Логика обработки (асинхронная):**

```
1. Немедленно ответить ManyChat: { "status": "ok" }  ← до 1 сек
2. В фоновом процессе (async/non-blocking):
   a. Загрузить историю диалога из БД по contact_id
   b. Добавить новое сообщение пользователя в историю
   c. Сформировать запрос к CometAPI: system prompt + история
   d. Получить ответ от LLM
   e. Проверить наличие тега [HANDOFF] в ответе
   f. Удалить [HANDOFF] из текста если есть, установить handoff_flag
   g. Обрезать текст до лимита канала (Instagram: 1000 симв, остальные: 2000)
   h. Сохранить ответ ассистента в историю БД
   i. Вызвать ManyChat API: setCustomField (ai_reply, handoff_flag)
   j. Вызвать ManyChat API: sendFlow ("Send AI Reply", contact_id)
```

**Немедленный ответ бэкенда (шаг 1):**
```json
{ "status": "ok" }
```

#### POST `/manychat-callback` (внутренний)
Внутренний метод для шагов i-j. Вызывает ManyChat Public API:

```
PATCH https://api.manychat.com/fb/subscriber/setCustomField
Authorization: Bearer <MANYCHAT_API_TOKEN>

{
  "subscriber_id": "<contact_id>",
  "field_name": "ai_reply",
  "field_value": "<текст ответа>"
}
```

```
POST https://api.manychat.com/fb/sending/sendFlow
Authorization: Bearer <MANYCHAT_API_TOKEN>

{
  "subscriber_id": "<contact_id>",
  "flow_ns": "<namespace флоу Send AI Reply>"
}
```

#### GET `/health`
Проверка работоспособности. Возвращает `{"status": "ok"}`.

### 4.3 Схема БД

**Таблица `conversations`:**
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER PK | |
| contact_id | TEXT | ID контакта из ManyChat |
| role | TEXT | `user` или `assistant` |
| content | TEXT | Текст сообщения |
| created_at | TIMESTAMP | Время сообщения |

**Индекс:** по `contact_id` + `created_at`

### 4.4 Управление историей
- Загружать последние **20-30 сообщений** по `contact_id` — не всю историю
- При первом сообщении контакта — история пуста, начинается с нуля
- История хранится бессрочно (клиент может вернуться через 2 недели — бот вспомнит)

### 4.5 Конфигурация (.env)
```
MANYCHAT_API_TOKEN=...
COMET_API_KEY=...
COMET_API_URL=...
COMET_MODEL=...
DB_PATH=./db/conversations.sqlite
PORT=3000
```

---

## 5. Интеграция CometAPI

**Документация CometAPI:** `[ВСТАВИТЬ ССЫЛКУ]`  
**Базовый URL:** `[ВСТАВИТЬ]`  
**Авторизация:** `[ВСТАВИТЬ — Bearer token / API key]`  

### 5.1 Формат запроса к LLM
```json
{
  "model": "[ВСТАВИТЬ — название модели из CometAPI]",
  "max_tokens": 500,
  "messages": [
    { "role": "system", "content": "<SYSTEM_PROMPT>" },
    { "role": "user", "content": "Сообщение 1" },
    { "role": "assistant", "content": "Ответ 1" },
    { "role": "user", "content": "Последнее сообщение клиента" }
  ]
}
```

### 5.3 ManyChat Public API

**Документация (Swagger):** https://api.manychat.com/swagger  
**Используемые эндпоинты:**
- `POST /fb/subscriber/setCustomField` — записать `ai_reply` и `handoff_flag`
- `POST /fb/sending/sendFlow` — запустить флоу "Send AI Reply"

**Авторизация:** Bearer токен из Settings → API в аккаунте клиента

### 5.4 Ограничения каналов
- Instagram: максимум **1000 символов** в одном сообщении
- Facebook / WhatsApp: максимум **2000 символов**

Бэкенд должен обрезать ответ LLM если превышен лимит, либо передавать ограничение в system prompt.

---

## 6. System Prompt

System prompt формируется единожды и передаётся в каждый запрос к LLM.  
Содержит полный скрипт работы бота предоставленный клиентом.

### 6.1 Флаг handoff
В конец system prompt добавить инструкцию:

```
Если в диалоге требуется передать клиента администратору (кавер-ап, 
согласование времени, депозит, нестандартный запрос, неуверенность в ответе) — 
завершай ответ строго тегом: [HANDOFF]
Бэкенд обнаружит этот тег, удалит его из текста и выставит флаг handoff: true.
```

### 6.2 Хранение промпта
System prompt хранится в отдельном файле `system_prompt.txt` на сервере.  
При необходимости обновления — замена файла без деплоя кода.

---

## 7. Сценарии тестирования

После деплоя проверить следующие сценарии вручную:

| # | Сценарий | Ожидаемый результат |
|---|----------|---------------------|
| 1 | Приветствие на русском | Ответ на русском, запрос имени |
| 2 | Приветствие на английском | Ответ на английском, без смешивания языков |
| 3 | Запрос цены сразу | Бот сначала уточняет детали, цена в конце |
| 4 | Татуировка реализм | Бот упоминает мастера с опытом, предлагает примеры работ |
| 5 | Кавер-ап запрос | Бот запрашивает фото, передаёт администратору [HANDOFF] |
| 6 | "Дорого" возражение | Бот объясняет ценность, спрашивает бюджет |
| 7 | Согласование времени | Бот НЕ называет время, передаёт администратору |
| 8 | Длинный диалог (10+ сообщений) | Бот помнит имя клиента, стиль, детали тату |
| 9 | Смена языка в середине диалога | Бот переключается на новый язык |
| 10 | Клиент просит телефон | Бот даёт номер +382 68 534 562 |

---

## 8. Что предоставляет клиент

- [ ] Доступ Admin в ManyChat (инвайт-ссылка: Settings → Team Members → Invite)
- [ ] ManyChat API токен (Settings → API → Generate Token)
- [ ] API-ключ CometAPI (или используется ключ исполнителя с включением в стоимость)
- [ ] Финальная версия скрипта / промпта
- [ ] Подтверждение что ManyChat план — Pro

---

## 9. Что не входит в scope

- Изменение структуры существующих флоу ManyChat
- Разработка новых скриптов продаж
- Интеграция с системой онлайн-записи или CRM
- Поддержка после сдачи (обсуждается отдельно)
