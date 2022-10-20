import json

from loguru import logger

INTERVAL = 10


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


def get_battle_msg(b_info, battle_detail):
    mode = b_info['vsMode']['mode']
    rule = b_info['vsRule']['name']
    judgement = b_info['judgement']
    battle_detail = battle_detail['data']['vsHistoryDetail']
    bankara_match = ((battle_detail or {}).get('bankaraMatch') or {}).get('mode') or ''
    msg = f"`{mode}, {bankara_match}, {rule}, {judgement}`\n"

    my_team = battle_detail['myTeam']
    other_team = battle_detail['otherTeams'][0]
    award = battle_detail['awards']
    dict_a = {'GOLD': '🏅️', 'SILVER': '🥈', 'BRONZE': '🥉'}
    award_list = [f"{dict_a.get(a['rank'], '')}`{a['name']}`" for a in award]
    if judgement == 'WIN':
        teams = [my_team, other_team]
    else:
        teams = [other_team, my_team]

    text_list = []
    for p in teams[0]['players']:
        text_list.append(get_row_text(p))
    text_list.append('\n')
    for p in teams[1]['players']:
        text_list.append(get_row_text(p))
    for t in text_list:
        # logger.info(t)
        msg += t
    duration = battle_detail['duration']
    knockout = battle_detail['knockout']
    msg += f"\n`duration: {duration}, knockout: {knockout}`"
    msg += ('\n ' + '\n '.join(award_list) + '\n')
    # print(msg)
    return msg
