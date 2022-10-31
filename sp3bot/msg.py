import json
import os
import sys
from datetime import datetime as dt, timedelta
from loguru import logger
pth = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(pth)
sys.path.append(f'{pth}/s3s')
import utils

INTERVAL = 10

DICT_RANK_POINT = {
    'C-': 0,
    'C': 20,
    'C+': 40,
    'B-': 55,
    'B': 70,
    'B+': 85,
    'A-': 100,
    'A': 110,
    'A+': 120,
    'S': -150,
    'S+': -160,
}


def get_row_text(p):
    re = p['result']
    if not re:
        re = {"kill": 0, "death": 99, "assist": 0, "special": 0}
    ak = re['kill']
    k = re['kill'] - re['assist']
    k_str = f'{k}+{re["assist"]}'
    d = re['death']
    ration = k / d if d else 99
    # name = p['name'].replace('`', '\\`') .replace("_", "\\_").replace("*", "\\*").replace("[", "\\[")
    name = p['name'].replace('`', '`\``')
    t = f"`{ak:>2}{k_str:>5}k {d:>2}d{ration:>4.1f}{re['special']:>3}sp {p['paint']:>4}p {name}`\n"
    # if p['isMyself']:
    #     t = '  ------------>  ' + t.strip()
    #     if ak > 9:
    #         t = t.replace('->', '>')
    return t


def get_battle_msg(b_info, battle_detail, **kwargs):
    mode = b_info['vsMode']['mode']
    rule = b_info['vsRule']['name']
    judgement = b_info['judgement']
    udemae = b_info['udemae']
    battle_detail = battle_detail['data']['vsHistoryDetail']
    bankara_match = ((battle_detail or {}).get('bankaraMatch') or {}).get('mode') or ''
    point = 0
    if bankara_match:
        bankara_match = f'({bankara_match})'
        if bankara_match == '(OPEN)':
            # open
            point = b_info['bankaraMatch']['earnedUdemaePoint']
            if point > 0:
                point = f'+{point}'
        else:
            # challenge
            try:
                splt = kwargs.get('splt')
                data = utils.gen_graphql_body(utils.translate_rid['BankaraBattleHistoriesQuery'])
                bankara_info = splt._request(data, skip_check_token=True)
                hg = bankara_info['data']['bankaraBattleHistories']['historyGroups']['nodes'][0]
                point = hg['bankaraMatchChallenge']['earnedUdemaePoint'] or 0
                bankara_detail = hg['bankaraMatchChallenge']
                if point > 0:
                    point = f'+{point}'
                if point == 0 and bankara_detail and (
                        len(hg['historyDetails']['nodes']) == 1 and
                        bankara_detail.get('maxWinCount') == 5 and
                        bankara_detail.get('winCount') + bankara_detail.get('loseCount') == 1):
                    # first battle, open ticket
                    point = DICT_RANK_POINT.get(udemae[:2], 0)
            except Exception as e:
                logger.exception(e)

    str_point = f'{point}p' if point else ''

    msg = f"`{mode}{bankara_match} {rule} {judgement} {udemae} {str_point}`\n"

    dict_a = {'GOLD': '🏅️', 'SILVER': '🥈', 'BRONZE': '🥉'}
    award_list = [f"{dict_a.get(a['rank'], '')}`{a['name']}`" for a in battle_detail['awards']]

    succ = 0
    if 'current_statics' in kwargs:
        current_statics = kwargs['current_statics']
        current_statics['TOTAL'] += 1
        current_statics[judgement] += 1
        current_statics['point'] += int(point)

        successive = current_statics['successive']
        if judgement == 'WIN':
            successive = max(successive, 0) + 1
        elif judgement not in ('DRAW', ):
            successive = min(successive, 0) - 1
        current_statics['successive'] = successive
        succ = current_statics['successive']

        logger.info(f"current_statics: {current_statics}")

    text_list = []

    teams = [battle_detail['myTeam']] + battle_detail['otherTeams']
    for team in sorted(teams, key=lambda x: x['order']):
        for p in team['players']:
            text_list.append(get_row_text(p))
        text_list.append('\n')

    msg += ''.join(text_list)

    msg += f"`duration: {battle_detail['duration']}s, knockout: {battle_detail['knockout']}`"

    if abs(succ) >= 3:
        if succ > 0:
            msg += f'`, {succ}连胜`'
        else:
            msg += f'`, {abs(succ)}连败`'

    msg += ('\n ' + '\n '.join(award_list) + '\n')
    # print(msg)
    return msg


def get_summary(data, all_data, coop):
    player = data['data']['currentPlayer']
    history = data['data']['playHistory']
    start_time = history['gameStartTime']
    s_time = dt.strptime(start_time, '%Y-%m-%dT%H:%M:%SZ') + timedelta(hours=8)

    all_cnt = ''
    if all_data:
        all_cnt = f"/{all_data['data']['playHistory']['battleNumTotal']}"

    coop_msg = ''
    if coop:
        coop = coop['data']['coopResult']
        card = coop['pointCard']
        p = coop['scale']
        name = f"{coop['regularGrade']['name']} {coop['regularGradePoint']}"
        coop_msg = f"""
{name}
现有点数: {card['regularPoint']}
打工次数: {card['playCount']}
已收集的金鲑鱼卵: {card['goldenDeliverCount']}
已收集的鲑鱼卵: {card['deliverCount']}
已击倒的头目鲑鱼: {card['defeatBossCount']}
救援次数: {card['rescueCount']}
累计点数: {card['totalPoint']}
鳞片: 🥉{p['bronze']} 🥈{p['silver']} 🏅️{p['gold']}
"""

    msg = f"""
```
{player['name']} #{player['nameId']}
{player['byname']}
最高技术: {history['udemaeMax']}
总胜利数: {history['winCountTotal']}{all_cnt}
至今为止的涂墨面积: {history['paintPointTotal']:,}p
徽章: {len(history['badges'])}
开始游玩时间: {s_time:%Y-%m-%d %H:%M:%S}
{coop_msg}
```
"""
    return msg


def coop_row(p):
    boss = f"x{p['defeatEnemyCount']}"
    name = p['player']['name'].replace('`', '`\``')
    return f"`{boss:>3} {p['goldenDeliverCount']:>2} {p['rescuedCount']}d " \
           f"{p['deliverCount']:>4} {p['rescueCount']}r {name}`"


def get_coop_msg(c_point, data):
    detail = data['data']['coopHistoryDetail']
    my = detail['myResult']
    wave_msg = ''
    d_w = {0: '∼', 1: '≈', 2: '≋'}
    for w in detail['waveResults'][:3]:
        event = (w.get('eventWave') or {}).get('name') or ''
        wave_msg += f"`W{w['waveNumber']} {w['teamDeliverCount']}/{w['deliverNorm']}({w['goldenPopCount']}) " \
                    f"{d_w[w['waterLevel']]} {event}`\n"
    if detail.get('bossResult'):
        w = detail['waveResults'][-1]
        r = 'GJ!' if detail['bossResult']['hasDefeatBoss'] else 'NG'
        s = ''
        scale = detail.get('scale')
        if scale and scale.get('bronze'):
            s += f'🥉{scale["bronze"]}'
        if scale and scale.get('silver'):
            s += f' 🥈{scale["silver"]}'
        if scale and scale.get('gold'):
            s += f' 🏅️{scale["gold"]}'
        wave_msg += f"`EX {detail['bossResult']['boss']['name']} ({w['goldenPopCount']}) {r} {s}`\n"
    msg = f"""
`{detail['afterGrade']['name']} {detail['afterGradePoint']} {detail['dangerRate']:.0%} +{detail['jobPoint']}({c_point}p)`
{wave_msg}
{coop_row(my)}
"""
    for p in detail['memberResults']:
        msg += f"""{coop_row(p)}\n"""
    # logger.info(msg)
    return msg


def get_statics(data):
    point = 0
    if data.get('point'):
        point = data['point']
    if 'point' in data:
        del data['point']
    if 'successive' in data:
        del data['successive']
    point = f'+{point}' if point > 0 else point
    point_str = f"Point: {point}p" if point else ''
    lst = sorted([(k, v) for k, v in data.items()], key=lambda x: x[1], reverse=True)
    msg = f"""
Statistics:
```
{', '.join([f'{k}: {v}' for k, v in lst])}
WIN_RATE: {data['WIN'] / data['TOTAL']:.2%}
{point_str}
```
"""
    return msg
