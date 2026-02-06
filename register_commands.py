import os
import requests

DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
DISCORD_APP_ID = os.environ.get('DISCORD_APP_ID')
DISCORD_GUILD_ID = os.environ.get('DISCORD_GUILD_ID')

if not all([DISCORD_BOT_TOKEN, DISCORD_APP_ID, DISCORD_GUILD_ID]):
    print('Error: Missing required environment variables')
    print('Required: DISCORD_BOT_TOKEN, DISCORD_APP_ID, DISCORD_GUILD_ID')
    exit(1)

url = f'https://discord.com/api/v10/applications/{DISCORD_APP_ID}/guilds/{DISCORD_GUILD_ID}/commands'

command = {
    'name': 'mapstatus',
    'description': 'Show current and upcoming Arc Raiders map events',
    'type': 1
}

headers = {
    'Authorization': f'Bot {DISCORD_BOT_TOKEN}',
    'Content-Type': 'application/json'
}

try:
    response = requests.put(url, json=[command], headers=headers)
    response.raise_for_status()

    print('Successfully registered /mapstatus command')
    print(f'Response: {response.json()}')
except requests.RequestException as e:
    print(f'Failed to register command: {e}')
    if hasattr(e, 'response') and e.response:
        print(f'Response body: {e.response.text}')
