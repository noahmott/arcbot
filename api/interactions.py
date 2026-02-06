import os
import time
import requests
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import json
from http.server import BaseHTTPRequestHandler

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
    """Format events into Discord embed"""
    events = get_events()

    if not events:
        return {
            'embeds': [{
                'title': 'Arc Raiders Map Events',
                'description': 'Unable to fetch event data. Please try again later.',
                'color': 0xFF0000
            }]
        }

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

    fields = []

    if active_events:
        end_time_seconds = active_events[0]['endTime'] // 1000

        active_group = [active_events[0]]
        for event in active_events[1:]:
            if event['endTime'] == active_events[0]['endTime']:
                active_group.append(event)

        active_text = '\n'.join([f"**{event['name']}** - {event['map']}" for event in active_group])
        fields.append({
            'name': f'ACTIVE NOW (ends <t:{end_time_seconds}:R>)',
            'value': active_text,
            'inline': False
        })

    if upcoming_events:
        start_time_seconds = upcoming_events[0]['startTime'] // 1000

        next_group = [upcoming_events[0]]
        for event in upcoming_events[1:]:
            if event['startTime'] == upcoming_events[0]['startTime']:
                next_group.append(event)

        upcoming_text = '\n'.join([f"**{event['name']}** - {event['map']}" for event in next_group])
        fields.append({
            'name': f'UP NEXT (starts <t:{start_time_seconds}:R>)',
            'value': upcoming_text,
            'inline': False
        })

    if not active_events and not upcoming_events:
        return {
            'embeds': [{
                'title': 'Arc Raiders Map Events',
                'description': 'No active or upcoming events found.',
                'color': 0x808080
            }]
        }

    thumbnail_url = active_events[0]['icon'] if active_events else (upcoming_events[0]['icon'] if upcoming_events else None)

    embed = {
        'title': 'Arc Raiders Map Events',
        'color': 0x00FF00 if active_events else 0xFFAA00,
        'fields': fields,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
    }

    if thumbnail_url:
        embed['thumbnail'] = {'url': thumbnail_url}

    return {'embeds': [embed]}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write('Discord bot is running'.encode('utf-8'))
        return

    def do_POST(self):
        signature = self.headers.get('X-Signature-Ed25519')
        timestamp = self.headers.get('X-Signature-Timestamp')

        if not signature or not timestamp:
            self.send_response(401)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write('Missing signature headers'.encode('utf-8'))
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        if not verify_discord_signature(signature, timestamp, body):
            self.send_response(401)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write('Invalid signature'.encode('utf-8'))
            return

        interaction = json.loads(body)

        if interaction['type'] == 1:
            response = json.dumps({'type': 1})
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
            return

        if interaction['type'] == 2:
            if interaction['data']['name'] == 'mapstatus':
                embed_data = format_map_status()
                response = json.dumps({
                    'type': 4,
                    'data': embed_data
                })
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(response.encode('utf-8'))
                return

        self.send_response(400)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': 'Unknown interaction type'}).encode('utf-8'))
        return
