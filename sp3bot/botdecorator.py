#!/usr/bin/env python
# -*- coding: utf-8 -*-

import functools
from loguru import logger
from telegram import Update
from .db import get_or_set_user


def check_user_handler(func):

    @functools.wraps('func')
    async def wrapper(*args, **kwargs):
        # logger.info(f'wrapper: {args}, {kwargs}, {func.__name__}')

        ctx = args[1]
        if isinstance(args[0], Update):
            update = args[0]
            user_id = update.effective_user.id
            user_name = update.effective_user.username
            first_name = update.effective_user.first_name
            last_name = update.effective_user.last_name
            full_name = f'{first_name} {last_name}'
            text = getattr(update.message, "text", "")
            logger.info(f'{func.__name__:>20}, {user_id}, {user_name}, {full_name} input: {text}')
            get_or_set_user(user_id=user_id, user_name=user_name, first_name=first_name, last_name=last_name)
            # await ctx.bot.send_message(chat_id=user_id, text='xxxx', parse_mode='Markdown')

        result = await func(*args, **kwargs)
        return result

    return wrapper


def check_session_handler(func):

    @functools.wraps('func')
    async def wrapper(*args, **kwargs):
        # logger.info(f'wrapper: {args}, {kwargs}, {func.__name__}')

        ctx = args[1]
        if isinstance(args[0], Update):
            update = args[0]
            if not update.effective_user:
                logger.debug(f'{func.__name__:>20}, effective_user is none, update: {update}')
                return
            user_id = update.effective_user.id
            user_name = update.effective_user.username
            first_name = update.effective_user.first_name
            last_name = update.effective_user.last_name
            full_name = f'{first_name or ""} {last_name or ""}'
            text = getattr(update.message, "text", "")
            logger.info(f'{func.__name__:>20}, {user_id}, {user_name}, {full_name} input: {text}')
            get_or_set_user(user_id=user_id, user_name=user_name, first_name=first_name, last_name=last_name)
            user = get_or_set_user(user_id=user_id)
            if not user.session_token:
                msg = f'Hello {user.first_name or full_name}! please /login'
                logger.debug(update.message)
                if getattr(getattr(update.message, "chat", ""), "type", "") == 'private':
                    logger.debug(f'private chat')
                    logger.info(msg)
                    await ctx.bot.send_message(chat_id=user_id, text=msg)
                return

        result = await func(*args, **kwargs)
        return result

    return wrapper


async def send_bot_msg(ctx, **kwargs):
    try:
        return await ctx.bot.send_message(**kwargs)
    except Exception as e:
        logger.error(f'send_bot_msg: {kwargs}\n{e}')
        if not kwargs.get('text'):
            return
