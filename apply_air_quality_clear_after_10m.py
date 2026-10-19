import json
import urllib.request

with open('/Users/rpotc/Documents/DMS/flower-care/home_assistant_token.txt') as f:
    token = f.read().strip()

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# 1. Update air_quality_alert_living_room
aut_lr = {
    'id': 'air_quality_alert_living_room',
    'alias': 'AIR: Living Room Air Quality Alert & Management',
    'description': 'Monitors Living Room CO2, PM2.5, and formaldehyde. Sets alert when bad, clears alert after 10 minutes of clean air.',
    'mode': 'restart',
    'triggers': [
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.mt15_mt29_carbon_dioxide',
            'above': 1200,
            'for': {'minutes': 1},
            'id': 'co2_high'
        },
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.mt15_mt29_pm2_5',
            'above': 30,
            'for': {'minutes': 1},
            'id': 'pm25_high'
        },
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.mt15_mt29_formaldehyde',
            'above': 0.08,
            'for': {'minutes': 1},
            'id': 'hcho_high'
        },
        {
            'trigger': 'state',
            'entity_id': 'binary_sensor.livingroom_window_sensor_1',
            'to': 'off',
            'id': 'window_closed'
        },
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.mt15_mt29_carbon_dioxide',
            'below': 1000,
            'for': {'minutes': 10},
            'id': 'air_clean_co2'
        },
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.mt15_mt29_pm2_5',
            'below': 25,
            'for': {'minutes': 10},
            'id': 'air_clean_pm25'
        },
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.mt15_mt29_formaldehyde',
            'below': 0.07,
            'for': {'minutes': 10},
            'id': 'air_clean_hcho'
        }
    ],
    'actions': [
        {
            'choose': [
                {
                    'conditions': [
                        {
                            'condition': 'template',
                            'value_template': "{{ states('sensor.mt15_mt29_carbon_dioxide') | float(0) <= 1000 and states('sensor.mt15_mt29_pm2_5') | float(0) <= 25 and states('sensor.mt15_mt29_formaldehyde') | float(0) <= 0.07 and is_state('input_boolean.living_room_air_quality_alert', 'on') }}"
                        }
                    ],
                    'sequence': [
                        {
                            'action': 'input_boolean.turn_off',
                            'target': {'entity_id': 'input_boolean.living_room_air_quality_alert'}
                        },
                        {
                            'action': 'persistent_notification.dismiss',
                            'data': {'notification_id': 'living_room_air_alert'}
                        },
                        {
                            'action': 'input_text.set_value',
                            'target': {'entity_id': 'input_text.recent_alerts_24h'},
                            'data': {
                                'value': """{% set current = states('input_text.recent_alerts_24h') %}
{% if current not in ['unknown', 'unavailable', '', 'none'] %}
  {% set items = current.split('   •   ') %}
  {% set ns = namespace(rem=[]) %}
  {% for item in items %}
    {% if 'Living Room High' not in item and 'CO2' not in item and 'Formaldehyde' not in item and 'PM2.5' not in item %}
      {% set ns.rem = ns.rem + [item] %}
    {% endif %}
  {% endfor %}
  {{ ns.rem | join('   •   ') }}
{% else %}
  {{ '' }}
{% endif %}"""
                            }
                        }
                    ]
                },
                {
                    'conditions': [
                        {
                            'condition': 'template',
                            'value_template': "{{ states('sensor.mt15_mt29_carbon_dioxide') | float(0) > 1200 or states('sensor.mt15_mt29_pm2_5') | float(0) > 30 or states('sensor.mt15_mt29_formaldehyde') | float(0) > 0.08 }}"
                        }
                    ],
                    'sequence': [
                        {
                            'action': 'input_boolean.turn_on',
                            'target': {'entity_id': 'input_boolean.living_room_air_quality_alert'}
                        },
                        {
                            'variables': {
                                'co2': "{{ states('sensor.mt15_mt29_carbon_dioxide') | float(0) }}",
                                'pm25': "{{ states('sensor.mt15_mt29_pm2_5') | float(0) }}",
                                'hcho': "{{ states('sensor.mt15_mt29_formaldehyde') | float(0) }}",
                                'window_open_10m': "{{ is_state('binary_sensor.livingroom_window_sensor_1', 'on') and (now() - states.binary_sensor.livingroom_window_sensor_1.last_changed).total_seconds() >= 600 }}",
                                'alert_msg': """{% if pm25 > 30 %}
🚨 Living Room PM2.5 is high ({{ pm25 | round(0) }} µg/m³). {% if window_open_10m %}Window open > 10m; purifier turned off for efficiency.{% else %}Purifier should be running.{% endif %}
{% elif co2 > 1200 %}
⚠️ Living Room CO2 is high ({{ co2 | round(0) }} ppm). Please OPEN windows to ventilate with fresh air.
{% elif hcho > 0.08 %}
⚠️ Living Room Formaldehyde is elevated ({{ hcho }} mg/m³). Please ventilate with fresh air.
{% else %}
Air quality warning in Living Room.
{% endif %}"""
                            }
                        },
                        {
                            'choose': [
                                {
                                    'conditions': [
                                        {'condition': 'template', 'value_template': '{{ window_open_10m }}'}
                                    ],
                                    'sequence': [
                                        {
                                            'action': 'fan.turn_off',
                                            'target': {'entity_id': 'fan.zhimi_vb4_5851_air_purifier'}
                                        }
                                    ]
                                },
                                {
                                    'conditions': [
                                        {'condition': 'template', 'value_template': "{{ pm25 > 30 and not window_open_10m and states('fan.zhimi_vb4_5851_air_purifier') not in ['unavailable', 'unknown'] }}"}
                                    ],
                                    'sequence': [
                                        {
                                            'action': 'fan.turn_on',
                                            'target': {'entity_id': 'fan.zhimi_vb4_5851_air_purifier'},
                                            'data': {'preset_mode': 'Auto'}
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            'action': 'persistent_notification.create',
                            'data': {
                                'title': '🚨 Living Room Air Quality Alert',
                                'message': '{{ alert_msg }}',
                                'notification_id': 'living_room_air_alert'
                            }
                        },
                        {
                            'action': 'notify.send_message',
                            'target': {'entity_id': 'notify.s24'},
                            'data': {
                                'title': 'Living Room Air Quality Alert',
                                'message': '{{ alert_msg }}'
                            }
                        },
                        {
                            'action': 'input_text.set_value',
                            'target': {'entity_id': 'input_text.recent_alerts_24h'},
                            'data': {
                                'value': """{% set t = now().strftime("%H:%M") %}
{% if pm25 > 30 %}
  {% set entry = "🚨 [" ~ t ~ "] Living Room High PM2.5 (" ~ (pm25 | round(0)) ~ " µg/m³)" %}
{% elif co2 > 1200 %}
  {% set entry = "⚠️ [" ~ t ~ "] Living Room High CO2 (" ~ (co2 | round(0)) ~ " ppm)" %}
{% else %}
  {% set entry = "⚠️ [" ~ t ~ "] Living Room High Formaldehyde (" ~ hcho ~ " mg/m³)" %}
{% endif %}
{% set current = states('input_text.recent_alerts_24h') %}
{% if current in ['unknown', 'unavailable', '', 'none'] %}
  {{ entry }}
{% elif entry not in current %}
  {{ (entry ~ '   •   ' ~ current)[:250] }}
{% else %}
  {{ current }}
{% endif %}"""
                            }
                        }
                    ]
                }
            ]
        }
    ]
}

req = urllib.request.Request(
    'http://192.168.0.100:8123/api/config/automation/config/air_quality_alert_living_room',
    data=json.dumps(aut_lr).encode('utf-8'),
    headers=headers,
    method='POST'
)
with urllib.request.urlopen(req) as resp:
    print('Updated air_quality_alert_living_room:', resp.status)

# 2. Update air_quality_alert_bedroom
aut_bed = {
    'id': 'air_quality_alert_bedroom',
    'alias': 'AIR: Bedroom Air Quality Alert & Purifier Management',
    'description': 'Monitors Bedroom PM2.5 and CO2. Sets alert when bad, clears alert after 10 minutes of clean air.',
    'mode': 'restart',
    'triggers': [
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.mi_air_purifier_3_3h2_pm2_5',
            'above': 25,
            'for': {'minutes': 1},
            'id': 'pm25_high'
        },
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.smart_air_box_carbon_dioxide',
            'above': 1200,
            'for': {'minutes': 2},
            'id': 'co2_high'
        },
        {
            'trigger': 'state',
            'entity_id': 'binary_sensor.balcony_door',
            'to': 'off',
            'id': 'door_closed'
        },
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.mi_air_purifier_3_3h2_pm2_5',
            'below': 20,
            'for': {'minutes': 10},
            'id': 'air_clean_pm25'
        },
        {
            'trigger': 'numeric_state',
            'entity_id': 'sensor.smart_air_box_carbon_dioxide',
            'below': 1000,
            'for': {'minutes': 10},
            'id': 'air_clean_co2'
        }
    ],
    'actions': [
        {
            'choose': [
                {
                    'conditions': [
                        {
                            'condition': 'template',
                            'value_template': "{{ states('sensor.mi_air_purifier_3_3h2_pm2_5') | float(0) <= 20 and (states('sensor.smart_air_box_carbon_dioxide') in ['unavailable', 'unknown'] or states('sensor.smart_air_box_carbon_dioxide') | float(0) <= 1000) and is_state('input_boolean.bedroom_air_quality_alert', 'on') }}"
                        }
                    ],
                    'sequence': [
                        {
                            'action': 'input_boolean.turn_off',
                            'target': {'entity_id': 'input_boolean.bedroom_air_quality_alert'}
                        },
                        {
                            'action': 'persistent_notification.dismiss',
                            'data': {'notification_id': 'bedroom_air_alert'}
                        },
                        {
                            'action': 'input_text.set_value',
                            'target': {'entity_id': 'input_text.recent_alerts_24h'},
                            'data': {
                                'value': """{% set current = states('input_text.recent_alerts_24h') %}
{% if current not in ['unknown', 'unavailable', '', 'none'] %}
  {% set items = current.split('   •   ') %}
  {% set ns = namespace(rem=[]) %}
  {% for item in items %}
    {% if 'Bedroom High' not in item and 'Bedroom PM2.5' not in item %}
      {% set ns.rem = ns.rem + [item] %}
    {% endif %}
  {% endfor %}
  {{ ns.rem | join('   •   ') }}
{% else %}
  {{ '' }}
{% endif %}"""
                            }
                        }
                    ]
                },
                {
                    'conditions': [
                        {
                            'condition': 'template',
                            'value_template': "{{ states('sensor.mi_air_purifier_3_3h2_pm2_5') | float(0) > 25 or states('sensor.smart_air_box_carbon_dioxide') | float(0) > 1200 }}"
                        }
                    ],
                    'sequence': [
                        {
                            'action': 'input_boolean.turn_on',
                            'target': {'entity_id': 'input_boolean.bedroom_air_quality_alert'}
                        },
                        {
                            'variables': {
                                'pm25': "{{ states('sensor.mi_air_purifier_3_3h2_pm2_5') | float(0) }}",
                                'co2': "{{ states('sensor.smart_air_box_carbon_dioxide') | float(0) }}",
                                'door_open_10m': "{{ is_state('binary_sensor.balcony_door', 'on') and (now() - states.binary_sensor.balcony_door.last_changed).total_seconds() >= 600 }}",
                                'alert_msg': """{% if pm25 > 25 %}
🚨 Bedroom PM2.5 is high ({{ pm25 | round(0) }} µg/m³). {% if door_open_10m %}Balcony door open > 10m; purifier turned off for efficiency.{% else %}Purifier turned on to Auto mode.{% endif %}
{% elif co2 > 1200 %}
⚠️ Bedroom CO2 is high ({{ co2 | round(0) }} ppm). Please OPEN windows to ventilate with fresh air.
{% else %}
Air quality warning in Bedroom.
{% endif %}"""
                            }
                        },
                        {
                            'choose': [
                                {
                                    'conditions': [
                                        {'condition': 'template', 'value_template': '{{ door_open_10m }}'}
                                    ],
                                    'sequence': [
                                        {
                                            'action': 'fan.turn_off',
                                            'target': {'entity_id': 'fan.mi_air_purifier_3_3h2'}
                                        }
                                    ]
                                },
                                {
                                    'conditions': [
                                        {'condition': 'template', 'value_template': '{{ pm25 > 25 and not door_open_10m }}'}
                                    ],
                                    'sequence': [
                                        {
                                            'action': 'fan.turn_on',
                                            'target': {'entity_id': 'fan.mi_air_purifier_3_3h2'},
                                            'data': {'preset_mode': 'Auto'}
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            'action': 'persistent_notification.create',
                            'data': {
                                'title': '🚨 Bedroom Air Quality Alert',
                                'message': '{{ alert_msg }}',
                                'notification_id': 'bedroom_air_alert'
                            }
                        },
                        {
                            'action': 'notify.send_message',
                            'target': {'entity_id': 'notify.s24'},
                            'data': {
                                'title': 'Bedroom Air Quality Alert',
                                'message': '{{ alert_msg }}'
                            }
                        }
                    ]
                }
            ]
        }
    ]
}

req = urllib.request.Request(
    'http://192.168.0.100:8123/api/config/automation/config/air_quality_alert_bedroom',
    data=json.dumps(aut_bed).encode('utf-8'),
    headers=headers,
    method='POST'
)
with urllib.request.urlopen(req) as resp:
    print('Updated air_quality_alert_bedroom:', resp.status)

# 3. Clean current input_text.recent_alerts_24h right now since air quality is currently safe
clean_req = urllib.request.Request(
    'http://192.168.0.100:8123/api/services/input_text/set_value',
    data=json.dumps({'entity_id': 'input_text.recent_alerts_24h', 'value': ''}).encode('utf-8'),
    headers=headers,
    method='POST'
)
with urllib.request.urlopen(clean_req) as resp:
    print('Cleaned input_text.recent_alerts_24h:', resp.status)

# 4. Dismiss stale persistent notification
dismiss_req = urllib.request.Request(
    'http://192.168.0.100:8123/api/services/persistent_notification/dismiss',
    data=json.dumps({'notification_id': 'living_room_air_alert'}).encode('utf-8'),
    headers=headers,
    method='POST'
)
with urllib.request.urlopen(dismiss_req) as resp:
    print('Dismissed living_room_air_alert notification:', resp.status)
