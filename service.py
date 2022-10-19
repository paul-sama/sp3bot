#!/usr/bin/env python
# -*- coding: utf-8 -*-
from sp3bot.bot import main
from loguru import logger

logger.add("sp3bot.log")


if __name__ == '__main__':
    logger.info('Starting sp3bot'.center(120, '-'))
    main()
