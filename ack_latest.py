import os
import sys

STATE_FILE = os.environ.get('STATE_FILE', '/tmp/frigate_notifier_last_id.txt')
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ACK_EVENT = os.path.join(SCRIPT_DIR, 'ack_event.py')


def main():
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            event_id = f.read().strip()
    except FileNotFoundError:
        event_id = ''

    if not event_id:
        print('No recent event to acknowledge.')
        sys.exit(1)

    os.execv(sys.executable, [sys.executable, ACK_EVENT, event_id])


if __name__ == '__main__':
    main()
