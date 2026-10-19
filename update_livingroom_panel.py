import json
import asyncio
import websockets

with open('/Users/rpotc/Documents/DMS/livingroom_panel_fresh.json') as f:
    cfg = json.load(f)

card0 = cfg['views'][0]['cards'][0]
subcards = card0['cards']

# 1. Update SubCard 0 (Header button-card)
sc0 = subcards[0]
sc0_triggers = set(sc0.get('triggers_update', []))
extra_triggers = [
    'sensor.mt15_mt29_carbon_dioxide',
    'sensor.mt15_mt29_pm2_5',
    'sensor.mt15_mt29_formaldehyde',
    'sensor.mt15_mt29_temperature',
    'sensor.mi_air_purifier_3_3h2_pm2_5',
    'sensor.cpu_temperature',
    'binary_sensor.shellypro4pm_doorbell_overheating',
    'binary_sensor.shellypro4pm_lights_overheating',
    'binary_sensor.shellypro4pm_outlets_overheating',
    'binary_sensor.shellyplugsg3_8cbfea943910_overheating',
    'binary_sensor.shellyplugsg3_b08184a5b7e8_overheating',
    'binary_sensor.tv_shellyplugsg_overheating'
]
for et in extra_triggers:
    sc0_triggers.add(et)
sc0['triggers_update'] = list(sc0_triggers)

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

  // Air Quality Alerts
  let lrCo2 = parseFloat(states['sensor.mt15_mt29_carbon_dioxide']?.state);
  if (!isNaN(lrCo2) && lrCo2 > 1000) {
    if (lrCo2 > 1300) {
      active.push('🚨 [AIR QUALITY] High CO₂ in Living Room (' + Math.round(lrCo2) + ' ppm) — Open Windows!');
    } else {
      active.push('⚠️ [AIR QUALITY] Elevated CO₂ in Living Room (' + Math.round(lrCo2) + ' ppm)');
    }
  }

  let lrPm25 = parseFloat(states['sensor.mt15_mt29_pm2_5']?.state);
  if (!isNaN(lrPm25) && lrPm25 > 25) {
    active.push('🚨 [AIR QUALITY] High PM2.5 in Living Room (' + Math.round(lrPm25) + ' µg/m³)');
  }

  let lrHcho = parseFloat(states['sensor.mt15_mt29_formaldehyde']?.state);
  if (!isNaN(lrHcho) && lrHcho > 0.08) {
    active.push('⚠️ [AIR QUALITY] High Formaldehyde in Living Room (' + lrHcho.toFixed(2) + ' mg/m³)');
  }

  let bedPm25 = parseFloat(states['sensor.mi_air_purifier_3_3h2_pm2_5']?.state);
  if (!isNaN(bedPm25) && bedPm25 > 25) {
    active.push('🚨 [AIR QUALITY] High PM2.5 in Bedroom (' + Math.round(bedPm25) + ' µg/m³)');
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
      <!-- Top Row: Greeting on left, Weather widget on right -->
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

      <!-- Bottom Row: News Ticker Chyron -->
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

# 2. Update SubCard 1 (Chips card) - add Air Quality chip
sc1 = subcards[1]
chips_list = sc1.get('chips', [])
if not any(c.get('entity') == 'sensor.mt15_mt29_carbon_dioxide' for c in chips_list):
    aq_chip = {
        'type': 'template',
        'entity': 'sensor.mt15_mt29_carbon_dioxide',
        'icon': 'mdi:molecule-co2',
        'icon_color': "{{ 'red' if states('sensor.mt15_mt29_carbon_dioxide') | float(0) > 1200 else 'orange' if states('sensor.mt15_mt29_carbon_dioxide') | float(0) > 1000 else 'green' }}",
        'content': "{{ states('sensor.mt15_mt29_carbon_dioxide') | round(0) }} ppm",
        'tap_action': {
            'action': 'more-info'
        }
    }
    chips_list.insert(2, aq_chip)

# 3. Create new conditional alert cards for air quality, climate, and safety
new_alert_cards = [
    {
        'type': 'conditional',
        'conditions': [
            {
                'condition': 'numeric_state',
                'entity': 'sensor.mt15_mt29_carbon_dioxide',
                'above': 1200
            }
        ],
        'card': {
            'type': 'custom:mushroom-template-card',
            'primary': "⚠️ AIR QUALITY: High CO₂ ({{ states('sensor.mt15_mt29_carbon_dioxide') | round(0) }} ppm)",
            'secondary': 'Living Room CO₂ is high. Please OPEN windows to ventilate with fresh air.',
            'icon': 'mdi:molecule-co2',
            'icon_color': 'deep-orange',
            'layout': 'horizontal',
            'tap_action': {
                'action': 'more-info'
            },
            'entity': 'sensor.mt15_mt29_carbon_dioxide'
        }
    },
    {
        'type': 'conditional',
        'conditions': [
            {
                'condition': 'numeric_state',
                'entity': 'sensor.mt15_mt29_pm2_5',
                'above': 30
            }
        ],
        'card': {
            'type': 'custom:mushroom-template-card',
            'primary': "🚨 AIR QUALITY: High PM2.5 ({{ states('sensor.mt15_mt29_pm2_5') | round(0) }} µg/m³)",
            'secondary': "Living Room PM2.5 is high. {% if is_state('binary_sensor.livingroom_window_sensor_1', 'on') %}Window is open — purifier kept off for efficiency.{% else %}Window is closed — turn on air purifier.{% endif %}",
            'icon': 'mdi:air-filter',
            'icon_color': 'red',
            'layout': 'horizontal',
            'tap_action': {
                'action': 'more-info'
            },
            'entity': 'sensor.mt15_mt29_pm2_5'
        }
    },
    {
        'type': 'conditional',
        'conditions': [
            {
                'condition': 'numeric_state',
                'entity': 'sensor.mt15_mt29_formaldehyde',
                'above': 0.08
            }
        ],
        'card': {
            'type': 'custom:mushroom-template-card',
            'primary': "⚠️ AIR QUALITY: Elevated Formaldehyde ({{ states('sensor.mt15_mt29_formaldehyde') }} mg/m³)",
            'secondary': 'Formaldehyde exceeds recommended limit (0.08 mg/m³). Ventilate with fresh air.',
            'icon': 'mdi:chemical-weapon',
            'icon_color': 'amber',
            'layout': 'horizontal',
            'tap_action': {
                'action': 'more-info'
            },
            'entity': 'sensor.mt15_mt29_formaldehyde'
        }
    },
    {
        'type': 'conditional',
        'conditions': [
            {
                'condition': 'numeric_state',
                'entity': 'sensor.mi_air_purifier_3_3h2_pm2_5',
                'above': 30
            }
        ],
        'card': {
            'type': 'custom:mushroom-template-card',
            'primary': "🚨 AIR QUALITY: Bedroom High PM2.5 ({{ states('sensor.mi_air_purifier_3_3h2_pm2_5') | round(0) }} µg/m³)",
            'secondary': 'Bedroom air pollution is high.',
            'icon': 'mdi:air-filter',
            'icon_color': 'orange',
            'layout': 'horizontal',
            'tap_action': {
                'action': 'more-info'
            },
            'entity': 'sensor.mi_air_purifier_3_3h2_pm2_5'
        }
    },
    {
        'type': 'conditional',
        'conditions': [
            {
                'condition': 'numeric_state',
                'entity': 'sensor.everything_presence_livingroom_temperature',
                'above': 28
            }
        ],
        'card': {
            'type': 'custom:mushroom-template-card',
            'primary': '🌡️ CLIMATE ALERT: Living Room Overheating',
            'secondary': "Temperature is {{ states('sensor.everything_presence_livingroom_temperature') | round(1) }}°C. Check heating or cooling.",
            'icon': 'mdi:thermometer-alert',
            'icon_color': 'red',
            'layout': 'horizontal',
            'tap_action': {
                'action': 'more-info'
            },
            'entity': 'sensor.everything_presence_livingroom_temperature'
        }
    },
    {
        'type': 'conditional',
        'conditions': [
            {
                'condition': 'numeric_state',
                'entity': 'sensor.everything_presence_livingroom_temperature',
                'below': 18
            }
        ],
        'card': {
            'type': 'custom:mushroom-template-card',
            'primary': '❄️ CLIMATE ALERT: Living Room Cold',
            'secondary': "Temperature is {{ states('sensor.everything_presence_livingroom_temperature') | round(1) }}°C. Check heating.",
            'icon': 'mdi:snowflake-alert',
            'icon_color': 'blue',
            'layout': 'horizontal',
            'tap_action': {
                'action': 'more-info'
            },
            'entity': 'sensor.everything_presence_livingroom_temperature'
        }
    },
    {
        'type': 'conditional',
        'conditions': [
            {
                'condition': 'state',
                'entity': 'binary_sensor.shellypro4pm_outlets_overheating',
                'state': 'on'
            }
        ],
        'card': {
            'type': 'custom:mushroom-template-card',
            'primary': '🔥 ELECTRICAL DANGER: Shelly Outlets Overheating!',
            'secondary': 'Outlets circuit is overheating! Check immediately!',
            'icon': 'mdi:fire-alert',
            'icon_color': 'red',
            'layout': 'horizontal'
        }
    },
    {
        'type': 'conditional',
        'conditions': [
            {
                'condition': 'state',
                'entity': 'binary_sensor.shellypro4pm_lights_overheating',
                'state': 'on'
            }
        ],
        'card': {
            'type': 'custom:mushroom-template-card',
            'primary': '🔥 ELECTRICAL DANGER: Shelly Lights Overheating!',
            'secondary': 'Lights circuit is overheating! Check immediately!',
            'icon': 'mdi:fire-alert',
            'icon_color': 'red',
            'layout': 'horizontal'
        }
    },
    {
        'type': 'conditional',
        'conditions': [
            {
                'condition': 'state',
                'entity': 'binary_sensor.shellyplugsg3_8cbfea943910_overheating',
                'state': 'on'
            }
        ],
        'card': {
            'type': 'custom:mushroom-template-card',
            'primary': '🔥 ELECTRICAL DANGER: Fridge Plug Overheating!',
            'secondary': 'Fridge smart plug is overheating! Check immediately!',
            'icon': 'mdi:fire-alert',
            'icon_color': 'red',
            'layout': 'horizontal'
        }
    }
]

# Insert right after SubCard 1 (index 2)
for i, c in enumerate(new_alert_cards):
    subcards.insert(2 + i, c)

with open('/Users/rpotc/Documents/DMS/livingroom_panel_updated.json', 'w') as f:
    json.dump(cfg, f, indent=2)

print('Successfully generated livingroom_panel_updated.json')
