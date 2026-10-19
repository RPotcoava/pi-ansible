import json
import asyncio
import websockets

with open('/Users/rpotc/Documents/DMS/flower-care/home_assistant_token.txt') as f:
    token = f.read().strip()

async def update_panel():
    async with websockets.connect('ws://192.168.0.100:8123/api/websocket', max_size=10*1024*1024) as ws:
        await ws.recv()
        await ws.send(json.dumps({'type': 'auth', 'access_token': token}))
        await ws.recv()
        
        await ws.send(json.dumps({'id': 1, 'type': 'lovelace/config', 'url_path': 'livingroom-panel'}))
        res = json.loads(await ws.recv())
        cfg = res['result']

        card0 = cfg['views'][0]['cards'][0]
        subcards = card0['cards']

        # 1. Update SubCard 0 (Header card)
        sc0 = subcards[0]
        triggers = set(sc0.get('triggers_update', []))
        triggers.add('input_boolean.living_room_air_quality_alert')
        triggers.add('input_boolean.bedroom_air_quality_alert')
        triggers.add('input_text.recent_alerts_24h')
        triggers.add('sensor.mt15_mt29_carbon_dioxide')
        triggers.add('sensor.mt15_mt29_pm2_5')
        triggers.add('sensor.mt15_mt29_formaldehyde')
        sc0['triggers_update'] = list(triggers)

        new_content_js = """[[[
  let hr = new Date().getHours();
  let greeting = hr >= 6 && hr < 12 ? 'Good Morning' :
                 hr >= 12 && hr < 18 ? 'Good Afternoon' :
                 hr >= 18 && hr < 22 ? 'Good Evening' : 'Good Night';

  let rawTemp = states['sensor.everything_presence_livingroom_temperature']?.state;
  let rawHum = states['sensor.everything_presence_livingroom_humidity']?.state;
  let rawLux = states['sensor.everything_presence_livingroom_illuminance']?.state;

  let temp = rawTemp && !isNaN(rawTemp) ? (Math.round(parseFloat(rawTemp) * 10) / 10) + '°C' : '--°C';
  let hum = rawHum && !isNaN(rawHum) ? Math.round(parseFloat(rawHum)) + '%' : '--%';
  let lux = rawLux && !isNaN(rawLux) ? Math.round(parseFloat(rawLux)) : '--';

  // Weather widget data
  let wState = states['weather.acasa_2']?.state || 'partlycloudy';
  let wTemp = states['weather.acasa_2']?.attributes?.temperature || '--';
  let iconMap = {
    'sunny': '☀️',
    'clear-night': '🌙',
    'cloudy': '☁️',
    'partlycloudy': '⛅',
    'rainy': '🌧️',
    'pouring': '🌧️',
    'snowy': '❄️',
    'lightning': '⛈️',
    'lightning-rainy': '⛈️',
    'windy': '💨',
    'fog': '🌫️'
  };
  let wIcon = iconMap[wState] || '⛅';
  let wCond = wState.replace(/-/g, ' ');

  let active = [];

  // Safety & Hazard alerts
  if (states['binary_sensor.natgas_sensor_158d00035a8b85']?.state === 'on') {
    active.push('🔥 [DANGER] Kitchen Gas Leak Detected!');
  }
  if (states['binary_sensor.smoke_sensor_158d0002ad1027']?.state === 'on') {
    active.push('🔥 [DANGER] Kitchen Smoke Detected!');
  }
  if (states['binary_sensor.klippbok_water_leak_sensor_water_leak']?.state === 'on') {
    active.push('💧 [ACTIVE] Living Room Leak (KLIPPBOK)');
  }
  if (states['binary_sensor.ikea_of_sweden_badring_water_leakage_sensor_moisture']?.state === 'on') {
    active.push('💧 [ACTIVE] Water Leak (BADRING)');
  }

  // Electrical & Overheating
  let shellyOverheats = [
    ['binary_sensor.shellypro4pm_doorbell_overheating', 'Doorbell Shelly'],
    ['binary_sensor.shellypro4pm_lights_overheating', 'Lights Shelly'],
    ['binary_sensor.shellypro4pm_outlets_overheating', 'Outlets Shelly'],
    ['binary_sensor.shellyplugsg3_8cbfea943910_overheating', 'Fridge Plug'],
    ['binary_sensor.shellyplugsg3_b08184a5b7e8_overheating', 'Washers Plug'],
    ['binary_sensor.tv_shellyplugsg_overheating', 'TV Plug']
  ];
  for (let [eid, label] of shellyOverheats) {
    if (states[eid]?.state === 'on') {
      active.push('🔥 [ELECTRICAL] ' + label + ' Overheating!');
    }
  }

  let cpuTemp = parseFloat(states['sensor.cpu_temperature']?.state);
  if (!isNaN(cpuTemp) && cpuTemp > 75) {
    active.push('🔥 [HARDWARE] Server CPU Overheating (' + Math.round(cpuTemp) + '°C)');
  }

  // Air Quality Alerts - governed by 10-min cool-off input_booleans
  if (states['input_boolean.living_room_air_quality_alert']?.state === 'on') {
    let lrCo2 = parseFloat(states['sensor.mt15_mt29_carbon_dioxide']?.state);
    let lrPm25 = parseFloat(states['sensor.mt15_mt29_pm2_5']?.state);
    let lrHcho = parseFloat(states['sensor.mt15_mt29_formaldehyde']?.state);
    let reasons = [];
    if (!isNaN(lrCo2) && lrCo2 > 1000) reasons.push('CO₂ ' + Math.round(lrCo2) + ' ppm');
    if (!isNaN(lrPm25) && lrPm25 > 25) reasons.push('PM2.5 ' + Math.round(lrPm25) + ' µg/m³');
    if (!isNaN(lrHcho) && lrHcho > 0.08) reasons.push('HCHO ' + lrHcho.toFixed(2) + ' mg/m³');
    let detail = reasons.length > 0 ? reasons.join(', ') : 'Clearing (cooling off)...';
    active.push('⚠️ [AIR QUALITY] Living Room: ' + detail);
  }

  if (states['input_boolean.bedroom_air_quality_alert']?.state === 'on') {
    let bedPm25 = parseFloat(states['sensor.mi_air_purifier_3_3h2_pm2_5']?.state);
    active.push('🚨 [AIR QUALITY] Bedroom PM2.5 ' + (!isNaN(bedPm25) ? Math.round(bedPm25) + ' µg/m³' : 'Elevated'));
  }

  // Climate Extremes
  let lrTempNum = parseFloat(rawTemp);
  if (!isNaN(lrTempNum)) {
    if (lrTempNum > 28) {
      active.push('🌡️ [CLIMATE] Living Room Overheating (' + lrTempNum.toFixed(1) + '°C)');
    } else if (lrTempNum < 18) {
      active.push('❄️ [CLIMATE] Living Room Cold (' + lrTempNum.toFixed(1) + '°C)');
    }
  }

  let lrHumNum = parseFloat(rawHum);
  if (!isNaN(lrHumNum)) {
    if (lrHumNum > 70) {
      active.push('💧 [CLIMATE] High Humidity in Living Room (' + Math.round(lrHumNum) + '%)');
    } else if (lrHumNum < 25) {
      active.push('🌵 [CLIMATE] Very Low Humidity in Living Room (' + Math.round(lrHumNum) + '%)');
    }
  }

  // Robot Vacuum Alerts
  let se = states['sensor.saros_z70_vacuum_error']?.state;
  if (se && !['none', 'no_error', 'unknown', 'unavailable', ''].includes(se)) {
    active.push('🔴 [ACTIVE] Saros Z70: ' + se.replace(/_/g, ' '));
  }
  if (states['binary_sensor.saros_z70_water_shortage']?.state === 'on') {
    active.push('🔴 [ACTIVE] Saros Z70: Clean Water Empty');
  }
  if (states['binary_sensor.saros_z70_dock_clean_water_box']?.state === 'on') {
    active.push('🔴 [ACTIVE] Saros Z70: Clean Water Box Alert');
  }
  if (states['binary_sensor.saros_z70_dock_dirty_water_box']?.state === 'on') {
    active.push('🔴 [ACTIVE] Saros Z70: Dirty Water Box Alert');
  }
  let be = states['sensor.bedroom_roborock_vacuum_cleaner_operational_error']?.state;
  if (be && !['none', 'no_error', 'unknown', 'unavailable', ''].includes(be)) {
    active.push('🔴 [ACTIVE] Bedroom Vacuum: ' + be.replace(/_/g, ' '));
  }

  let past = states['input_text.recent_alerts_24h']?.state;
  let total = [...active];
  if (past && !['unknown', 'unavailable', 'none', ''].includes(past)) {
    total.push(past);
  }
  let hasAlerts = total.length > 0;
  let badgeBg = hasAlerts ? '#dc2626' : '#16a34a';
  let badgeText = hasAlerts ? 'ALERTS (24H)' : 'SYSTEM OK';
  let tickerBorder = hasAlerts ? '1px solid rgba(239, 68, 68, 0.5)' : '1px solid rgba(34, 197, 94, 0.3)';
  let displayText = hasAlerts
    ? total.join('   •   ')
    : '🟢 All systems nominal   •   No safety, climate, air quality, or device alerts';

  return `
    <div style="display: flex; flex-direction: column; width: 100%; font-family: var(--ha-card-font-family, inherit);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; width: 100%;">
        <div style="text-align: left;">
          <div style="font-size: 1.4rem; font-weight: 700; color: var(--primary-text-color, #ffffff); line-height: 1.2; letter-spacing: -0.01em;">
            ${greeting}, Razvan
          </div>
          <div style="font-size: 0.85rem; color: var(--secondary-text-color, #94a3b8); margin-top: 3px; font-weight: 500;">
            Temp: ${temp} &nbsp;|&nbsp; Humidity: ${hum} &nbsp;|&nbsp; Lux: ${lux}
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 8px; background: rgba(255, 255, 255, 0.06); padding: 5px 12px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.08); flex-shrink: 0;">
          <span style="font-size: 1.35rem; line-height: 1;">${wIcon}</span>
          <div style="text-align: right; line-height: 1.15;">
            <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff;">${wTemp}°C</div>
            <div style="font-size: 0.72rem; color: #94a3b8; text-transform: capitalize;">${wCond}</div>
          </div>
        </div>
      </div>

      <div style="display: flex; align-items: center; width: 100%; overflow: hidden; background: rgba(15, 23, 42, 0.65); border: ${tickerBorder}; border-radius: 8px; padding: 6px 10px; box-sizing: border-box;">
        <div style="background: ${badgeBg}; color: white; font-weight: 700; font-size: 0.72rem; padding: 3px 8px; border-radius: 5px; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 5px; white-space: nowrap; margin-right: 10px; flex-shrink: 0;">
          <span style="display: inline-block; width: 6px; height: 6px; background: white; border-radius: 50%;"></span>
          ${badgeText}
        </div>
        <div class="ticker-wrap" style="flex: 1; overflow: hidden; white-space: nowrap; position: relative;">
          <span class="ticker-text" style="color: #f1f5f9; font-size: 0.86rem; font-weight: 500;">
            ${displayText}
          </span>
        </div>
      </div>
    </div>
  `;
]]]"""
        sc0['custom_fields']['content'] = new_content_js

        # 2. Update Conditional Cards
        # Remove any previous raw air quality conditional cards
        cleaned_subcards = []
        for c in subcards:
            is_old_raw_aq = False
            if c.get('type') == 'conditional':
                for cond in c.get('conditions', []):
                    if cond.get('entity') in ['sensor.mt15_mt29_carbon_dioxide', 'sensor.mt15_mt29_pm2_5', 'sensor.mt15_mt29_formaldehyde', 'sensor.mi_air_purifier_3_3h2_pm2_5']:
                        is_old_raw_aq = True
            if not is_old_raw_aq:
                cleaned_subcards.append(c)

        # Build clean dynamic Living Room Air Quality Card governed by input_boolean (cleaned after 10m)
        lr_aq_card = {
            'type': 'conditional',
            'conditions': [
                {
                    'condition': 'state',
                    'entity': 'input_boolean.living_room_air_quality_alert',
                    'state': 'on'
                }
            ],
            'card': {
                'type': 'custom:mushroom-template-card',
                'primary': """{% set co2 = states('sensor.mt15_mt29_carbon_dioxide') | float(0) %}
{% set pm25 = states('sensor.mt15_mt29_pm2_5') | float(0) %}
{% set hcho = states('sensor.mt15_mt29_formaldehyde') | float(0) %}
{% if co2 > 1200 %}
  ⚠️ AIR QUALITY: High CO₂ ({{ co2 | round(0) }} ppm)
{% elif pm25 > 30 %}
  🚨 AIR QUALITY: High PM2.5 ({{ pm25 | round(0) }} µg/m³)
{% elif hcho > 0.08 %}
  ⚠️ AIR QUALITY: Elevated Formaldehyde ({{ hcho }} mg/m³)
{% else %}
  🌿 AIR QUALITY: Returning to Normal (Cool-off)
{% endif %}""",
                'secondary': """{% set co2 = states('sensor.mt15_mt29_carbon_dioxide') | float(0) %}
{% set pm25 = states('sensor.mt15_mt29_pm2_5') | float(0) %}
{% set hcho = states('sensor.mt15_mt29_formaldehyde') | float(0) %}
{% if co2 > 1200 %}
  Living Room CO₂ is elevated. Please OPEN windows to ventilate with fresh air.
{% elif pm25 > 30 %}
  Living Room PM2.5 is high. {% if is_state('binary_sensor.livingroom_window_sensor_1', 'on') %}Window is open — purifier kept off for efficiency.{% else %}Window is closed — air purifier running.{% endif %}
{% elif hcho > 0.08 %}
  Formaldehyde exceeds recommended threshold (0.08 mg/m³). Ventilate with fresh air.
{% else %}
  Air quality is now safe. Alert will automatically clear after 10 minutes of clean air.
{% endif %}""",
                'icon': """{% set co2 = states('sensor.mt15_mt29_carbon_dioxide') | float(0) %}
{% set pm25 = states('sensor.mt15_mt29_pm2_5') | float(0) %}
{% if co2 > 1200 %}
  mdi:molecule-co2
{% elif pm25 > 30 %}
  mdi:air-filter
{% else %}
  mdi:chemical-weapon
{% endif %}""",
                'icon_color': """{% set co2 = states('sensor.mt15_mt29_carbon_dioxide') | float(0) %}
{% set pm25 = states('sensor.mt15_mt29_pm2_5') | float(0) %}
{% set hcho = states('sensor.mt15_mt29_formaldehyde') | float(0) %}
{% if co2 > 1200 or pm25 > 30 %}
  red
{% elif hcho > 0.08 %}
  amber
{% else %}
  green
{% endif %}""",
                'layout': 'horizontal',
                'tap_action': {
                    'action': 'more-info'
                },
                'entity': 'sensor.mt15_mt29_carbon_dioxide'
            }
        }

        bed_aq_card = {
            'type': 'conditional',
            'conditions': [
                {
                    'condition': 'state',
                    'entity': 'input_boolean.bedroom_air_quality_alert',
                    'state': 'on'
                }
            ],
            'card': {
                'type': 'custom:mushroom-template-card',
                'primary': """{% set pm25 = states('sensor.mi_air_purifier_3_3h2_pm2_5') | float(0) %}
{% if pm25 > 25 %}
  🚨 AIR QUALITY: Bedroom High PM2.5 ({{ pm25 | round(0) }} µg/m³)
{% else %}
  🌿 AIR QUALITY: Bedroom Clean (Cool-off)
{% endif %}""",
                'secondary': """{% set pm25 = states('sensor.mi_air_purifier_3_3h2_pm2_5') | float(0) %}
{% if pm25 > 25 %}
  Bedroom particulate pollution is elevated. Purifier running.
{% else %}
  Bedroom air quality is safe. Alert will automatically clear after 10 minutes.
{% endif %}""",
                'icon': 'mdi:air-filter',
                'icon_color': "{{ 'red' if states('sensor.mi_air_purifier_3_3h2_pm2_5') | float(0) > 25 else 'green' }}",
                'layout': 'horizontal',
                'tap_action': {
                    'action': 'more-info'
                },
                'entity': 'sensor.mi_air_purifier_3_3h2_pm2_5'
            }
        }

        # Insert at index 2 (right after chips card)
        cleaned_subcards.insert(2, lr_aq_card)
        cleaned_subcards.insert(3, bed_aq_card)

        card0['cards'] = cleaned_subcards

        # Save to HA
        await ws.send(json.dumps({'id': 2, 'type': 'lovelace/config/save', 'url_path': 'livingroom-panel', 'config': cfg}))
        save_res = json.loads(await ws.recv())
        print('Panel update success:', save_res.get('success'), save_res.get('error'))

asyncio.run(update_panel())
