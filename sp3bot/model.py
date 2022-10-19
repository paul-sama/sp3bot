import json
import logging
from datetime import timedelta, datetime as dt
try:
    from lib_paul import get_mysql_data
except ImportError:
    def get_mysql_data(db, sql):
        return None


def show_schedule(full=False):
    sql = "SELECT * FROM `schedule` ORDER BY `start_time` DESC LIMIT 1"
    r = get_mysql_data('splatoon3', sql)
    if not r:
        return 'No schedule found!'

    res = json.loads(r[0]['raw_data'])
    nodes = res['data']['bankaraSchedules']['nodes']
    if not full:
        nodes = nodes[:3]
    s_list = []
    for n in nodes:
        s_list.append({
            'start_time': n['startTime'],
            'end_time': n['endTime'],
            'challenge': {
                'mode': n['bankaraMatchSettings'][0]['mode'],
                'rule': n['bankaraMatchSettings'][0]['vsRule']['name'],
                'stage': [n['bankaraMatchSettings'][0]['vsStages'][0]['name'],
                          n['bankaraMatchSettings'][0]['vsStages'][1]['name']],
            },
            'open': {
                'mode': n['bankaraMatchSettings'][1]['mode'],
                'rule': n['bankaraMatchSettings'][1]['vsRule']['name'],
                'stage': [n['bankaraMatchSettings'][1]['vsStages'][0]['name'],
                            n['bankaraMatchSettings'][1]['vsStages'][1]['name']]
            }
        })
    text = ''
    for s in s_list:
        date_start = dt.strptime(s['start_time'], '%Y-%m-%dT%H:%M:%S%z') + timedelta(hours=8)
        date_end = dt.strptime(s['end_time'], '%Y-%m-%dT%H:%M:%S%z') + timedelta(hours=8)
        # print(f"{date_start:%d.%H}-{date_end:%H} 挑战: {s['challenge']['rule'][2]}, 开放: {s['open']['rule'][2]}")
        text += f"{date_start:%d.%H}-{date_end:%H} 挑战: {s['challenge']['rule'][2]},  开放: {s['open']['rule'][2]}\n"
    return text


def show_coop():
    sql = "SELECT * FROM `schedule` ORDER BY `start_time` DESC LIMIT 1"
    r = get_mysql_data('splatoon3', sql)
    if not r:
        return 'No schedule found!'

    res = json.loads(r[0]['raw_data'])
    nodes = res['data']['coopGroupingSchedule']['regularSchedules']['nodes']

    text = ''
    c = 0
    for n in nodes:
        date_start = dt.strptime(n['startTime'], '%Y-%m-%dT%H:%M:%S%z') + timedelta(hours=8)
        date_end = dt.strptime(n['endTime'], '%Y-%m-%dT%H:%M:%S%z') + timedelta(hours=8)
        text += f"{date_start:%d.%H:%M} - {date_end:%d.%H:%M}, {n['setting']['coopStage']['name']}\n"
        if c < 2:
            text += '    ' + ", ".join([x['name'] for x in n['setting']['weapons']]) + "\n"
        c += 1
    return text


def show_mall():
    sql = "SELECT * FROM `mall` where type='limited' ORDER BY `id` DESC LIMIT 6"
    r = get_mysql_data('splatoon3', sql)
    if not r:
        return 'No schedule found!'

    dict_mall = {'ClothingGear': '衣', 'HeadGear': '帽', 'ShoesGear': '鞋'}

    text = ''
    for i in r[::-1]:
        i = json.loads(i['raw_data'])
        _type = dict_mall.get(i['gear']['__typename']) or '鞋'
        cnt = len(i['gear']['additionalGearPowers'])
        price = i['price']
        gear = i['gear']['primaryGearPower']['name']
        # print(f"{_type} {cnt}孔 {price:>5} {gear}")
        text += f"{_type} {cnt}孔 {price:>5} {gear}\n"

    sql = "SELECT * FROM `mall` where type='pickup' ORDER BY `id` DESC LIMIT 3"
    r = get_mysql_data('splatoon3', sql)
    if r:
        text += "\n每日精选:\n"
        for i in r[::-1]:
            i = json.loads(i['raw_data'])
            _type = dict_mall.get(i['gear']['__typename']) or '鞋'
            cnt = len(i['gear']['additionalGearPowers'])
            price = i['price']
            gear = i['gear']['primaryGearPower']['name']
            text += f"{_type} {cnt}孔 {price:>5} {gear}\n"
    return text
