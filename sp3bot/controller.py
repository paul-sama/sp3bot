import base64
import json
from datetime import datetime as dt
from telegram import Update
from loguru import logger
from telegram.ext import ContextTypes
from .model import show_schedule, show_coop, show_mall
from .botdecorator import check_user_handler, check_session_handler
from .db import get_or_set_user, get_all_user
from .splat import Splatoon
from .bot_iksm import log_in, login_2, A_VERSION, post_battle_to_stat_ink
from .msg import get_battle_msg, INTERVAL, get_summary, get_coop_msg


@check_user_handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="""
I'm a bot for splatoon3, please select the function you want to use:
/help show more
   """)


@check_user_handler
async def help_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="""
/start - start the bot
/schedule - show the schedule
/full_schedule - show the full schedule
/coop_schedule - show the coop schedule
/mall - show the mall
/help - show this help message
/login - login
/me - show your info
/last - show the last battle or coop
/start_push - start push mode
/set_api_key - set stat.ink api_key
/show_db_info - show db info

source code: https://github.com/paul-sama/sp3bot
    """, disable_web_page_preview=True)


@check_user_handler
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=show_schedule(), parse_mode='Markdown')


@check_user_handler
async def full_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=show_schedule(True), parse_mode='Markdown')


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
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Sorry, I didn't understand. /help")


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f'login: {update.effective_user.username}')
    url, auth_code_verifier = log_in(A_VERSION)
    context.user_data['auth_code_verifier'] = auth_code_verifier
    logger.info(f'get login url: {url}')
    logger.info(f'auth_code_verifier: {auth_code_verifier}')
    if url:
        msg = f"""
Make sure you have fully read the "Token generation" section of the s3s's readme before proceeding.
https://github.com/frozenpandaman/s3s#token-generation-

Navigate to this URL in your browser:
{url}
Log in, right click the "Select this account" button, copy the link address, and /set_token the_link_address
"""
        logger.info(msg)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, disable_web_page_preview=True)


async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    token = text[10:]
    logger.info(f'{update.effective_user.username} set_token: {token}')
    if not token:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Please past the link address after /set_token")
        return

    auth_code_verifier = context.user_data['auth_code_verifier']
    logger.info(f'auth_code_verifier: {auth_code_verifier}')
    session_token = login_2(use_account_url=token, auth_code_verifier=auth_code_verifier)
    if session_token == 'skip':
        msg = 'set token failed, please try again. /login'
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        return
    logger.info(f'session_token: {session_token}')
    user = get_or_set_user(user_id=update.effective_user.id, session_token=session_token)
    await context.bot.send_message(chat_id=update.effective_chat.id, text='set_token success')


@check_session_handler
async def set_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        api_key = context.args[0]
        if len(api_key) != 43:
            raise IndexError
    except IndexError:
        msg = 'Please copy you api_key from https://stat.ink/profile then paste after /set_api_key'
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=msg, disable_web_page_preview=True)
        return
    logger.info(f'set_api_key: {api_key}')

    get_or_set_user(user_id=update.effective_user.id, api_key=api_key)
    msg = 'set_api_key success, bot will check every 3 hours and post your data to stat.ink'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


async def get_last_battle_or_coop(user_id, for_push=False):
    user = get_or_set_user(user_id=user_id)
    splt = Splatoon(user_id, user.session_token)

    # get last battle
    res = splt.get_recent_battles(skip_check_token=True if for_push else False)
    b_info = res['data']['latestBattleHistories']['historyGroups']['nodes'][0]['historyDetails']['nodes'][0]
    battle_id = b_info['id']

    # get last coop
    res = splt.get_coops()
    c_point = res['data']['coopResult']['pointCard']['regularPoint']
    coop_id = res['data']['coopResult']['historyGroups']['nodes'][0]['historyDetails']['nodes'][0]['id']
    battle_t = base64.b64decode(battle_id).decode('utf-8').split('_')[0].split(':')[-1]
    coop_t = base64.b64decode(coop_id).decode('utf-8').split('_')[0].split(':')[-1]

    if battle_t > coop_t:
        if for_push:
            return battle_id, b_info, True
        msg = get_last_msg(splt, battle_id, b_info)
        return msg
    else:
        if for_push:
            return coop_id, c_point, False
        msg = get_last_msg(splt, coop_id, c_point, False)
        return msg


def get_last_msg(splt, _id, extra_info, is_battle=True):
    if is_battle:
        battle_detail = splt.get_battle_detail(_id)
        msg = get_battle_msg(extra_info, battle_detail)
    else:
        coo_detail = splt.get_coop_detail(_id)
        msg = get_coop_msg(extra_info, coo_detail)
    return msg


@check_session_handler
async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await get_last_battle_or_coop(user_id)
    await context.bot.send_message(chat_id=user_id, text=msg, parse_mode='Markdown')


@check_session_handler
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id)
    splt = Splatoon(update.effective_user.id, user.session_token)
    res = splt.get_summary()
    all_res = splt.get_all_res()
    coop = splt.get_coop_summary()
    msg = get_summary(res, all_res, coop)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')


@check_session_handler
async def start_push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id, push=True, push_cnt=0)
    chat_id = update.effective_chat.id
    context.job_queue.run_repeating(push_latest_battle, interval=INTERVAL, name=str(chat_id), chat_id=chat_id,
                                    job_kwargs=dict(misfire_grace_time=6))
    msg = f'Start push! check new data(battle or coop) every {INTERVAL} seconds. /stop_push to stop'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


async def push_latest_battle(context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f'push_latest_battle: {context.job.name}')
    chat_id = context.job.chat_id
    battle_id, _info, is_battle = await get_last_battle_or_coop(chat_id, for_push=True)

    user = get_or_set_user(user_id=chat_id)
    if user.user_info:
        user_info = json.loads(user.user_info)
        last_battle_id = user_info.get('battle_id')
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
                logger.info(f'{user.username}, {msg}')
                await context.bot.send_message(chat_id=chat_id, text=msg)
                return
            return

    logger.info(f'{user.username} get new battle!')
    user_info = json.dumps({'battle_id': battle_id})
    get_or_set_user(user_id=chat_id, user_info=user_info, push_cnt=0)
    splt = Splatoon(chat_id, user.session_token)
    msg = get_last_msg(splt, battle_id, _info, is_battle)
    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')


async def stop_push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id, push=False)
    chat_id = update.effective_chat.id
    msg = f'stop push!'
    current_jobs = context.job_queue.get_jobs_by_name(str(update.effective_user.id))
    if not current_jobs:
        return False
    for job in current_jobs:
        logger.info(f'job: {job.name}, {chat_id}')
        if job.name == str(chat_id):
            job.schedule_removal()
            logger.info(f'job: {job.name}, {chat_id} removed')
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


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
user_info: {user.user_info}
```
/clear\_db\_info  clear your data
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='MarkdownV2')


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
        user_info=None,
    )
    msg = "All your data cleared!"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


async def check_push_job(context: ContextTypes.DEFAULT_TYPE):
    logger.debug('check_push_job')
    users = get_all_user()
    job_queue = context.job.data
    for user in users:
        if user.push:
            chat_id = user.id
            logger.info(f'start push: {user.username}, {chat_id}')
            job_queue.run_repeating(push_latest_battle, interval=INTERVAL, name=str(chat_id), chat_id=chat_id,
                                    job_kwargs=dict(misfire_grace_time=6))


async def crontab_job(context: ContextTypes.DEFAULT_TYPE):
    now = dt.now()
    # run every 3 hours
    if not (now.hour % 3 == 0 and now.minute == 0):
        return
    logger.bind(cron=True).debug(f"crontab_job")
    users = get_all_user()
    for u in users:
        if not u.api_key:
            continue
        logger.bind(cron=True).debug(f"get user: {u.username}, have api_key: {u.api_key}")
        res = post_battle_to_stat_ink(user_name=u.username, session_token=u.session_token, api_key=u.api_key)
        if res:
            chat_id = u.id
            msg = f'push {res[0]} battles to stat.ink\n{res[1]}'
            await context.bot.send_message(chat_id=chat_id, text=msg, disable_web_page_preview=True)
