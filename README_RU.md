# NEVEX — первый технический этап

Твой исходный интерфейс сохранён без изменений:
`frontend/gift_market_prototype.jsx`

Добавлены:
- FastAPI backend
- SQLite database
- Telegram Gifts collector
- получение Model / Pattern / Backdrop и rarity
- получение resale listings и цен
- JSON export
- API для будущего React frontend

## Что НЕ делаем пока
Покупки/продажи за реальные деньги, кошельки и вывод средств пока не включаем.
Сначала проверяем каталог и синхронизацию данных.

## Что нужно будет сделать тебе
Только установить Python и самостоятельно заполнить `.env` своими Telegram API ID/HASH.
Никому не отправляй пароль Telegram, код входа, API hash или bot token.

## Запуск

В папке `backend`:

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

Потом:
```bash
pip install -r requirements.txt
copy .env.example .env
```

Заполни:
```env
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
```

Запуск API:
```bash
python -m uvicorn app:app --reload
```

Проверка:
`http://127.0.0.1:8000/health`

Сбор данных:
```bash
python ../scripts/collect_telegram_gifts.py
```

Результат:
- `data/gifts.json`
- `data/nevex.db`
- `data/media/`

## Следующий этап
После проверки этого этапа подключим существующий React-интерфейс к `/api/gifts`, чтобы карточки перестали быть тестовыми.


## MRKT live prices
Frontend now reads only from the backend API and never replaces missing market prices with demo values. To enable authenticated MRKT sync, put your own MRKT API token in `backend/.env` as `MRKT_TOKEN` (never send the token here or commit it).


## Подключение live-цен MRKT
1. Скопируй `backend/.env.example` в `backend/.env`.
2. Впиши свой `MRKT_TOKEN` в `backend/.env`. Токен не отправляй в чат и не добавляй в React/frontend.
3. Перезапусти backend.
4. Обнови страницу NEVEX.

MRKT API требует авторизацию для получения списка актуальных объявлений; без токена NEVEX специально не подставляет выдуманные цены.


## Публичный сайт (production)
Frontend и backend могут работать с одного HTTPS-адреса. Это важно: браузер пользователя больше не обращается к `localhost:8000`.

Собрать frontend:
```bash
cd frontend-app
npm install
npm run build
```

После сборки скопировать содержимое `frontend-app/dist` в `backend/static`. Затем запустить:
```bash
cd ../backend
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Проверка: `http://127.0.0.1:8000/app`

Для постоянного публичного сайта нужен сервер/VPS или managed hosting. Quick Tunnel Cloudflare подходит только для временного теста.
