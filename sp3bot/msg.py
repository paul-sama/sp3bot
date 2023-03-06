import json
import os
import sys
from datetime import datetime as dt, timedelta
from collections import defaultdict
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
    'A-': -110,
    'A': -120,
    'A+': -130,
    'S': -170,
    'S+': -180,
}


MSG_HELP = """
/login - login
/me - show your info
/friends - show online friends
/last - show the last battle or coop
/start_push - start push mode
/my_schedule - my schedule
/coop_schedule - Coop Schedule
/x_top - show X Top Players

settings:
/set_lang - set language, default(zh-CN) 默认中文
/set_api_key - set stat.ink api_key for post data
/set_battle_info - set battle info
/get_seed - https://leanny.github.io/splat3seedchecker/#/settings
/show_db_info - show db info

/help - show this help message
"""


def get_row_text(p, battle_show_type='1'):
    re = p['result']
    if not re:
        re = {"kill": 0, "death": 99, "assist": 0, "special": 0}
    ak = re['kill']
    k = re['kill'] - re['assist']
    k_str = f'{k}+{re["assist"]}'
    d = re['death']
    ration = k / d if d else 99
    # name = p['name'].replace('`', '\\`') .replace("_", "\\_").replace("*", "\\*").replace("[", "\\[")
    name = p['name']
    weapon = (p.get('weapon') or {}).get('name') or ''
    if battle_show_type == '2':
        name = weapon
    elif battle_show_type == '3':
        name = f"{name} ({weapon})"
    elif battle_show_type == '4':
        name = f"{weapon} ({name})"
    name = name.replace('`', '`\``')
    t = f"`{ak:>2}{k_str:>5}k {d:>2}d{ration:>4.1f}{re['special']:>3}sp {p['paint']:>4}p {name}`\n"
    if p.get('isMyself'):
        t = t.strip().replace('`', '').replace(name, '')
        t = f"`{t}`*{name}*\n"
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


def get_x_power(**kwargs):
    try:
        power = ''
        x_process = ''
        battle_detail = kwargs.get('battle_detail')
        splt = kwargs.get('splt')
        b_info = kwargs['b_info']

        data = utils.gen_graphql_body(utils.translate_rid['XBattleHistoriesQuery'])
        res = splt._request(data, skip_check_token=True)
        hg = res['data']['xBattleHistories']['historyGroups']['nodes'][0]
        x_info = hg['xMatchMeasurement']
        if x_info['state'] == 'COMPLETED':
            last_x_power = battle_detail['xMatch'].get('lastXPower') or 0
            cur_x_power = x_info.get('xPowerAfter') or 0
            xp = cur_x_power - last_x_power
            power = f'{xp:.2f} ({cur_x_power:.2f})'
            if xp > 0:
                power = f'+{power} ({cur_x_power:.2f})'
        x_process = f"{x_info.get('winCount') or 0}-{x_info.get('loseCount') or 0}"

    except Exception as e:
        logger.exception(e)
        power = ''
        x_process = ''

    return power, x_process


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
            text_list.append(get_row_text(p, kwargs.get('battle_show_type')))
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
            current_statics = {}
            if 'current_statics' in kwargs:
                current_statics = kwargs['current_statics']
            last_power = current_statics.get('fest_power') or 0
            current_statics['fest_power'] = fest_power
            if last_power:
                diff = fest_power - last_power
                if diff >= 0:
                    msg += f' `+{diff:.2f}`'
                else:
                    msg += f' `{diff:.2f}`'
            msg += f'`({fest_power:.2f})`'
    # print(msg)
    return msg


def get_battle_msg_title(b_info, battle_detail, **kwargs):
    mode = b_info['vsMode']['mode']
    rule = b_info['vsRule']['name']
    judgement = b_info['judgement']
    bankara_match = (battle_detail.get('bankaraMatch') or {}).get('mode') or ''

    point = 0
    b_process = ''
    if bankara_match:
        point, b_process = get_point(bankara_match=bankara_match, b_info=b_info, splt=kwargs.get('splt'))
    elif battle_detail.get('xMatch'):
        point, b_process = get_x_power(battle_detail=battle_detail, b_info=b_info, splt=kwargs.get('splt'))

    str_point = ''
    if bankara_match:
        bankara_match = f'({bankara_match})'
        if point:
            str_point = f'{point}p'
    elif battle_detail.get('xMatch'):
        str_point = point
        point = 0

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
    r = ''
    if all_data:
        total_cnt = all_data['data']['playHistory']['battleNumTotal']
        all_cnt = f"/{total_cnt}"
        if total_cnt:
            r = f"{history['winCountTotal'] / total_cnt:.2%}"

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

    ar = (history.get('xMatchMaxAr') or {}).get('power') or 0
    lf = (history.get('xMatchMaxLf') or {}).get('power') or 0
    gl = (history.get('xMatchMaxGl') or {}).get('power') or 0
    cl = (history.get('xMatchMaxCl') or {}).get('power') or 0
    x_msg = ''
    if any([ar, lf, gl, cl]):
        x_msg = f"X max power:\n{ar:>7.2f}, {lf:>7.2f}, {gl:>7.2f}, {cl:>7.2f}"

    msg = f"""
```
{player['name']} #{player['nameId']}
{player['byname']}
{dict_lang['History.rank']}: {history['rank']}
{dict_lang['History.udemae']}: {history['udemae']}
{dict_lang['History.highest_udemae']}: {history['udemaeMax']}
{dict_lang['History.total_win']}: {history['winCountTotal']}{all_cnt} {r}
{dict_lang['History.total_turf_point']}: {history['paintPointTotal']:,}p
{dict_lang['History.badge']}: {len(history['badges'])}
{s_time:%Y-%m-%d %H:%M:%S} +08:00
{x_msg}
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
    win = False
    total_deliver_cnt = 0
    for w in detail['waveResults'][:3]:
        event = (w.get('eventWave') or {}).get('name') or ''
        wave_msg += f"`W{w['waveNumber']} {w['teamDeliverCount']}/{w['deliverNorm']}({w['goldenPopCount']}) " \
                    f"{d_w[w['waterLevel']]} {event}`\n"
        total_deliver_cnt += w['teamDeliverCount'] or 0
        if w['waveNumber'] == 3 and w['teamDeliverCount'] >= w['deliverNorm']:
            win = True
    if detail.get('bossResult'):
        w = detail['waveResults'][-1]
        r = 'GJ!' if detail['bossResult']['hasDefeatBoss'] else 'NG'
        s = ''
        scale = detail.get('scale')
        if scale and scale.get('gold'):
            s += f' 🏅️{scale["gold"]}'
        if scale and scale.get('silver'):
            s += f' 🥈{scale["silver"]}'
        if scale and scale.get('bronze'):
            s += f' 🥉{scale["bronze"]}'
        wave_msg += f"`EX {detail['bossResult']['boss']['name']} ({w['goldenPopCount']}) {r} {s}`\n"

    king_smell = detail.get("smellMeter")
    king_str = f'{king_smell}/5' if king_smell else ''
    msg = f"""
`{detail['afterGrade']['name']} {detail['afterGradePoint']} {detail['dangerRate']:.0%} {'🎉 ' if win else ''}+{detail['jobPoint']}({c_point}p) {king_str}`
{wave_msg}          `{total_deliver_cnt}`
{coop_row(my)}
"""
    for p in detail['memberResults']:
        msg += f"""{coop_row(p)}\n"""
    msg += '\n'
    for e in detail['enemyResults']:
        c = str(e.get('teamDefeatCount') or 0)
        nice = ''
        if e.get('popCount') <= int(c):
            nice = '√'
        if e.get('defeatCount'):
            c += f"({e['defeatCount']}"
        c += f" /{e['popCount']:<2}"
        msg += f"""`{c:>8}\t{(e.get('enemy') or {}).get('name') or ''} {nice}`\n"""
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

    for k in ('point', 'successive', 'KA', 'K', 'A', 'D', 'S', 'P', 'fest_power'):
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
    data = utils.gen_graphql_body('5f279779e7081f2d14ae1ddca0db2b6e')
    res = splt._request(data, skip_check_token=True)
    if not res:
        return '`Network error, try again`'
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
    data = utils.gen_graphql_body('f08a932d533845dde86e674e03bbb7d3')
    res = splt._request(data, skip_check_token=True)
    if not res:
        return '`Network error, try again`'
    stages = res['data']['stageRecords']['nodes']
    str_list = []
    for s in stages:
        if not s.get('stats'):
            s['stats'] = {'winRateAr': 0, 'winRateLf': 0, 'winRateGl': 0, 'winRateCl': 0}
        str_stage = f'''{s['name']}
{s['stats']['winRateAr'] or 0:>7.2%} {s['stats']['winRateLf'] or 0:>7.2%} {s['stats']['winRateGl'] or 0:>7.2%} {s['stats']['winRateCl'] or 0:>7.2%}
'''
        str_list.append(str_stage)

    msg = f'''
```
{''.join(str_list)}
```
/my\_schedule
 '''
    return msg


def get_fest_record(splt, lang='zh-CN'):
    dict_lang = get_dict_lang(lang)
    res = splt._request(utils.gen_graphql_body('44c76790b68ca0f3da87f2a3452de986'), skip_check_token=True)
    if not res:
        return '`Network error, try again`'
    records = res['data']['festRecords']['nodes']
    str_list = []
    for s in records:
        fest_id = s['id']
        teams = ', '.join((f"{i['teamName']}{'🏆' if (i['result'] or {}).get('isWinner') else ''}" for i in s['teams']))

        _d = utils.gen_graphql_body('96c3a7fd484b8d3be08e0a3c99eb2a3d', varname='festId', varvalue=fest_id)
        fes_detail = splt._request(_d, skip_check_token=True)
        str_detail = ''
        if fes_detail:
            p_r = ((fes_detail.get('data') or {}).get("fest") or {}).get('playerResult') or {}
            if p_r:
                max_power = p_r.get('maxFestPower') or 0
                avg = dict_lang['FesRecord.average']
                ttl = dict_lang['FesRecord.total']
                tri_c = ''
                if p_r.get('tricolorContributionEnabled'):
                    tri_c = f'{dict_lang["FesRecord.contribution_tricolor"]}: {avg}: {p_r.get("tricolorContributionAverage") or 0} {ttl}: {p_r.get("tricolorContributionTotal") or 0}\n'
                str_detail = f'''{p_r.get('grade')}
{dict_lang['FesRecord.got_horagai']}: {p_r.get('horagai') or 0}
{dict_lang['FesRecord.contribution_regular']}: {avg} {p_r.get('regularContributionAverage') or 0}, {ttl} {p_r.get('regularContributionTotal') or 0}
{dict_lang['FesRecord.contribution_challenge']}: {avg} {p_r.get('challengeContributionAverage') or 0}, {ttl} {p_r.get('challengeContributionTotal') or 0}
{tri_c}{dict_lang['FesRecord.highest_fest_power']}: {max_power:.1f}
'''
                str_top = ''
                if max_power:
                    my_name = fes_detail['data']['currentPlayer']['name']
                    my_team = fes_detail['data']['fest']['myTeam']['teamName']
                    try:
                        _d = utils.gen_graphql_body('4869de13d0d209032b203608cb598aef', varname='festId', varvalue=fest_id)
                        top_res = splt._request(_d, skip_check_token=True)

                        for t in top_res['data']['fest']['teams']:
                            if t['teamName'] != my_team:
                                continue

                            my_team_id = t['id']
                            for n in t['result']['rankingHolders']['edges']:
                                n = n['node']
                                if n['name'] == my_name and int(max_power) == int(n['festPower']):
                                    str_top = f"{dict_lang['FesRecord.fest_ranking']}: #{n['rank']}"
                                    break

                            has_next_page = t['result']['rankingHolders']['pageInfo']['hasNextPage']
                            cursor = t['result']['rankingHolders']['pageInfo']['endCursor']
                            cnt = 0
                            while True:
                                if not has_next_page:
                                    break
                                _d = {
                                    "extensions": {
                                        "persistedQuery": {
                                            "sha256Hash": 'be2eb9e9b8dd680519eb59cc46c1a32b',
                                            "version": 1
                                        }
                                    },
                                    "variables": {
                                        'cursor': cursor,
                                        'first': 25,
                                        'id': my_team_id
                                    }
                                }
                                _d = json.dumps(_d)
                                page_top_res = splt._request(_d, skip_check_token=True)
                                for n in page_top_res['data']['node']['result']['rankingHolders']['edges']:
                                    n = n['node']
                                    if n['name'] == my_name and int(max_power) == int(n['festPower']):
                                        str_top = f"{dict_lang['FesRecord.fest_ranking']}: #{n['rank']}"
                                        break
                                cursor = page_top_res['data']['node']['result']['rankingHolders']['pageInfo']['endCursor']
                                has_next_page = page_top_res['data']['node']['result']['rankingHolders']['pageInfo']['hasNextPage']
                                logger.debug(f'get page:{my_team},  {cursor}, {has_next_page}')
                                if not has_next_page:
                                    break
                                cnt += 1
                                if cnt > 5:
                                    break

                    except Exception as e:
                        logger.error(e)
                    str_detail += f'{str_top}'
        str_stage = f'''{s['startTime'][:10].replace('-', '/')}-{s['endTime'][8:10]} {(s.get('lang') or '')[:2]}
{s['title']}({s['myTeam']['teamName']})
{teams}
{str_detail}

'''
        str_list.append(str_stage)

    msg = f'''
```
{''.join(str_list)}
```
 '''
    return msg


def get_my_schedule(splt):
    data = utils.gen_graphql_body('730cd98e84f1030d3e9ac86b6f1aae13')
    res = splt._request(data)
    if not res:
        return 'No schedule found!'

    data = utils.gen_graphql_body('f08a932d533845dde86e674e03bbb7d3')
    stage_record = splt._request(data, skip_check_token=True)

    dict_stage = {}
    for s in stage_record['data']['stageRecords']['nodes']:
        if not s or not s.get('stats'):
            continue
        dict_stage[s['id']] = {
            'VnNSdWxlLTE=': s['stats'].get('winRateAr'),
            'VnNSdWxlLTI=': s['stats'].get('winRateLf'),
            'VnNSdWxlLTM=': s['stats'].get('winRateGl'),
            'VnNSdWxlLTQ=': s['stats'].get('winRateCl'),
        }

    x_node = res['data']['xSchedules']['nodes']
    l_node = res['data']['leagueSchedules']['nodes']

    text = ''
    for idx, node in enumerate(res['data']['bankaraSchedules']['nodes'][:4]):
        s = node['bankaraMatchSettings']
        date_start = dt.strptime(node['startTime'], '%Y-%m-%dT%H:%M:%S%z')
        c_rid = s[0]['vsRule']['id']
        c_s1, c_s2 = s[0]['vsStages']
        o_rid = s[1]['vsRule']['id']
        o_s1, o_s2 = s[1]['vsStages']

        x = x_node[idx]['xMatchSetting']
        x_rid = x['vsRule']['id']
        x_s1, x_s2 = x['vsStages']

        l = l_node[idx]['leagueMatchSetting']
        l_rid = l['vsRule']['id']
        l_s1, l_s2 = l['vsStages']

        row = f'''
`C: {s[0]['vsRule']['name']} ({get_r(dict_stage, c_s1['id'], c_rid)}, {get_r(dict_stage, c_s2['id'], c_rid)})
{c_s1['name']}, {c_s2['name']}
O: {s[1]['vsRule']['name']} ({get_r(dict_stage, o_s1['id'], o_rid)}, {get_r(dict_stage, o_s2['id'], o_rid)})
{o_s1['name']}, {o_s2['name']}
X: {x['vsRule']['name']} ({get_r(dict_stage, x_s1['id'], x_rid)}, {get_r(dict_stage, x_s2['id'], x_rid)})
{x_s1['name']}, {x_s2['name']}
L: {l['vsRule']['name']} ({get_r(dict_stage, l_s1['id'], l_rid)}, {get_r(dict_stage, l_s2['id'], l_rid)})
{l_s1['name']}, {l_s2['name']}`
/img\_schedule\_{date_start.hour}
'''
        text += row
    msg = f'\n{text}'
    return msg


def get_r(_dict, stage_id, rule_id):
    rate = 0
    if stage_id not in _dict:
        return f'{rate:.2%}'
    rate = _dict[stage_id].get(rule_id) or 0
    return f'{rate:.2%}'


def get_friends(splt, lang='zh-CN'):
    data = utils.gen_graphql_body('f0a8ebc384cf5fbac01e8085fbd7c898')
    res = splt._request(data)
    if not res:
        return 'No friends found!'

    msg = ''
    _dict = defaultdict(int)
    for f in res['data']['friends']['nodes']:
        _state = f.get('onlineState')
        if _state == 'OFFLINE':
            continue
        if _state == 'VS_MODE_FIGHTING':
            _state = f'VS_MODE ({f["vsMode"]["mode"]})'
            if f['vsMode']['mode'] == 'BANKARA':
                if f['vsMode']['id'] == 'VnNNb2RlLTUx':
                    _state += 'O'
                else:
                    _state += 'C'

            elif f['vsMode']['mode'] == 'FEST':
                mod_id = f['vsMode']['id']
                if mod_id == 'VnNNb2RlLTY=':
                    _state += 'O'
                elif mod_id == 'VnNNb2RlLTg=':
                    _state += '3'
                else:
                    _state += 'C'
        _dict[_state] += 1
        n = f['playerName'] or f.get('nickname')
        if f['playerName'] and f['playerName'] != f['nickname']:
            n = f'{f["playerName"]}({f["nickname"]})'
        msg += f'''{n}\t\t {_state}\n'''
    msg = f'```\n{msg}\n```'
    _dict['TOTAL'] = sum(_dict.values())
    for k, v in _dict.items():
        msg += f'`{k:>20}: {v}`\n'
    return msg


def get_x_top(splt, lang='zh-CN'):
    sha = 'd771444f2584d938db8d10055599011d'
    res = splt._request(utils.gen_graphql_body(sha, varname='region', varvalue='PACIFIC'))
    res_a = splt._request(utils.gen_graphql_body(sha, varname='region', varvalue='ATLANTIC'), skip_check_token=True)
    if not res:
        return 'No X found!'

    x = res['data']['xRanking']['currentSeason']
    t = x['lastUpdateTime'].replace('T', ' ').replace('Z', '')
    region_p = region_x_top(x)
    x_a = res_a['data']['xRanking']['currentSeason']
    t_a = x_a['lastUpdateTime'].replace('T', ' ').replace('Z', '')
    region_a = region_x_top(x_a)

    msg = f'''```
{x['name']}
{res['data']['xRanking']['region']} {t}(UTC)
{region_p}
{res_a['data']['xRanking']['region']} {t_a}(UTC)
{region_a}
```
'''
    return msg


def region_x_top(x):
    ar = x['xRankingAr']['nodes'][0]
    lf = x['xRankingLf']['nodes'][0]
    gl = x['xRankingGl']['nodes'][0]
    cl = x['xRankingCl']['nodes'][0]
    return f'''{ar['xPower']} {ar['name']} #{ar['nameId']} {ar['weapon']['name']}
{lf['xPower']} {lf['name']} #{lf['nameId']} {lf['weapon']['name']}
{gl['xPower']} {gl['name']} #{gl['nameId']} {gl['weapon']['name']}
{cl['xPower']} {cl['name']} #{cl['nameId']} {cl['weapon']['name']}
'''



def get_ns_friends(splt):
    res = splt.app_request() or {}
    res = res.get('result')
    if not res:
        logger.info(res)
        return 'No friends found!'

    msg = ''
    for f in res.get('friends') or []:
        if (f.get('presence') or {}).get('state') != 'ONLINE' and f.get('isFavoriteFriend') is False:
            continue
        msg += f"{f.get('name')}\t"
        if (f.get('presence') or {}).get('state') == 'ONLINE':
            msg += f" {f['presence']['game'].get('name')}"
            if f['presence']['game'].get('totalPlayTime'):
                msg += f"({int(f['presence']['game'].get('totalPlayTime')/60)}h)"
        else:
            t = (f.get('presence') or {}).get('logoutAt') or 0
            if t:
                delt = str(dt.utcnow() - dt.utcfromtimestamp(t))
                tt = delt
                if tt.startswith('0'):
                    tt = tt.split(', ')[-1]
                tt = tt.split('.')[0][:-3].replace(':', 'h')
                msg += f" (offline about {tt})"
            else:
                msg += f" ({(f.get('presence') or {}).get('state', 'offline')})"
        msg += '\n'
    msg = f'```\n{msg}\n```'
    return msg
