from pyrogram import Client
import asyncio

# Вставьте сюда ваши данные
API_ID = 29882404
API_HASH = "78d0b7392746aa239403cea9d6bd36a1"


async def main():
    print("Генерируем сессию... Введите номер телефона и код, когда попросят.")
    # in_memory=True важно, чтобы сессия не сохранялась в файл, а вывелась в консоль
    app = Client("my_account", api_id=API_ID, api_hash=API_HASH, in_memory=True)

    await app.start()
    session_string = await app.export_session_string()
    print("\nВАША НОВАЯ СТРОКА СЕССИИ (скопируйте её полностью):\n")
    print(session_string)
    await app.stop()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())