import os
import time
import requests
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import json
from urllib.parse import parse_qs

DISCORD_PUBLIC_KEY = os.environ.get('DISCORD_PUBLIC_KEY')
METAFORGE_API = 'https://metaforge.app/api/arc-raiders/events-schedule'

event_cache = {
    'data': None,
    'timestamp': 0
}
CACHE_DURATION = 300


def verify_discord_signature(signature, timestamp, body):
    """Verify Ed25519 signature from Discord"""
    try:
        verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        verify_key.verify(f'{timestamp}{body}'.encode(), bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError):
        return False


def get_events():
    """Fetch events from MetaForge API with 5-minute cache"""
    current_time = time.time()

    if event_cache['data'] and (current_time - event_cache['timestamp']) < CACHE_DURATION:
        return event_cache['data']

    try:
        response = requests.get(METAFORGE_API, timeout=10)
        response.raise_for_status()
        data = response.json()

        event_cache['data'] = data.get('data', [])
        event_cache['timestamp'] = current_time

        return event_cache['data']
    except requests.RequestException:
        return event_cache['data'] if event_cache['data'] else []


def format_map_status():
    """Format events into Discord message"""
    events = get_events()

    if not events:
        return 'Unable to fetch event data. Please try again later.'

    current_time = int(time.time() * 1000)

    active_events = []
    upcoming_events = []

    for event in events:
        if event['startTime'] <= current_time < event['endTime']:
            active_events.append(event)
        elif event['startTime'] > current_time:
            upcoming_events.append(event)

    active_events.sort(key=lambda x: x['endTime'])
    upcoming_events.sort(key=lambda x: x['startTime'])

    lines = []

    if active_events:
        end_time_seconds = active_events[0]['endTime'] // 1000
        lines.append(f"ACTIVE NOW (ends <t:{end_time_seconds}:R>)")

        active_group = [active_events[0]]
        for event in active_events[1:]:
            if event['endTime'] == active_events[0]['endTime']:
                active_group.append(event)

        for event in active_group:
            lines.append(f"> **{event['name']}** - {event['map']}")
        lines.append("")

    if upcoming_events:
        start_time_seconds = upcoming_events[0]['startTime'] // 1000
        lines.append(f"UP NEXT (starts <t:{start_time_seconds}:R>)")

        next_group = [upcoming_events[0]]
        for event in upcoming_events[1:]:
            if event['startTime'] == upcoming_events[0]['startTime']:
                next_group.append(event)

        for event in next_group:
            lines.append(f"> **{event['name']}** - {event['map']}")

    if not active_events and not upcoming_events:
        return 'No active or upcoming events found.'

    return '\n'.join(lines)


def handler(environ, start_response):
    """Vercel WSGI handler"""
    method = environ.get('REQUEST_METHOD', 'GET')

    if method == 'GET':
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'Discord bot is running']

    if method == 'POST':
        headers = {
            key[5:].replace('_', '-'): value
            for key, value in environ.items()
            if key.startswith('HTTP_')
        }

        signature = headers.get('X-SIGNATURE-ED25519')
        timestamp = headers.get('X-SIGNATURE-TIMESTAMP')

        if not signature or not timestamp:
            start_response('401 Unauthorized', [('Content-Type', 'text/plain')])
            return [b'Missing signature headers']

        content_length = int(environ.get('CONTENT_LENGTH', 0))
        body = environ['wsgi.input'].read(content_length).decode('utf-8')

        if not verify_discord_signature(signature, timestamp, body):
            start_response('401 Unauthorized', [('Content-Type', 'text/plain')])
            return [b'Invalid signature']

        interaction = json.loads(body)

        if interaction['type'] == 1:
            response = json.dumps({'type': 1})
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response.encode('utf-8')]

        if interaction['type'] == 2:
            if interaction['data']['name'] == 'mapstatus':
                message = format_map_status()
                response = json.dumps({
                    'type': 4,
                    'data': {
                        'content': message
                    }
                })
                start_response('200 OK', [('Content-Type', 'application/json')])
                return [response.encode('utf-8')]

        start_response('400 Bad Request', [('Content-Type', 'application/json')])
        return [json.dumps({'error': 'Unknown interaction type'}).encode('utf-8')]

    start_response('405 Method Not Allowed', [('Content-Type', 'text/plain')])
    return [b'Method not allowed']
