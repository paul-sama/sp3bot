import os
import sys
import time
import requests
from loguru import logger
from .db import get_or_set_user
from .bot_iksm import A_VERSION, APP_USER_AGENT

pth = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(pth)
sys.path.append(f'{pth}/s3s')
import iksm
import utils

API_URL = 'https://api.lp1.av5ja.srv.nintendo.net'
WEB_VIEW_VERSION = '2.0.0-bd36a652'


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
            self.user_lang = user.acc_loc if user.acc_loc else self.user_lang

    def get_bullet(self, web_service_token, web_view_ver, app_user_agent, user_lang, user_country):
        """Returns a bulletToken."""

        app_head = {
            'Content-Length': '0',
            'Content-Type': 'application/json',
            'Accept-Language': user_lang,
            'User-Agent': app_user_agent,
            'X-Web-View-Ver': web_view_ver,
            'X-NACOUNTRY': user_country,
            'Accept': '*/*',
            'Origin': API_URL,
            'X-Requested-With': 'com.nintendo.znca'
        }
        app_cookies = {
            '_gtoken': web_service_token  # X-GameWebToken
        }
        url = f"{API_URL}/api/bullet_tokens"
        r = requests.post(url, headers=app_head, cookies=app_cookies)
        try:
            return r.json()['bulletToken']
        except Exception as e:
            logger.error(f'{self.user_id} get_bullet error. {r.status_code}, {e}')
            logger.warning(r.text)
            raise Exception(f'{self.user_id} get_bullet error. {r.status_code}')

    def set_gtoken_and_bullettoken(self):
        F_GEN_URL = 'https://api.imink.app/f'
        new_gtoken, acc_name, acc_lang, acc_country = iksm.get_gtoken(F_GEN_URL, self.session_token, A_VERSION)
        new_bullettoken = self.get_bullet(new_gtoken, WEB_VIEW_VERSION, APP_USER_AGENT, acc_lang, acc_country)
        self.gtoken = new_gtoken
        self.bullet_token = new_bullettoken
        logger.info(f'{self.user_id} tokens updated.')
        logger.debug(f'new gtoken: {new_gtoken}')
        logger.debug(f'new bullettoken: {new_bullettoken}')
        get_or_set_user(user_id=self.user_id, gtoken=new_gtoken, bullettoken=new_bullettoken)
        return True

    def headbutt(self, bullet_token):
        graphql_head = {
            'Authorization': f'Bearer {bullet_token}',
            'Accept-Language': self.user_lang,
            'User-Agent': APP_USER_AGENT,
            'X-Web-View-Ver': WEB_VIEW_VERSION,
            'Content-Type': 'application/json',
            'Accept': '*/*',
            'Origin': API_URL,
            'X-Requested-With': 'com.nintendo.znca',
            'Referer': f'{API_URL}/?lang={self.user_lang}&na_country={self.user_country}&na_lang={self.user_lang}',
            'Accept-Encoding': 'gzip, deflate'
        }
        return graphql_head

    def test_page(self):
        data = utils.gen_graphql_body(utils.translate_rid["HomeQuery"])
        # t = time.time()
        test = requests.post(utils.GRAPHQL_URL, data=data,
                             headers=self.headbutt(self.bullet_token), cookies=dict(_gtoken=self.gtoken))
        # logger.debug(f'_test_page: {time.time() - t:.3f}s')
        if test.status_code != 200:
            logger.info(f'{self.user_id} tokens expired.')
            self.set_gtoken_and_bullettoken()

    def _request(self, data, skip_check_token=False):
        try:
            if not skip_check_token:
                self.test_page()
            t = time.time()
            res = requests.post(utils.GRAPHQL_URL, data=data,
                                headers=self.headbutt(self.bullet_token), cookies=dict(_gtoken=self.gtoken))
            logger.debug(f'_request: {time.time() - t:.3f}s')
            if res.status_code != 200:
                logger.info(f'{self.user_id} tokens expired.')
                self.set_gtoken_and_bullettoken()
            else:
                return res.json()
        except Exception as e:
            logger.error(f'_request error: {e}')
            return None

    def get_recent_battles(self, skip_check_token=False):
        data = utils.gen_graphql_body(utils.translate_rid['LatestBattleHistoriesQuery'])
        res = self._request(data, skip_check_token)
        return res

    def get_battle_detail(self, battle_id, skip_check_token=True):
        data = utils.gen_graphql_body(utils.translate_rid['VsHistoryDetailQuery'], "vsResultId", battle_id)
        res = self._request(data, skip_check_token)
        return res

    def get_coops(self, skip_check_token=True):
        data = utils.gen_graphql_body(utils.translate_rid['CoopHistoryQuery'])
        res = self._request(data, skip_check_token)
        return res

    def get_coop_detail(self, battle_id, skip_check_token=True):
        data = utils.gen_graphql_body(utils.translate_rid['CoopHistoryDetailQuery'], "coopHistoryDetailId", battle_id)
        res = self._request(data, skip_check_token)
        return res

    def get_summary(self, skip_check_token=False):
        data = utils.gen_graphql_body('32b6771f94083d8f04848109b7300af5')
        res = self._request(data, skip_check_token)
        return res

    def get_all_res(self, skip_check_token=True):
        data = utils.gen_graphql_body('f8ae00773cc412a50dd41a6d9a159ddd')
        res = self._request(data, skip_check_token)
        return res

    def get_coop_summary(self, skip_check_token=True):
        data = utils.gen_graphql_body('2fd21f270d381ecf894eb975c5f6a716')
        res = self._request(data, skip_check_token)
        return res
