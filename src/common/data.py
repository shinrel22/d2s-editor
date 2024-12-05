import json
import os

from src.common.utils import decompress_data
from src.common.constants.dirs import DATA_DIR, TMR_DIR
from config import DATA_ENCRYPTION_KEY


def load_data_from_file(data_path: str, tmp_path: str) -> dict:
    data = None
    if os.path.exists(tmp_path):
        data = json.load(open(tmp_path))

    if not data:
        data = decompress_data(
            data=open(data_path, 'rb').read(),
            encryption_key=DATA_ENCRYPTION_KEY
        )
        data = json.loads(data.decode())

        with open(
                tmp_path,
                'w'
        ) as fr:
            fr.write(json.dumps(data))

    return data


PARSED_DATA_DIR = os.path.join(TMR_DIR, 'data')
if not os.path.exists(PARSED_DATA_DIR):
    os.makedirs(PARSED_DATA_DIR)

BASE_ITEMS = load_data_from_file(
    data_path=os.path.join(DATA_DIR, 'base_items.dat'),
    tmp_path=os.path.join(PARSED_DATA_DIR, 'base_items.json'),
)
ITEM_TYPES = load_data_from_file(
    data_path=os.path.join(DATA_DIR, 'item_types.dat'),
    tmp_path=os.path.join(PARSED_DATA_DIR, 'item_types.json'),
)
ITEM_BASE_MODS = load_data_from_file(
    data_path=os.path.join(DATA_DIR, 'item_mods.dat'),
    tmp_path=os.path.join(PARSED_DATA_DIR, 'item_mods.json'),
)
ITEM_BASE_STATS = load_data_from_file(
    data_path=os.path.join(DATA_DIR, 'item_stats.dat'),
    tmp_path=os.path.join(PARSED_DATA_DIR, 'item_stats.json'),
)
SKILLS = load_data_from_file(
    data_path=os.path.join(DATA_DIR, 'skills.dat'),
    tmp_path=os.path.join(PARSED_DATA_DIR, 'skills.json'),
)
