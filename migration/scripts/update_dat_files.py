import os.path

from src.common.constants.dirs import DATA_DIR, TMR_DIR
from src.common.utils import compress_data
from config import DATA_ENCRYPTION_KEY

file_names = [
    'base_items',
    'item_mods',
    'item_stats',
    'item_types',
    'skills',
]

for file_name in file_names:
    dat_path = os.path.join(DATA_DIR, f'{file_name}.dat')
    json_path = os.path.join(TMR_DIR, f'data\\{file_name}.json')

    with open(dat_path, 'wb') as fr:
        fr.write(compress_data(
            data=open(json_path, 'rb').read(),
            encryption_key=DATA_ENCRYPTION_KEY
        ))
