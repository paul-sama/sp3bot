#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys

from sp3bot.bot import main
from loguru import logger

logger.configure(handlers=[{"sink": sys.stderr, "level": "INFO"}])
logger.add("logs/sp3bot.log", level="DEBUG", filter=lambda record: "cron" not in record["extra"], rotation="500 MB")
logger.add("logs/cron_job.log", filter=lambda record: "cron" in record["extra"], rotation="500 MB")


if __name__ == '__main__':
    logger.info('Starting sp3bot'.center(120, '-'))
    main()
