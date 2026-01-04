from telethon.sync import TelegramClient
from telethon.sessions import StringSession

API_ID = 29882404
API_HASH = "78d0b7392746aa239403cea9d6bd36a1"

def main():
    phone = input("Введите номер телефона (+7...): ").strip()
    with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        client.start(phone=phone)  # спросит код/2FA
        print("\nВаш STRING_SESSION:\n")
        print(client.session.save())

if __name__ == "__main__":
    main()