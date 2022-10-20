import os
import sys
import time
import requests
from loguru import logger
from .db import get_or_set_user
from .bot_iksm import A_VERSION

pth = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(pth)
sys.path.append(f'{pth}/s3s')
import iksm
import utils
from s3s import APP_USER_AGENT


class Splatoon:

    def __init__(self, user_id, session_token):
        self.user_id = user_id
        self.session_token = session_token
        self.user_lang = 'zh-CN'
        self.user_country = 'JP'
        self.bullet_token = ''
        self.gtoken = ''
        user = get_or_set_user(user_id=self.user_id)
        if user:
            self.bullet_token = user.bullettoken
            self.gtoken = user.gtoken

    def set_gtoken_and_bullettoken(self):
        F_GEN_URL = 'https://api.imink.app/f'
        new_gtoken, acc_name, acc_lang, acc_country = iksm.get_gtoken(F_GEN_URL, self.session_token, A_VERSION)
        new_bullettoken = iksm.get_bullet(new_gtoken, utils.get_web_view_ver(), APP_USER_AGENT, acc_lang, acc_country)
        self.gtoken = new_gtoken
        self.bullet_token = new_bullettoken
        logger.info(f'new gtoken: {new_gtoken}')
        logger.info(f'new bullettoken: {new_bullettoken}')
        user = get_or_set_user(user_id=self.user_id, gtoken=new_gtoken, bullettoken=new_bullettoken)
        return True

    def headbutt(self, bullet_token):
        graphql_head = {
            'Authorization': f'Bearer {bullet_token}',
            'Accept-Language': self.user_lang,
            'User-Agent': APP_USER_AGENT,
            'X-Web-View-Ver': utils.get_web_view_ver(),
            'Content-Type': 'application/json',
            'Accept': '*/*',
            'Origin': 'https://api.lp1.av5ja.srv.nintendo.net',
            'X-Requested-With': 'com.nintendo.znca',
            'Referer': f'https://api.lp1.av5ja.srv.nintendo.net/?lang={self.user_lang}&na_country={self.user_country}&na_lang={self.user_lang}',
            'Accept-Encoding': 'gzip, deflate'
        }
        return graphql_head

    def _request(self, data):
        t = time.time()
        res = requests.post(utils.GRAPHQL_URL, data=data,
                            headers=self.headbutt(self.bullet_token), cookies=dict(_gtoken=self.gtoken))
        logger.debug(f'_request: {time.time() - t:.3f}s')
        if res.status_code != 200:
            logger.info('tokens have expired.')
            self.set_gtoken_and_bullettoken()
            self._request(data)
        else:
            return res.json()

    def test_page(self):
        data = utils.gen_graphql_body(utils.translate_rid["HomeQuery"])
        test = requests.post(utils.GRAPHQL_URL, data=data,
                             headers=self.headbutt(self.bullet_token), cookies=dict(_gtoken=self.gtoken))
        if test.status_code != 200:
            logger.info('tokens have expired.')
            self.set_gtoken_and_bullettoken()
        else:
            logger.info('tokens are still valid.')

    def get_recent_battles(self):
        data = utils.gen_graphql_body(utils.translate_rid['LatestBattleHistoriesQuery'])
        res = self._request(data)
        return res

    def get_battle_detail(self, battle_id):
        data = utils.gen_graphql_body(utils.translate_rid['VsHistoryDetailQuery'], "vsResultId", battle_id)
        res = self._request(data)
        return res
