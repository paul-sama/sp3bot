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
    'C': -20,
    'C+': -40,
    'B-': -55,
    'B': -70,
    'B+': -85,
    'A-': -100,
    'A': -110,
    'A+': -120,
    'S': -150,
    'S+': -160,
}


MSG_HELP = """
/login - login
/me - show your info
/last - show the last battle or coop
/start_push - start push mode
/my_schedule - my schedule

settings:
/set_lang - set language, default(zh-CN) 默认中文
/set_api_key - set stat.ink api_key for post data
/show_db_info - show db info

/help - show this help message
"""


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


def get_point(**kwargs):
    try:
        point = 0
        b_process = ''
        bankara_match = kwargs.get('bankara_match')
        if not bankara_match:
            return point, ''

        b_info = kwargs['b_info']

        if bankara_match == 'OPEN':
            # open
            point = b_info['bankaraMatch']['earnedUdemaePoint']
            if point > 0:
                point = f'+{point}'
        else:
            # challenge
            splt = kwargs.get('splt')
            data = utils.gen_graphql_body(utils.translate_rid['BankaraBattleHistoriesQuery'])
            bankara_info = splt._request(data, skip_check_token=True)
            hg = bankara_info['data']['bankaraBattleHistories']['historyGroups']['nodes'][0]
            point = hg['bankaraMatchChallenge']['earnedUdemaePoint'] or 0
            bankara_detail = hg['bankaraMatchChallenge'] or {}
            if point > 0:
                point = f'+{point}'
            if point == 0 and bankara_detail and (
                    len(hg['historyDetails']['nodes']) == 1 and
                    bankara_detail.get('winCount') + bankara_detail.get('loseCount') == 1):
                # first battle, open ticket
                udemae = b_info.get('udemae') or ''
                point = DICT_RANK_POINT.get(udemae[:2], 0)

            b_process = f"{bankara_detail.get('winCount') or 0}-{bankara_detail.get('loseCount') or 0}"

    except Exception as e:
        logger.exception(e)
        point = 0
        b_process = ''

    return point, b_process


def set_statics(**kwargs):
    try:
        current_statics = kwargs['current_statics']
        judgement = kwargs['judgement']
        point = kwargs['point']
        battle_detail = kwargs['battle_detail']

        current_statics['TOTAL'] += 1
        current_statics[judgement] += 1
        current_statics['point'] += int(point)

        successive = current_statics['successive']
        if judgement == 'WIN':
            successive = max(successive, 0) + 1
        elif judgement not in ('DRAW',):
            successive = min(successive, 0) - 1
        current_statics['successive'] = successive

        for p in battle_detail['myTeam']['players']:
            if not p.get('isMyself'):
                continue
            if not p.get('result'):
                continue
            current_statics['KA'] += p['result']['kill']
            current_statics['K'] += p['result']['kill'] - p['result']['assist']
            current_statics['A'] += p['result']['assist']
            current_statics['D'] += p['result']['death']
            current_statics['S'] += p['result']['special']
            current_statics['P'] += p['paint']

        logger.debug(f"current_statics: {current_statics}")

    except Exception as e:
        logger.exception(e)


def get_battle_msg(b_info, battle_detail, **kwargs):
    mode = b_info['vsMode']['mode']
    judgement = b_info['judgement']
    battle_detail = battle_detail['data']['vsHistoryDetail'] or {}
    title, point, b_process = get_battle_msg_title(b_info, battle_detail, **kwargs)

    # title
    msg = title

    # body
    text_list = []
    teams = [battle_detail['myTeam']] + battle_detail['otherTeams']
    for team in sorted(teams, key=lambda x: x['order']):
        for p in team['players']:
            text_list.append(get_row_text(p))
        ti = ''
        if mode == 'FEST':
            ti = f"`{(team.get('result') or {}).get('paintRatio') or 0:.2%}  {team.get('festTeamName')}`"
        text_list.append(f'{ti}\n')
    msg += ''.join(text_list)

    # footer
    msg += f"`duration: {battle_detail['duration']}s, knockout: {battle_detail['knockout']} {b_process}`"

    succ = 0
    if 'current_statics' in kwargs:
        current_statics = kwargs['current_statics']
        set_statics(current_statics=current_statics, judgement=judgement, point=point, battle_detail=battle_detail)
        succ = current_statics['successive']
    if abs(succ) >= 3:
        if succ > 0:
            msg += f'`, {succ}连胜`'
        else:
            msg += f'`, {abs(succ)}连败`'

    dict_a = {'GOLD': '🏅️', 'SILVER': '🥈', 'BRONZE': '🥉'}
    award_list = [f"{dict_a.get(a['rank'], '')}`{a['name']}`" for a in battle_detail['awards']]
    msg += ('\n ' + '\n '.join(award_list) + '\n')
    if mode == 'FEST':
        fest_power = (battle_detail.get('festMatch') or {}).get('myFestPower')
        msg += f'\n`{b_info["player"]["festGrade"]}`'
        if fest_power:
            msg += f' ({fest_power:.2f})'
    # print(msg)
    return msg


def get_battle_msg_title(b_info, battle_detail, **kwargs):
    mode = b_info['vsMode']['mode']
    rule = b_info['vsRule']['name']
    judgement = b_info['judgement']
    bankara_match = (battle_detail.get('bankaraMatch') or {}).get('mode') or ''

    point, b_process = get_point(bankara_match=bankara_match, b_info=b_info, splt=kwargs.get('splt'))
    if bankara_match:
        bankara_match = f'({bankara_match})'
    str_point = f'{point}p' if point else ''

    if mode == 'FEST':
        mode_id = b_info['vsMode']['id']
        bankara_match = '(CHALLENGE)'
        if mode_id == 'VnNNb2RlLTY=':
            bankara_match = '(OPEN)'
        elif mode_id == 'VnNNb2RlLTg=':
            bankara_match = '(TRI_COLOR)'
        fest_match = battle_detail.get('festMatch') or {}
        contribution = fest_match.get('contribution')
        if contribution:
            str_point = f'+{contribution}'
        if fest_match.get('dragonMatchType') == 'DECUPLE':
            rule += ' (x10)'
        elif fest_match.get('dragonMatchType') == 'DRAGON':
            rule += ' (x100)'
        elif fest_match.get('dragonMatchType') == 'DOUBLE_DRAGON':
            rule += ' (x333)'

    # BANKARA(OPEN) 真格蛤蜊 WIN S+9 +8p
    # FEST(OPEN) 占地对战 WIN  +2051
    title = f"`{mode}{bankara_match} {rule} {judgement} {b_info.get('udemae') or ''} {str_point}`\n"
    return title, point, b_process


def get_dict_lang(lang):
    if lang == 'en-US':
        lang = 'en-GB'

    cur_path = os.path.dirname(os.path.abspath(__file__))
    i18n_path = f'{cur_path}/i18n/{lang}.json'
    if not os.path.exists(i18n_path):
        i18n_path = f'{cur_path}/i18n/zh-CN.json'
    with open(i18n_path, 'r', encoding='utf-8') as f:
        dict_lang = json.loads(f.read())
    return dict_lang


def get_summary(data, all_data, coop, lang='zh-CN'):
    dict_lang = get_dict_lang(lang)

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
{dict_lang['CoopHistory.regular_point']}: {card['regularPoint']}
{dict_lang['CoopHistory.play_count']}: {card['playCount']}
{dict_lang['CoopHistory.golden_deliver_count']}: {card['goldenDeliverCount']}
{dict_lang['CoopHistory.deliver_count']}: {card['deliverCount']}
{dict_lang['CoopHistory.defeat_boss_count']}: {card['defeatBossCount']}
{dict_lang['CoopHistory.rescue_count']}: {card['rescueCount']}
{dict_lang['CoopHistory.total_point']}: {card['totalPoint']}
{dict_lang['CoopHistory.scale']}: 🥉{p['bronze']} 🥈{p['silver']} 🏅️{p['gold']}
"""

    msg = f"""
```
{player['name']} #{player['nameId']}
{player['byname']}
{dict_lang['History.rank']}: {history['rank']}
{dict_lang['History.highest_udemae']}: {history['udemaeMax']}
{dict_lang['History.total_win']}: {history['winCountTotal']}{all_cnt}
{dict_lang['History.total_turf_point']}: {history['paintPointTotal']:,}p
{dict_lang['History.badge']}: {len(history['badges'])}
{s_time:%Y-%m-%d %H:%M:%S} +08:00
{coop_msg}
```
/weapon\_record
/stage\_record
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

    my_str = ''
    if data.get('KA'):
        k_rate = data.get('K', 0) / data['D'] if data.get('D') else 99
        my_str += f"{data.get('KA', 0)} {data.get('K', 0)}+{data.get('A', 0)}k {data.get('D', 0)}d " \
                  f"{k_rate:.2f} {data.get('S', 0)}sp {data.get('P', 0)}p"

    for k in ('point', 'successive', 'KA', 'K', 'A', 'D', 'S', 'P'):
        if k in data:
            del data[k]

    point = f'+{point}' if point > 0 else point
    point_str = f"Point: {point}p" if point else ''
    lst = sorted([(k, v) for k, v in data.items()], key=lambda x: x[1], reverse=True)
    msg = f"""
Statistics:
```
{', '.join([f'{k}: {v}' for k, v in lst])}
WIN_RATE: {data['WIN'] / data['TOTAL']:.2%}
{point_str}
{my_str}
```
"""
    return msg


def get_weapon_record(splt, lang='zh-CN'):
    dict_lang = get_dict_lang(lang)
    data = utils.gen_graphql_body('a0c277c719b758a926772879d8e53ef8')
    res = splt._request(data, skip_check_token=True)
    if not res:
        return '`Error`'
    weapons = res['data']['weaponRecords']['nodes']
    str_list = []
    for w in weapons:
        if not w.get('stats'):
            continue
        st = w['stats']
        str_s = '⭐'*st['level']
        str_next = ''
        if st.get('expToLevelUp'):
            str_next = f'({st["expToLevelUp"]})'
        str_weapon = f'''{w['name']} {str_s}{str_next}
{dict_lang['Record.win_count']}: {st['win']:<4} {dict_lang['Record.vibes']}: {st['vibes']:<5.1f} {dict_lang['Record.turf_point']}: {st['paint']:,}p\n
'''
        str_list.append(str_weapon)

    msg = f'''
```
{''.join(str_list)}
```
 '''
    return msg


def get_stage_record(splt):
    data = utils.gen_graphql_body('56c46bdbdfa4519eaf7845ce9f3cd67a')
    res = splt._request(data, skip_check_token=True)
    if not res:
        return '`Error`'
    stages = res['data']['stageRecords']['nodes']
    str_list = []
    for s in stages:
        str_stage = f'''{s['name']}
{s['stats']['winRateAr'] or 0:>7.2%} {s['stats']['winRateLf'] or 0:>7.2%} {s['stats']['winRateGl'] or 0:>7.2%} {s['stats']['winRateCl'] or 0:>7.2%}
'''
        str_list.append(str_stage)

    msg = f'''
```
{''.join(str_list)}
```
 '''
    return msg


def get_my_schedule(splt):
    data = utils.gen_graphql_body('7d4bb0565342b7385ceb97d109e14897')
    res = splt._request(data)
    if not res:
        return 'No schedule found!'

    data = utils.gen_graphql_body('56c46bdbdfa4519eaf7845ce9f3cd67a')
    stage_record = splt._request(data, skip_check_token=True)
    dict_stage = {}
    for s in stage_record['data']['stageRecords']['nodes']:
        if not s or not s.get('stats'):
            continue
        dict_stage[s['id']] = {
            'VnNSdWxlLTE=': s['stats']['winRateAr'],
            'VnNSdWxlLTI=': s['stats']['winRateLf'],
            'VnNSdWxlLTM=': s['stats']['winRateGl'],
            'VnNSdWxlLTQ=': s['stats']['winRateCl'],
        }

    text = ''
    for node in res['data']['bankaraSchedules']['nodes'][:4]:
        s = node['bankaraMatchSettings']
        c_rule_id = s[0]['vsRule']['id']
        c_stage_1, c_stage_2 = s[0]['vsStages']
        o_rule_id = s[1]['vsRule']['id']
        o_stage_1, o_stage_2 = s[1]['vsStages']
        row = f'''CHALLENGE: {s[0]['vsRule']['name']} ({dict_stage[c_stage_1['id']][c_rule_id] or 0:.2%}, {dict_stage[c_stage_2['id']][c_rule_id] or 0:.2%})
{c_stage_1['name']}, {c_stage_2['name']}
OPEN: {s[1]['vsRule']['name']} ({dict_stage[o_stage_1['id']][o_rule_id] or 0:.2%}, {dict_stage[o_stage_2['id']][o_rule_id] or 0:.2%})
{o_stage_1['name']}, {o_stage_2['name']}

'''
        text += row
    msg = f'```\n{text}```'
    return msg
