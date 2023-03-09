
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, CallbackQueryHandler
from .controller import (
    start, help_msg, schedule, full_schedule, coop_schedule, mall, unknown, unknown_text, set_token, login, last,
    start_push, stop_push, set_api_key, show_db_info, clear_db_info, crontab_job, me, check_push_job,
    set_lang, lang_button, weapon_record, stage_record, fest_record, my_schedule, set_battle_info, get_seed,
    error_handler, friends, x_top, ns_friends, check_favorite_friends, stop_cff
)
from configs import TELEGRAM_BOT_TOKEN
TMT = 60


def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).concurrent_updates(True) \
        .read_timeout(TMT).write_timeout(TMT).connect_timeout(TMT).pool_timeout(TMT).build()

    start_handler = CommandHandler('start', start)
    application.add_handler(start_handler)

    application.add_handler(CommandHandler('help', help_msg))
    application.add_handler(CommandHandler('schedule', schedule))
    application.add_handler(CommandHandler('my_schedule', my_schedule))
    application.add_handler(CommandHandler('full_schedule', full_schedule))
    application.add_handler(CommandHandler('coop_schedule', coop_schedule))
    application.add_handler(CommandHandler('mall', mall))
    application.add_handler(CommandHandler('login', login))
    application.add_handler(CommandHandler('set_lang', set_lang))
    application.add_handler(CallbackQueryHandler(lang_button))
    application.add_handler(CommandHandler('set_token', set_token))
    application.add_handler(CommandHandler('me', me))
    application.add_handler(CommandHandler('friends', friends))
    application.add_handler(CommandHandler('ns_friends', ns_friends))
    application.add_handler(CommandHandler('check_favorite_friends', check_favorite_friends))
    application.add_handler(CommandHandler('check_favorite_friends_stop', stop_cff))
    application.add_handler(CommandHandler('x_top', x_top))
    application.add_handler(CommandHandler('weapon_record', weapon_record))
    application.add_handler(CommandHandler('stage_record', stage_record))
    application.add_handler(CommandHandler('fest_record', fest_record))
    application.add_handler(CommandHandler('last', last))
    application.add_handler(CommandHandler('set_battle_info', set_battle_info))
    application.add_handler(CommandHandler('start_push', start_push))
    application.add_handler(CommandHandler('stop_push', stop_push))
    application.add_handler(CommandHandler('set_api_key', set_api_key))
    application.add_handler(CommandHandler('show_db_info', show_db_info))
    application.add_handler(CommandHandler('clear_db_info', clear_db_info))
    application.add_handler(CommandHandler('get_seed', get_seed))

    # Other handlers
    application.add_handler(MessageHandler(filters.COMMAND, unknown))
    application.add_handler(MessageHandler(filters.ALL, unknown_text))

    # ...and the error handler
    application.add_error_handler(error_handler)

    job_queue = application.job_queue
    job_queue.run_once(check_push_job, 1, job_queue)
    job_queue.run_repeating(crontab_job, interval=60, first=1, name='crontab_job',
                            job_kwargs=dict(misfire_grace_time=50, coalesce=False, max_instances=3))

    application.run_polling()
