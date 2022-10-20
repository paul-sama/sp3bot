#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

from loguru import logger
from sqlalchemy import Column, String, create_engine, Integer, Boolean, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

import configs

# Create database
Base = declarative_base()


# Table
class UserTable(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    username = Column(String(), unique=True, nullable=True)
    first_name = Column(String(), nullable=False)
    last_name = Column(String(), nullable=True)
    user_id_sp = Column(String(), nullable=True)
    push = Column(Boolean(), default=False)
    push_cnt = Column(Integer(), default=0)
    api_key = Column(String(), nullable=True)
    acc_loc = Column(String(), nullable=True)
    gtoken = Column(String(), nullable=True)
    bullettoken = Column(String(), nullable=True)
    session_token = Column(String(), nullable=True)
    user_info = Column(Text(), nullable=True)


engine = create_engine(configs.DATABASE_URI)

Base.metadata.create_all(engine)

DBSession = sessionmaker(bind=engine)


def get_or_set_user(**kwargs):
    user_id = kwargs.get('user_id')
    session = DBSession()

    if not user_id:
        logger.error('user_id is None')
        return

    user = session.query(UserTable).filter(UserTable.id == user_id).first()
    if user:
        logger.debug(f'get user from db: {user.id}, {user.username}, {kwargs}')
        for k, v in kwargs.items():
            if not getattr(user, k, None) or k == 'user_id':
                continue
            if 'name' not in k:
                logger.debug(f'update user {k}={v}')
            setattr(user, k, v)
            session.commit()
        # session.close()
        return user

    logger.info('create user to db')
    user = UserTable(
        id=user_id,
        username=kwargs.get('user_name'),
        first_name=kwargs.get('first_name'),
        last_name=kwargs.get('last_name'),
    )

    session.add(user)
    session.commit()
    # session.close()
    return user


def get_all_user():
    session = DBSession()
    users = session.query(UserTable).all()
    return users
