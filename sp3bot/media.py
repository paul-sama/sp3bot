
import mmh3
import time
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


def download_img(img_list):
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR)

    for img_name, img_url in img_list:
        if not img_url or 'nintendo.net' not in img_url:
            logger.debug(f'skip wrong img: {img_url}')
            continue
        path = img_url.split('?')[0].split('nintendo.net/')[1].rsplit('/', 1)[0]
        img_folder = f'{IMG_DIR}{path}'
        if not os.path.exists(img_folder):
            os.makedirs(img_folder)

        img_name = img_name.replace('/', '-')
        img_path = f'{img_folder}/{img_name}.png'
        if not os.path.exists(img_path):
            logger.debug(f'downloading new file: {img_name}.png')
            p_res = requests.get(img_url, stream=True)
            with open(img_path, 'wb') as pf:
                shutil.copyfileobj(p_res.raw, pf)


def get_img_path(name, url):
    name = name.replace('/', '-')
    path = url.split('?')[0].split('nintendo.net/')[1].rsplit('/', 1)[0]
    img_path = f'{IMG_DIR}{path}/{name}.png'
    return img_path


def img_rounded_border(img_path):
    # https://www.imagemagick.org/Usage/thumbnails/#rounded_border
    e_img_path = img_path.replace('.png', '_edit.png')
    cmd = f'''
convert {img_path} \
          \( +clone -alpha extract -virtual-pixel black \
             -spread 10 -blur 0x3 -threshold 50% -spread 1 -blur 0x.7 \) \
          -alpha off -compose Copy_Opacity -composite {e_img_path}
    '''
    os.system(cmd)
    return e_img_path


def img_resize(img_path, size):
    e_img_path = img_path.replace('.png', '_edit.png')
    cmd = f'''
convert "{img_path}" -resize {size} "{e_img_path}"
    '''
    os.system(cmd)
    return e_img_path


def get_stage_img(cur_hour=0):
    sql = "SELECT * FROM `schedule` order by id desc limit 1"
    res = get_mysql_data('splatoon3', sql)
    if not res:
        return

    data = json.loads(res[0]['raw_data'])
    nodes = data['data']['bankaraSchedules']['nodes']
    x_nodes = data['data']['xSchedules']['nodes']

    idx = -1
    for n in nodes:
        idx += 1
        date_start = dt.strptime(n['startTime'], '%Y-%m-%dT%H:%M:%S%z')
        if date_start.hour != cur_hour:
            continue

        path_img_schedule = f"{IMG_DIR}images/schedule/{n['startTime']}.png"
        if os.path.exists(path_img_schedule):
            logger.debug(f'found schedule img: {path_img_schedule}')
            return path_img_schedule

        pth_dir = os.path.dirname(path_img_schedule)
        if not os.path.exists(pth_dir):
            os.makedirs(pth_dir)

        c_stages = n['bankaraMatchSettings'][0]['vsStages']
        o_stages = n['bankaraMatchSettings'][1]['vsStages']
        x_stages = x_nodes[idx]['xMatchSetting']['vsStages']

        download_img([
            (c_stages[0]['name'], c_stages[0]['image']['url']), (c_stages[1]['name'], c_stages[1]['image']['url']),
            (o_stages[0]['name'], o_stages[0]['image']['url']), (o_stages[1]['name'], o_stages[1]['image']['url']),
            (x_stages[0]['name'], x_stages[0]['image']['url']), (x_stages[1]['name'], x_stages[1]['image']['url']),
        ])

        dir_tmp = f'{IMG_DIR}images'

        if not os.path.exists(dir_tmp):
            os.makedirs(dir_tmp)
        os.chdir(dir_tmp)

        img_stage1 = get_img_path(c_stages[0]['name'], c_stages[0]['image']['url'])
        img_stage2 = get_img_path(c_stages[1]['name'], c_stages[1]['image']['url'])
        img_stage3 = get_img_path(o_stages[0]['name'], o_stages[0]['image']['url'])
        img_stage4 = get_img_path(o_stages[1]['name'], o_stages[1]['image']['url'])
        img_stage5 = get_img_path(x_stages[0]['name'], x_stages[0]['image']['url'])
        img_stage6 = get_img_path(x_stages[1]['name'], x_stages[1]['image']['url'])
        c_rule = base64.b64decode(n['bankaraMatchSettings'][0]['vsRule']['id']).decode('utf-8')
        o_rule = base64.b64decode(n['bankaraMatchSettings'][1]['vsRule']['id']).decode('utf-8')
        x_rule = base64.b64decode(x_nodes[idx]['xMatchSetting']['vsRule']['id']).decode('utf-8')

        for c in [
            f'convert +append {img_rounded_border(img_stage1)} {img_rounded_border(img_stage2)} c.png',
            f'convert +append {img_rounded_border(img_stage3)} {img_rounded_border(img_stage4)} o.png',
            f'convert +append {img_rounded_border(img_stage5)} {img_rounded_border(img_stage6)} x.png',
            f'convert -append  {c_rule}.png c.png {o_rule}.png o.png {x_rule}.png x.png {path_img_schedule}'
        ]:
            logger.debug(c)
            os.system(c)

        if os.path.exists(path_img_schedule):
            logger.debug(f'set img: {path_img_schedule}')
            return path_img_schedule
        else:
            logger.debug(f'not found path_img_schedule')


def get_coop_img():
    sql = "SELECT * FROM `schedule` order by id desc limit 1"
    res = get_mysql_data('splatoon3', sql)
    if not res:
        return

    data = json.loads(res[0]['raw_data'])
    nodes = data['data']['coopGroupingSchedule']['regularSchedules']['nodes']

    path_img_schedule = f"{IMG_DIR}images/schedule/coop_{nodes[0]['endTime']}.png"
    if os.path.exists(path_img_schedule):
        logger.debug(f'found schedule img: {path_img_schedule}')
        return path_img_schedule

    pth_dir = os.path.dirname(path_img_schedule)
    if not os.path.exists(pth_dir):
        os.makedirs(pth_dir)

    dir_tmp = f'{IMG_DIR}images'
    if not os.path.exists(dir_tmp):
        os.makedirs(dir_tmp)
    os.chdir(dir_tmp)

    coop_list = []
    for idx, n in enumerate(nodes):
        pth_node = f'{IMG_DIR}images/coop_node_{idx}.png'
        weapons = n['setting']['weapons']
        cmd = f'convert +append coop_stage_{n["setting"]["coopStage"]["coopStageId"]}.png '
        for w in weapons:
            download_img([
                (w['name'], w['image']['url'])
            ])
            pth_img = img_resize(get_img_path(w['name'], w['image']['url']), '128x128')
            cmd += f'"{pth_img}" '
        cmd += f'{pth_node}'

        logger.debug(cmd)
        os.system(cmd)
        coop_list.append(pth_node)

    cmd = f'convert -append {" ".join(coop_list)} {path_img_schedule}'
    logger.debug(cmd)
    os.system(cmd)

    if os.path.exists(path_img_schedule):
        logger.debug(f'set img: {path_img_schedule}')
        return path_img_schedule
    else:
        logger.debug(f'not found path_img_schedule')


def get_seed_file(uid, outfit):
    h = mmh3.hash(uid) & 0xFFFFFFFF  # make positive
    key = base64.b64encode(bytes([k ^ (h & 0xFF) for k in bytes(uid, "utf-8")]))
    t = int(time.time())

    path_file = f'/tmp/gear_{t}.json'
    with open(path_file, "x") as fout:
        json.dump({"key": key.decode("utf-8"), "h": h, "timestamp": t, "gear": outfit}, fout)
    logger.debug(f'get_seed_file: {path_file}')
    return path_file


if __name__ == '__main__':
    get_stage_img()
