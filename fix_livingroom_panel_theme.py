import json
import asyncio
import re
import websockets

TOKEN_PATH = '/Users/rpotc/Documents/DMS/flower-care/home_assistant_token.txt'
BACKUP_PATH = '/Users/rpotc/Documents/DMS/livingroom_panel_backup_before_theme_fix.json'
SAVED_PATH = '/Users/rpotc/Documents/DMS/livingroom_panel_theme_fixed.json'

with open(TOKEN_PATH) as f:
    token = f.read().strip()

async def run_fix():
    async with websockets.connect('ws://192.168.0.100:8123/api/websocket', max_size=10*1024*1024) as ws:
        # Auth handshake
        await ws.recv()
        await ws.send(json.dumps({'type': 'auth', 'access_token': token}))
        auth_res = json.loads(await ws.recv())
        if auth_res.get('type') != 'auth_ok':
            raise RuntimeError(f"Authentication failed: {auth_res}")

        # Fetch current lovelace config
        await ws.send(json.dumps({'id': 1, 'type': 'lovelace/config', 'url_path': 'livingroom-panel'}))
        res = json.loads(await ws.recv())
        if not res.get('success'):
            raise RuntimeError(f"Failed to fetch config: {res}")
        cfg = res['result']

        # Save backup
        with open(BACKUP_PATH, 'w') as bf:
            json.dump(cfg, bf, indent=2)
        print(f"Current configuration backed up to {BACKUP_PATH}")

        card0 = cfg['views'][0]['cards'][0]['cards'][0]
        
        # 1. Update SubCard 0 styles.card
        new_card_styles = [
            {'background': 'var(--ha-card-background, var(--card-background-color, #ffffff))'},
            {'color': 'var(--primary-text-color)'},
            {'backdrop-filter': 'blur(12px)'},
            {'-webkit-backdrop-filter': 'blur(12px)'},
            {'border-radius': 'var(--ha-card-border-radius, 12px)'},
            {'border': 'var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, rgba(127, 127, 127, 0.2)))'},
            {'padding': '14px 16px 12px 16px'},
            {'box-shadow': 'var(--ha-card-box-shadow, none)'}
        ]
        card0['styles']['card'] = new_card_styles

        # 2. Update SubCard 0 triggers_update
        triggers = set(card0.get('triggers_update', []))
        triggers.discard('input_boolean.living_room_air_quality_alert')
        triggers.add('input_boolean.kitchen_air_quality_alert')
        card0['triggers_update'] = sorted(list(triggers))

        # 3. Update SubCard 0 custom_fields.content
        content_js = card0['custom_fields']['content']

        # Greeting colors
        content_js = content_js.replace(
            'color: var(--primary-text-color, #ffffff);',
            'color: var(--primary-text-color);'
        )
        content_js = content_js.replace(
            'color: var(--secondary-text-color, #94a3b8);',
            'color: var(--secondary-text-color);'
        )

        # Weather widget container and text
        old_weather = 'background: rgba(255, 255, 255, 0.06); padding: 5px 12px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.08);'
        new_weather = 'background: var(--secondary-background-color, rgba(127, 127, 127, 0.08)); padding: 5px 12px; border-radius: 10px; border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.15));'
        content_js = content_js.replace(old_weather, new_weather)

        content_js = content_js.replace(
            '<div style="font-size: 0.95rem; font-weight: 700; color: #ffffff;">${wTemp}°C</div>',
            '<div style="font-size: 0.95rem; font-weight: 700; color: var(--primary-text-color);">${wTemp}°C</div>'
        )
        content_js = content_js.replace(
            '<div style="font-size: 0.72rem; color: #94a3b8; text-transform: capitalize;">${wCond}</div>',
            '<div style="font-size: 0.72rem; color: var(--secondary-text-color); text-transform: capitalize;">${wCond}</div>'
        )

        # News ticker chyron container and text
        old_ticker = 'background: rgba(15, 23, 42, 0.65);'
        new_ticker = 'background: var(--secondary-background-color, rgba(127, 127, 127, 0.08));'
        content_js = content_js.replace(old_ticker, new_ticker)

        content_js = content_js.replace(
            '<span class="ticker-text" style="color: #f1f5f9; font-size: 0.86rem; font-weight: 500;">',
            '<span class="ticker-text" style="color: var(--primary-text-color); font-size: 0.86rem; font-weight: 500;">'
        )

        # Ensure air quality alert text specifies Kitchen
        content_js = content_js.replace(
            "active.push('⚠️ [AIR QUALITY] Living Room: ' + detail);",
            "active.push('⚠️ [AIR QUALITY] Kitchen: ' + detail);"
        )

        card0['custom_fields']['content'] = content_js

        # 4. Update SubCard 2 (Conditional Air Quality Card)
        card2 = cfg['views'][0]['cards'][0]['cards'][2]
        if card2.get('type') == 'conditional':
            for cond in card2.get('conditions', []):
                if cond.get('entity') == 'input_boolean.living_room_air_quality_alert':
                    cond['entity'] = 'input_boolean.kitchen_air_quality_alert'
            if 'card' in card2:
                sec = card2['card'].get('secondary', '')
                if 'Living Room CO₂' in sec:
                    card2['card']['secondary'] = sec.replace('Living Room CO₂', 'Kitchen CO₂')

        # Save locally for reference
        with open(SAVED_PATH, 'w') as out:
            json.dump(cfg, out, indent=2)

        # Inspect hex and rgba in card0 to verify complete cleanup
        card0_str = json.dumps(card0)
        hex_colors = set(re.findall(r'#[0-9a-fA-F]{3,8}', card0_str))
        rgba_colors = set(re.findall(r'rgba\([^)]+\)', card0_str))
        print(f"Verified card0 hex colors: {hex_colors}")
        print(f"Verified card0 rgba colors: {rgba_colors}")

        # Push to Home Assistant Lovelace
        await ws.send(json.dumps({
            'id': 2,
            'type': 'lovelace/config/save',
            'url_path': 'livingroom-panel',
            'config': cfg
        }))
        save_res = json.loads(await ws.recv())
        if not save_res.get('success'):
            raise RuntimeError(f"Failed to save Lovelace config: {save_res}")
        print("Successfully saved updated dashboard configuration to Home Assistant!")

if __name__ == '__main__':
    asyncio.run(run_fix())
