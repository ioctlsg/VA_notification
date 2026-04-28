import json
import os
import time
import uuid
import urllib.parse
import urllib.request
from urllib.error import URLError, HTTPError
from urllib.parse import quote_plus

FRIGATE_URL = os.environ.get('FRIGATE_URL', 'http://host.docker.internal:5000')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
CAMERA = os.environ.get('CAMERA', 'front_camera')
POLL_SECONDS = int(os.environ.get('POLL_SECONDS', '10'))
STATE_FILE = os.environ.get('STATE_FILE', '/tmp/frigate_notifier_last_id.txt')
SENT_FILE = os.environ.get('SENT_FILE', '/tmp/frigate_notifier_sent.json')
ACK_FILE = os.environ.get('ACK_FILE', '/tmp/frigate_notifier_ack.json')
MESSAGE_PREFIX = os.environ.get('MESSAGE_PREFIX', '').strip()
BOT_USERNAME = os.environ.get('BOT_USERNAME', '').strip()
ACK_BASE_URL = os.environ.get('ACK_BASE_URL', '').strip()


def load_last_id():
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ''


def save_last_id(v: str):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        f.write(v)


def load_sent_state():
    try:
        with open(SENT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return {}


def save_sent_state(data):
    with open(SENT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def load_ack_state():
    try:
        with open(ACK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return {}


def save_ack_state(data):
    with open(ACK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def active_key(camera: str, label: str):
    return f'{camera}:{label}'


def has_been_sent(event_id: str, sent_state: dict):
    return bool(sent_state.get(event_id, False))


def mark_sent_event(event_id: str, sent_state: dict):
    sent_state[event_id] = True
    save_sent_state(sent_state)


def build_ack_text(camera: str, event_id: str):
    if ACK_BASE_URL:
        sep = '&' if '?' in ACK_BASE_URL else '?'
        return f'Acknowledge: {ACK_BASE_URL}{sep}camera={quote_plus(camera)}&event_id={quote_plus(event_id)}'
    if BOT_USERNAME:
        return f'Acknowledge: https://t.me/{BOT_USERNAME}?start=ack_{quote_plus(event_id)}'
    return ''


def build_caption(camera: str, zone_text: str, event_id: str):
    prefix = f'{MESSAGE_PREFIX} ' if MESSAGE_PREFIX else ''
    caption = f'{prefix}Person detected on {camera}. Zones: {zone_text}\nEvent ID: {event_id}'
    ack_text = build_ack_text(camera, event_id)
    if ack_text:
        caption = f'{caption}\n{ack_text}'
    return caption


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.load(resp)


def fetch_bytes(url: str):
    with urllib.request.urlopen(url, timeout=20) as resp:
        return resp.read(), resp.headers.get_content_type() or 'image/jpeg'


def send_telegram_message(text: str):
    data = urllib.parse.urlencode({
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
    }).encode()
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
        data=data,
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def send_telegram_photo_bytes(photo_bytes: bytes, caption: str, mime_type: str = 'image/jpeg'):
    boundary = f'----JarvisBoundary{uuid.uuid4().hex}'
    body = bytearray()

    def add_field(name: str, value: str):
        body.extend(f'--{boundary}\r\n'.encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode())
        body.extend(b'\r\n')

    add_field('chat_id', TELEGRAM_CHAT_ID)
    add_field('caption', caption)

    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(b'Content-Disposition: form-data; name="photo"; filename="snapshot.jpg"\r\n')
    body.extend(f'Content-Type: {mime_type}\r\n\r\n'.encode())
    body.extend(photo_bytes)
    body.extend(b'\r\n')
    body.extend(f'--{boundary}--\r\n'.encode())

    req = urllib.request.Request(
        f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto',
        data=bytes(body),
        method='POST',
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def cooldown_key(camera: str, label: str):
    return f'{camera}:{label}'


def should_send(camera: str, label: str, now: float, last_sent: dict):
    key = cooldown_key(camera, label)
    previous = float(last_sent.get(key, 0))
    return (now - previous) >= COOLDOWN_SECONDS


def mark_sent(camera: str, label: str, now: float, last_sent: dict):
    last_sent[cooldown_key(camera, label)] = now
    save_last_sent(last_sent)


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID', flush=True)
        while True:
            time.sleep(60)

    last_id = load_last_id()
    sent_state = load_sent_state()
    ack_state = load_ack_state()
    print('Notifier started. Last event id:', last_id, flush=True)

    while True:
        try:
            events = fetch_json(f'{FRIGATE_URL}/api/events?limit=20&has_snapshot=1')
            events = list(reversed(events))
            for event in events:
                event_id = event.get('id', '')
                if not event_id or event_id == last_id:
                    continue
                if event.get('label') != 'person':
                    continue
                if event.get('camera') != CAMERA:
                    continue
                if not event.get('has_snapshot', True):
                    continue

                camera = event.get('camera', CAMERA)
                zones = event.get('entered_zones', []) or []
                zone_text = ', '.join(zones) if zones else 'none'
                snapshot_url = f'{FRIGATE_URL}/api/events/{event_id}/snapshot.jpg'

                if has_been_sent(event_id, sent_state):
                    print('Event already notified, suppressing alert for', event_id, flush=True)
                elif ack_state.get(event_id, False):
                    print('Event already acknowledged, suppressing alert for', event_id, flush=True)
                else:
                    caption = build_caption(camera, zone_text, event_id)
                    try:
                        photo_bytes, mime_type = fetch_bytes(snapshot_url)
                        send_telegram_photo_bytes(photo_bytes, caption, mime_type)
                        print('Sent photo alert for', event_id, flush=True)
                    except Exception as photo_err:
                        print('direct photo upload failed, falling back to text:', photo_err, flush=True)
                        send_telegram_message(caption)
                    mark_sent_event(event_id, sent_state)

                last_id = event_id
                save_last_id(event_id)

            time.sleep(POLL_SECONDS)
        except (URLError, HTTPError) as e:
            print('Network error:', e, flush=True)
            time.sleep(POLL_SECONDS)
        except Exception as e:
            print('Unexpected error:', e, flush=True)
            time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
