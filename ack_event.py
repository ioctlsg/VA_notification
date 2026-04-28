import json
import os
import sys

ACK_FILE = os.environ.get('ACK_FILE', '/tmp/frigate_notifier_ack.json')


def load_json(path: str):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return {}


def save_json(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def main():
    event_id = sys.argv[1].strip() if len(sys.argv) > 1 else ''
    if not event_id:
        print('usage: python ack_event.py <event_id>')
        sys.exit(1)

    ack_state = load_json(ACK_FILE)
    ack_state[event_id] = True
    save_json(ACK_FILE, ack_state)
    print(f'Acknowledged event {event_id}')


if __name__ == '__main__':
    main()
