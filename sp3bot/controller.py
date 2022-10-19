import json
from telegram import Update
from loguru import logger
from telegram.ext import ContextTypes
from .model import show_schedule, show_coop, show_mall
from .botdecorator import check_user_handler, check_session_handler
from .db import get_or_set_user
from .splat import Splatoon
from .bot_iksm import log_in, login_2, A_VERSION
from .msg import show_challenge, INTERVAL


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
/last - show the last battle
/start_push - start push
/stop_push - stop push
/show_db_info - show db info
/clear_db_info - clear db info
    """)


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
    url, auth_code_verifier = log_in(A_VERSION, get_url=True)
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
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


async def set_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    token = text[10:]
    logger.info(f'set_token: {token}')
    if not token:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Please enter the link address after /set_token")
        return

    auth_code_verifier = context.user_data['auth_code_verifier']
    logger.info(f'auth_code_verifier: {auth_code_verifier}')
    session_token = login_2(use_account_url=token, auth_code_verifier=auth_code_verifier)
    logger.info(f'session_token: {session_token}')
    user = get_or_set_user(user_id=update.effective_user.id, session_token=session_token)
    await context.bot.send_message(chat_id=update.effective_chat.id, text='set_token success')


@check_session_handler
async def last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id)
    splt = Splatoon(update.effective_user.id, user.session_token)
    res = splt.get_recent_battles()
    history_groups = res['data']['latestBattleHistories']['historyGroups']['nodes']
    details = history_groups[0]['historyDetails']['nodes']
    detail = details[0]

    battle_id = detail["id"]
    # logger.info(f'battle_id: {battle_id}')
    context.user_data['battle_id'] = battle_id
    mode = detail['vsMode']['mode']
    rule = detail['vsRule']['name']
    j = detail['judgement']
    text = f"{mode:>8}, {j:>4}, {rule}"

    battle = splt.get_battle_detail(battle_id)
    msg = show_challenge(battle)
    # msg = text
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode='Markdown')


@check_session_handler
async def start_push(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_or_set_user(user_id=update.effective_user.id, push=True, push_cnt=0)
    chat_id = update.effective_chat.id
    context.job_queue.run_repeating(push_latest_battle, interval=INTERVAL, name=str(chat_id), chat_id=chat_id)
    msg = f'start push!'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)


async def push_latest_battle(context: ContextTypes.DEFAULT_TYPE):
    # update = context.update
    chat_id = context.job.chat_id
    # logger.info(f'push_latest_battle: {chat_id}')
    user = get_or_set_user(user_id=chat_id)
    splt = Splatoon(chat_id, user.session_token)
    res = splt.get_recent_battles()

    history_groups = res['data']['latestBattleHistories']['historyGroups']['nodes']
    details = history_groups[0]['historyDetails']['nodes']
    detail = details[0]

    battle_id = detail["id"]
    if user.user_info:
        user_info = json.loads(user.user_info)
        last_battle_id = user_info.get('battle_id')
        # logger.info(f'last_battle_id: {last_battle_id}')
        if last_battle_id == battle_id:
            push_cnt = user.push_cnt + 1
            get_or_set_user(user_id=chat_id, push_cnt=push_cnt)
            if push_cnt * INTERVAL / 60 > 30:
                context.job.schedule_removal()
                msg = f'已经推送了{push_cnt}次, 无游戏记录，不再推送 /start_push'
                logger.info(f'{user.username}, {msg}')
                await context.bot.send_message(chat_id=chat_id, text=msg)
                return
            return

    user_info = json.dumps({'battle_id': battle_id})
    get_or_set_user(user_id=chat_id, user_info=user_info, push_cnt=0)
    mode = detail['vsMode']['mode']
    rule = detail['vsRule']['name']
    j = detail['judgement']
    text = f"{mode:>8}, {j:>4}, {rule}"

    battle = splt.get_battle_detail(battle_id)
    msg = show_challenge(battle)
    # msg = text
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
user_info: {user.user_info}
```
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
        user_info=None,
    )
    msg = "All data cleared!"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
