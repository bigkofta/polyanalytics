"""
Telegram sender. Reads TG_BOT_TOKEN and TG_CHAT_ID from .env.

Setup:
  1. Message @BotFather -> /newbot -> get token -> add to .env as TG_BOT_TOKEN
  2. Message your bot anything -> run: python tg.py setup -> it finds your chat ID
  3. Add that ID to .env as TG_CHAT_ID
  4. Test: python tg.py "hello"
"""

import os, sys, requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
CHAT_ID   = os.environ.get('TG_CHAT_ID', '')

def send(text: str, parse_mode='Markdown') -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print('[TG] TG_BOT_TOKEN or TG_CHAT_ID not set in .env')
        return False
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': parse_mode},
            timeout=10
        )
        if not r.ok:
            print(f'[TG] Error {r.status_code}: {r.text}')
        return r.ok
    except Exception as e:
        print(f'[TG] Failed: {e}')
        return False


def get_chat_id() -> str:
    """Find your chat ID — message the bot first, then run this."""
    r = requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates', timeout=10)
    updates = r.json().get('result', [])
    if not updates:
        print('No messages found. Send your bot a message first, then re-run.')
        return ''
    chat_id = str(updates[-1]['message']['chat']['id'])
    print(f'Your chat ID: {chat_id}')
    print(f'Add this to .env:  TG_CHAT_ID={chat_id}')
    return chat_id


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'setup':
        get_chat_id()
    elif len(sys.argv) > 1:
        ok = send(' '.join(sys.argv[1:]))
        print('Sent.' if ok else 'Failed.')
    else:
        print(__doc__)
