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
    name = p['name']
    t = f"`\t\t{ak:>2}, {k_str:>5}k, {d:>2}d, {ration:>4.1f}, {re['special']:>2}sp, {p['paint']:>4}p  {name}`\n"
    # if p['isMyself']:
    #     t = '  ------------>  ' + t.strip()
    #     if ak > 9:
    #         t = t.replace('->', '>')
    return t


def show_challenge(battle_info):
    msg = ''
    my_team = battle_info['data']['vsHistoryDetail']['myTeam']
    other_team = battle_info['data']['vsHistoryDetail']['otherTeams'][0]
    award = battle_info['data']['vsHistoryDetail']['awards']
    dict_a = {'GOLD': '🏅️', 'SILVER': '🥈', 'BRONZE': '🥉'}
    award_list = [f"{dict_a.get(a['rank'], '')}`{a['name']}`" for a in award]
    if battle_info['data']['vsHistoryDetail']['judgement'] == 'WIN':
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
    duration = battle_info['data']['vsHistoryDetail']['duration']
    knockout = battle_info['data']['vsHistoryDetail']['knockout']
    msg += f"\n`duration: {duration}, knockout: {knockout}`"
    msg += ('\n ' + '\n '.join(award_list) + '\n')
    return msg
