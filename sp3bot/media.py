
import base64
import json
import os
import shutil
import requests
from datetime import datetime as dt
from subprocess import call
from loguru import logger

pth = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = f'{pth}/resource/'
try:
    from lib_paul import get_mysql_data
except ImportError:
    def get_mysql_data(db, sql):
        return None


def d_img(img_list):
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)

    for n, img in img_list:
        path = img.split('?')[0]
        path = path.split('nintendo.net/')[1].rsplit('/', 1)[0]
        img_name = f'{n}.png'
        img_folder = f'{IMG_DIR}{path}'
        if not os.path.exists(img_folder):
            os.makedirs(img_folder)
        img_path = f'{IMG_DIR}{path}/{n}.png'

        if not os.path.exists(img_path):
            logger.debug('downloading new file: %s' % img_name)
            p_res = requests.get(img, stream=True)
            with open(img_path, 'wb') as pf:
                shutil.copyfileobj(p_res.raw, pf)


def get_img_path(name, url):
    path = url.split('?')[0]
    path = path.split('nintendo.net/')[1].rsplit('/', 1)[0]
    img_path = f'{IMG_DIR}{path}/{name}.png'
    return img_path


def get_stage_img(cur_hour=0):
    sql = "SELECT * FROM `schedule` order by id desc limit 1"
    res = get_mysql_data('splatoon3', sql)
    if not res:
        return
    data = json.loads(res[0]['raw_data'])
    nodes = data['data']['bankaraSchedules']['nodes']

    for n in nodes:
        date_start = dt.strptime(n['startTime'], '%Y-%m-%dT%H:%M:%S%z')
        if date_start.hour != cur_hour:
            continue

        path_img_schedule = f"{IMG_DIR}images/schedule/{n['startTime']}.png"
        if os.path.exists(path_img_schedule):
            return path_img_schedule

        c_stages = n['bankaraMatchSettings'][0]['vsStages']
        c_rule = base64.b64decode(n['bankaraMatchSettings'][0]['vsRule']['id']).decode('utf-8')
        o_rule = base64.b64decode(n['bankaraMatchSettings'][1]['vsRule']['id']).decode('utf-8')
        o_stages = n['bankaraMatchSettings'][1]['vsStages']
        img_stage = get_img_path(c_stages[0]['name'], c_stages[0]['image']['url'])
        img_stage2 = get_img_path(c_stages[1]['name'], c_stages[1]['image']['url'])
        img_stage3 = get_img_path(o_stages[0]['name'], o_stages[0]['image']['url'])
        img_stage4 = get_img_path(o_stages[1]['name'], o_stages[1]['image']['url'])

        d_img([(c_stages[0]['name'], c_stages[0]['image']['url']), (c_stages[1]['name'], c_stages[1]['image']['url'])])
        d_img([(o_stages[0]['name'], o_stages[0]['image']['url']), (o_stages[1]['name'], o_stages[1]['image']['url'])])

        dir_tmp = f'{IMG_DIR}images'

        if not os.path.exists(dir_tmp):
            os.makedirs(dir_tmp)
        os.chdir(dir_tmp)
        call(['convert', '+append', img_stage, img_stage2, 'c.png'])

        call(['convert', '+append', img_stage3, img_stage4, 'o.png'])

        pth_dir = os.path.dirname(path_img_schedule)
        if not os.path.exists(pth_dir):
            os.makedirs(pth_dir)

        cmd = f'convert -append  {c_rule}.png c.png {o_rule}.png o.png {path_img_schedule}'
        logger.debug(cmd)
        os.system(cmd)

        logger.debug(path_img_schedule)
        return path_img_schedule


if __name__ == '__main__':
    get_stage_img()
