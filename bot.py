import os
import asyncio
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TOKEN")

bot = Bot(TOKEN)
dp = Dispatcher()

# --- память (для личного использования) ---
favorites = {}   # user_id: set(manga_id)
progress = {}    # user_id: (manga_id, chapter_id)

# ---------- START ----------
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer(
        "📚 Манхва-ридер\n\n"
        "Напиши название манхвы\n\n"
        "⭐ /favorites — избранное\n"
        "▶️ /continue — продолжить чтение"
    )

# ---------- SEARCH ----------
@dp.message()
async def search(msg: types.Message):
    r = requests.get(
        "https://api.mangadex.org/manga",
        params={"title": msg.text, "limit": 5}
    ).json()

    if not r.get("data"):
        await msg.answer("❌ Ничего не найдено")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for m in r["data"]:
        title = m["attributes"]["title"].get("en", "Без названия")
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=title,
                callback_data=f"m_{m['id']}"
            )
        ])

    await msg.answer("🔍 Найдено:", reply_markup=kb)

# ---------- CHAPTERS ----------
@dp.callback_query(lambda c: c.data.startswith("m_"))
async def chapters(call: types.CallbackQuery):
    manga_id = call.data.split("_")[1]

    # кнопка избранного
    fav_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("⭐ В избранное", callback_data=f"fav_{manga_id}")]
    ])
    await call.message.answer("📖 Загружаю главы...", reply_markup=fav_kb)

    # сначала RU, потом EN
    for lang in ["ru", "en"]:
        r = requests.get(
            "https://api.mangadex.org/chapter",
            params={
                "manga": manga_id,
                "translatedLanguage[]": [lang],
                "order[chapter]": "asc",
                "limit": 20
            }
        ).json()

        if r.get("data"):
            kb = InlineKeyboardMarkup(inline_keyboard=[])
            for ch in r["data"]:
                num = ch["attributes"]["chapter"] or "?"
                kb.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=f"Глава {num} ({lang.upper()})",
                        callback_data=f"c_{manga_id}_{ch['id']}"
                    )
                ])
            await call.message.answer("📖 Выбери главу:", reply_markup=kb)
            break

    await call.answer()

# ---------- ADD FAVORITE ----------
@dp.callback_query(lambda c: c.data.startswith("fav_"))
async def add_favorite(call: types.CallbackQuery):
    manga_id = call.data.split("_")[1]
    user = call.from_user.id

    favorites.setdefault(user, set()).add(manga_id)
    await call.answer("⭐ Добавлено в избранное")

# ---------- READ ----------
@dp.callback_query(lambda c: c.data.startswith("c_"))
async def read(call: types.CallbackQuery):
    _, manga_id, chapter_id = call.data.split("_")
    user = call.from_user.id

    progress[user] = (manga_id, chapter_id)

    r = requests.get(
        f"https://api.mangadex.org/at-home/server/{chapter_id}"
    ).json()

    base = r["baseUrl"]
    h = r["chapter"]["hash"]
    pages = r["chapter"]["data"]

    await call.message.answer("📖 Чтение главы:")

    for page in pages:
        await bot.send_photo(
            call.message.chat.id,
            f"{base}/data/{h}/{page}"
        )

    await call.answer()

# ---------- FAVORITES ----------
@dp.message(Command("favorites"))
async def show_favorites(msg: types.Message):
    user = msg.from_user.id
    favs = favorites.get(user)

    if not favs:
        await msg.answer("⭐ Избранное пусто")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for manga_id in favs:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"📘 {manga_id[:8]}...",
                callback_data=f"m_{manga_id}"
            )
        ])

    await msg.answer("⭐ Твоё избранное:", reply_markup=kb)

# ---------- CONTINUE ----------
@dp.message(Command("continue"))
async def cont(msg: types.Message):
    user = msg.from_user.id

    if user not in progress:
        await msg.answer("❌ Нет сохранённого чтения")
        return

    manga_id, chapter_id = progress[user]
    await msg.answer("▶️ Продолжаю чтение...")

    await read(types.CallbackQuery(
        id="0",
        from_user=msg.from_user,
        chat_instance="",
        message=msg,
        data=f"c_{manga_id}_{chapter_id}"
    ))

# ---------- RUN ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
