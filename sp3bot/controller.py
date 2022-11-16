import base64
import json
import os
import time
from collections import defaultdict
from datetime import datetime as dt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from telegram.ext import ContextTypes
from .model import show_schedule, show_coop, show_mall
from .botdecorator import check_user_handler, check_session_handler, send_bot_msg
from .db import get_or_set_user, get_all_user
from .splat import Splatoon
from .bot_iksm import log_in, login_2, A_VERSION, post_battle_to_stat_ink, post_battle_to_stat_ink_s3si_ts
from .msg import (
    MSG_HELP, get_battle_msg, INTERVAL, get_summary, get_coop_msg, get_statics, get_weapon_record, get_stage_record,
    get_my_schedule, get_fest_record
)


@check_user_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_bot_msg(context, chat_id=update.effective_chat.id, text="""
I'm a bot for splatoon3, please select the function you want to use:
/help show more
   """)


@check_user_handler
async def help_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_bot_msg(context, chat_id=update.effective_chat.id, text=MSG_HELP)


@check_user_handler
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=show_schedule(), parse_mode='Markdown')


@check_user_handler
async def full_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=show_schedule(True), parse_mode='Markdown')


@check_session_handler
async def my_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_or_set_user(user_id=user_id)
    splt = Splatoon(user_id, user.session_token)
    await send_bot_msg(context, chat_id=user_id, text=get_my_schedule(splt), parse_mode='Markdown')


@check_user_handler
async def coop_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=show_coop(), parse_mode='Markdown')


@check_user_handler
async def mall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=show_mall(), parse_mode='Markdown')


@check_user_handler
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Sorry, I didn't understand that command. /help")


@check_session_handler
async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text and len(text) > 500 and text.startswith('npf'):
        user_id = update.effective_user.id
        await set_session_token(context, user_id, text)
        return
    logger.debug(update.message)
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Sorry, I didn't understand. /help")


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dir_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        img_path = f'{dir_path}/screenshots/sp3bot-login.gif'
        await context.bot.send_animation(chat_id=update.effective_chat.id, animation=open(img_path, 'rb'))
    except Exception as e:
        logger.error(e)

    logger.info(f'login: {update.effective_user.username}')
    url, auth_code_verifier = log_in(A_VERSION)
    context.user_data['auth_code_verifier'] = auth_code_verifier
    logger.info(f'get login url: {url}')
    logger.info(f'auth_code_verifier: {auth_code_verifier}')
    if url:
        msg = f"""
Navigate to this URL in your browser:
{url}
Log in, right click the "Select this account" button, copy the link address, and paste below.
"""
        logger.info(msg)
        await send_bot_msg(context, chat_id=update.effective_chat.id, text=msg, disable_web_page_preview=True)


async def set_session_token(context, user_id, token_msg):
    try:
        auth_code_verifier = context.user_data['auth_code_verifier']
    except KeyError:
        await send_bot_msg(context, chat_id=user_id,
                           text="set token failed, please try again. /login")
        return

    logger.info(f'auth_code_verifier: {auth_code_verifier}')
    session_token = login_2(use_account_url=token_msg, auth_code_verifier=auth_code_verifier)
    if session_token == 'skip':
        msg = 'set token failed, please try again. /login'
        await send_bot_msg(context, chat_id=user_id, text=msg)
        return
    logger.info(f'session_token: {session_token}')
    get_or_set_user(user_id=user_id, session_token=session_token)
    msg = f"""
Set token success! Bot now can get your splatoon3 data from SplatNet.
/set_lang - set language, default(zh-CN) 默认中文
/set_api_key - set stat.ink api_key, bot will sync your data to stat.ink
/me - show your info
/last - show the latest battle or coop
/start_push - start push mode
"""
    await send_bot_msg(context, chat_id=user_id, text=msg)

    user = get_or_set_user(user_id=user_id)
    Splatoon(user_id, user.session_token).set_gtoken_and_bullettoken()


async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    token = text[10:]
    logger.info(f'{update.effective_user.username} set_token: {token}')
    if not token:
        await send_bot_msg(context, chat_id=update.effective_chat.id,
                           text="Please past the link address after /set_token")
        return
    await set_session_token(context, user_id, token)


@check_user_handler
async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # https://github.com/frozenpandaman/s3s/wiki/languages
    all_lang = [
        ('German', 'de-DE'),
        ('English (UK/Australia)', 'en-GB'),
        ('English (US)', 'en-US'),
        ('Spanish (Spain)', 'es-ES'),
        ('Spanish (Latin America)', 'es-MX'),
        ('French (Canada)', 'fr-CA'),
        ('French (France)', 'fr-FR'),
        ('Italian', 'it-IT'),
        ('Japanese', 'ja-JP'),
        ('Korean', 'ko-KR'),
        ('Dutch', 'nl-NL'),
        ('Russian', 'ru-RU'),
        ('Chinese (China)', 'zh-CN'),
        ('Chinese (Taiwan)', 'zh-TW'),
    ]
    keyboard = [
        [InlineKeyboardButton(i[0], callback_data=i[1])] for i in all_lang
    ]

    try:
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Please set your language, default[Chinese (China)]:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(e)


async def lang_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    try:
        query = update.callback_query

        await query.answer()
        lang = query.data
        get_or_set_user(user_id=update.effective_user.id, acc_loc=lang)
        await query.edit_message_text(text=f"Set language Success! {lang}")
    except Exception as e:
        logger.error(e)


@check_user_handler
async def set_battle_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    battle_show_type = context.args[0] if context.args else None

    if not battle_show_type:
        msg = '''
set battle info, default show name
/set_battle_info 1 - name
/set_battle_info 2 - weapon
/set_battle_info 3 - name (weapon)
/set_battle_info 4 - weapon (name)
'''
        await send_bot_msg(context, chat_id=user_id, text=msg)
        return

    user = get_or_set_user(user_id=user_id)
    db_user_info = defaultdict(str)
    if user and user.user_info:
        db_user_info = json.loads(user.user_info)
    db_user_info['battle_show_type'] = str(battle_show_type)
    get_or_set_user(user_id=user_id, user_info=json.dumps(db_user_info))
    msg = await get_last_battle_or_coop(user_id)
    await send_bot_msg(context, chat_id=user_id, text=msg, parse_mode='Markdown')


@check_session_handler
async def set_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        api_key = context.args[0]
        if len(api_key) != 43:
            raise IndexError
    except IndexError:
        msg = '''Please copy you api_key from https://stat.ink/profile then paste after
/set_api_key your_api_key'''
        await send_bot_msg(context, chat_id=update.effective_chat.id, text=msg, disable_web_page_preview=True)
        return
    logger.info(f'set_api_key: {api_key}')

    user_id = update.effective_user.id
    get_or_set_user(user_id=user_id, api_key=api_key)
    msg = f'''set_api_key success, bot will check every 3 hours and post your data to stat.ink.
first sync will be in minutes.
    '''
    await send_bot_msg(context, chat_id=user_id, text=msg)

    # sync data immediately
    context.job_queue.run_once(crontab_job, 1, data={'user_id': user_id})


async def get_last_battle_or_coop(user_id, for_push=False):
    user = get_or_set_user(user_id=user_id)
    splt = Splatoon(user_id, user.session_token)

    # get last battle
    res = splt.get_recent_battles(skip_check_token=True if for_push else False)
    if not res:
        return None
    b_info = res['data']['latestBattleHistories']['historyGroups']['nodes'][0]['historyDetails']['nodes'][0]
    battle_id = b_info['id']
    battle_t = base64.b64decode(battle_id).decode('utf-8').split('_')[0].split(':')[-1]

    # get last coop
    res = splt.get_coops()
    try:
        c_point = res['data']['coopResult']['pointCard']['regularPoint']
        coop_id = res['data']['coopResult']['historyGroups']['nodes'][0]['historyDetails']['nodes'][0]['id']
        coop_t = base64.b64decode(coop_id).decode('utf-8').split('_')[0].split(':')[-1]
    except:
        c_point = 0
        coop_id = ''
        coop_t = ''

    if battle_t > coop_t:
        if for_push:
            return battle_id, b_info, True

        try:
            user_info = json.loads(user.user_info)
        except:
            user_info = {}
        msg = get_last_msg(splt, battle_id, b_info, battle_show_type=user_info.get('battle_show_type'))
        return msg
    else:
        if for_push:
            return coop_id, c_point, False
        msg = get_last_msg(splt, coop_id, c_point, False)
        return msg


def get_last_msg(splt, _id, extra_info, is_battle=True, **kwargs):
    try:
        if is_battle:
            battle_detail = splt.get_battle_detail(_id)
            kwargs['splt'] = splt
            msg = get_battle_msg(extra_info, battle_detail, **kwargs)
        else:
            coo_detail = splt.get_coop_detail(_id)
            msg = get_coop_msg(extra_info, coo_detail)
    except Exception as e:
        logger.exception(e)
        msg = f'get last {"battle" if is_battle else "coop"} failed, please try again later.'
    return msg


@check_session_handler
async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await get_last_battle_or_coop(user_id)
    await send_bot_msg(context, chat_id=user_id, text=msg, parse_mode='Markdown')


@check_session_handler
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id)
    splt = Splatoon(update.effective_user.id, user.session_token)
    res = splt.get_summary()
    all_res = splt.get_all_res()
    coop = splt.get_coop_summary()
    msg = get_summary(res, all_res, coop, lang=user.acc_loc)
    logger.debug(msg)
    await send_bot_msg(context, chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')


@check_session_handler
async def weapon_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id)
    splt = Splatoon(update.effective_user.id, user.session_token)
    msg = get_weapon_record(splt, lang=user.acc_loc)
    # logger.debug(msg)
    await send_bot_msg(context, chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')


@check_session_handler
async def stage_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id)
    splt = Splatoon(update.effective_user.id, user.session_token)
    msg = get_stage_record(splt)
    # logger.debug(msg)
    await send_bot_msg(context, chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')


@check_session_handler
async def fest_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id)
    splt = Splatoon(update.effective_user.id, user.session_token)
    msg = get_fest_record(splt, lang=user.acc_loc)
    logger.debug(msg)
    await send_bot_msg(context, chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')


@check_session_handler
async def start_push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = get_or_set_user(user_id=chat_id)
    if user.push:
        # if /start_push again, set push_cnt 0
        get_or_set_user(user_id=chat_id, push=True, push_cnt=0)
        await send_bot_msg(context, chat_id=chat_id, text='You have already started push. /stop_push to stop')
        return
    get_or_set_user(user_id=chat_id, push=True, push_cnt=0)
    current_statics = defaultdict(int)
    context.user_data['current_statics'] = current_statics
    context.job_queue.run_repeating(
        push_latest_battle, interval=INTERVAL,
        name=str(chat_id), chat_id=chat_id,
        data=dict(current_statics=current_statics),
        job_kwargs=dict(misfire_grace_time=9, coalesce=False, max_instances=3))
    msg = f'Start push! check new data(battle or coop) every {INTERVAL} seconds. /stop_push to stop'
    await send_bot_msg(context, chat_id=chat_id, text=msg)


async def push_latest_battle(context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f'push_latest_battle: {context.job.name}')
    chat_id = context.job.chat_id

    user = get_or_set_user(user_id=chat_id)
    if not user or user.push is False:
        logger.info(f'stop by user clear db: {context.job.name} stop')
        context.job.schedule_removal()
        return

    data = context.job.data or {}
    res = await get_last_battle_or_coop(chat_id, for_push=True)
    if not res:
        logger.info('no new battle or coop')
        return
    battle_id, _info, is_battle = res

    db_user_info = defaultdict(str)

    if user.user_info:
        db_user_info = json.loads(user.user_info)
        last_battle_id = db_user_info.get('battle_id')
        # logger.info(f'last_battle_id: {last_battle_id}')
        if last_battle_id == battle_id:
            push_cnt = user.push_cnt + 1
            if push_cnt % 60 == 0:
                # show log every 10 minutes
                logger.info(f'push_latest_battle: {user.username}, {chat_id}')

            get_or_set_user(user_id=chat_id, push_cnt=push_cnt)
            if push_cnt * INTERVAL / 60 > 30:
                context.job.schedule_removal()
                get_or_set_user(user_id=chat_id, push=False)
                msg = 'No game record for 30 minutes, stop push.'

                if data.get('current_statics'):
                    msg += get_statics(data['current_statics'])
                logger.info(f'{user.username}, {msg}')
                await send_bot_msg(context, chat_id=chat_id, text=msg, parse_mode='Markdown')
                return
            return

    logger.info(f'{user.id}, {user.username} get new {"battle" if is_battle else "coop"}!')
    db_user_info['battle_id'] = battle_id
    get_or_set_user(user_id=chat_id, user_info=json.dumps(db_user_info), push_cnt=0)
    splt = Splatoon(chat_id, user.session_token)
    msg = get_last_msg(splt, battle_id, _info, is_battle, battle_show_type=db_user_info.get('battle_show_type'), **data)
    await send_bot_msg(context, chat_id=chat_id, text=msg, parse_mode='Markdown')


@check_session_handler
async def stop_push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id, push=False)
    chat_id = update.effective_chat.id
    msg = f'Stop push!'
    current_statics = context.user_data.get('current_statics')
    if current_statics:
        msg += get_statics(current_statics)
    current_jobs = context.job_queue.get_jobs_by_name(str(update.effective_user.id))
    if not current_jobs:
        return False
    for job in current_jobs:
        logger.info(f'job: {job.name}, {chat_id}')
        if job.name == str(chat_id):
            job.schedule_removal()
            logger.info(f'job: {job.name}, {chat_id} removed')
    await send_bot_msg(context, chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')


@check_user_handler
async def show_db_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id)
    msg = f"""
```
user_name: {user.username}
gtoken: {user.gtoken}
bullettoken: {user.bullettoken}
session_token: {user.session_token}
push: {user.push}
push_cnt: {user.push_cnt}
api_key: {user.api_key}
acc_loc: {user.acc_loc}
user_info: {user.user_info}
```
/clear\_db\_info  clear your data
    """
    await send_bot_msg(context, chat_id=update.effective_chat.id, text=msg, parse_mode='MarkdownV2')


@check_user_handler
async def clear_db_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_or_set_user(
        user_id=update.effective_user.id,
        gtoken=None,
        bullettoken=None,
        session_token=None,
        push=False,
        push_cnt=0,
        api_key=None,
        acc_loc=None,
        user_info=None,
    )
    msg = "All your data cleared!"
    await send_bot_msg(context, chat_id=update.effective_chat.id, text=msg)


async def check_push_job(context: ContextTypes.DEFAULT_TYPE):
    logger.debug('check_push_job')
    users = get_all_user()
    job_queue = context.job.data
    for user in users:
        if user.push:
            chat_id = user.id
            logger.info(f'start push: {user.username}, {chat_id}')
            job_queue.run_repeating(push_latest_battle, interval=INTERVAL, name=str(chat_id), chat_id=chat_id,
                                    job_kwargs=dict(misfire_grace_time=9, coalesce=False, max_instances=3))


async def crontab_job(context: ContextTypes.DEFAULT_TYPE):
    now = dt.now()
    data = context.job.data or {}
    user_id = data.get('user_id')
    # run every 3 hours

    if not user_id:
        if not (now.hour % 3 == 0 and now.minute == 0):
            return

    logger.bind(cron=True).debug(f"crontab_job")
    users = get_all_user()
    for u in users:
        if not u.api_key:
            continue
        if user_id and user_id != u.id:
            continue
        u_id = u.id
        logger.bind(cron=True).debug(f"get user: {u.username}, have api_key: {u.api_key}")
        res = post_battle_to_stat_ink_s3si_ts(user_id=u_id, session_token=u.session_token,
                                              api_key=u.api_key, acc_loc=u.acc_loc)
        if res:
            chat_id = u.id
            msg = f'push {res[0]} battles to stat.ink\n{res[1]}'
            while True:
                try:
                    ret = await context.bot.send_message(chat_id=chat_id, text=msg, disable_web_page_preview=True)
                    if isinstance(ret, Message):
                        logger.bind(cron=True).debug(f"send message: {ret.text}")
                        break
                except Exception as e:
                    logger.bind(cron=True).error(f"post_battle_to_stat_ink: {e}")
                    time.sleep(5)
