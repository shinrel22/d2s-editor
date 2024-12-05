import json
import os

from migration.utils import decompress_dat_file_from_decapitator
from src.common.constants.dirs import TMR_DIR, DATA_DIR
from src.common.utils import decompress_data, compress_data, convert_tsv_to_json
from config import DATA_ENCRYPTION_KEY


def update_item_mods():
    decapitator_file_path = os.path.join(TMR_DIR, 'decapitator\\props.dat')
    file_path = os.path.join(DATA_DIR, 'item_mods.dat')

    if os.path.exists(file_path):
        with open(file_path, 'rb') as fr:
            result = json.loads(decompress_data(data=fr.read(), encryption_key=DATA_ENCRYPTION_KEY))
    else:
        result = dict()

    for i in convert_tsv_to_json(
            decompress_dat_file_from_decapitator(decapitator_file_path)
    ):
        mod_id = i['#code']
        mod_id_as_int = int(mod_id)
        stat_code = i['stat']
        code = stat_code

        mod = {
            'code': code,
            'id': mod_id_as_int,
            'stat_code': stat_code,
            'positive_desc': i['descPositive']
        }

        teammate_codes = i.get('descGroupIDs')
        if teammate_codes:
            teammate_codes = teammate_codes.split(',')
        else:
            teammate_codes = []

        mod['teammate_codes'] = teammate_codes

        try:
            bits = int(i.get('bits'))
        except (TypeError, ValueError):
            bits = 0

        try:
            save_param_bits = int(i.get('saveParamBits'))
        except (TypeError, ValueError):
            save_param_bits = 0

        try:
            min_value = int(i.get('add'))
        except (TypeError, ValueError):
            min_value = 0

        mod['min_value'] = min_value
        mod['length'] = bits + save_param_bits

        if mod_id in result:
            for k, v in mod.items():
                if k not in result[mod_id]:
                    result[mod_id][k] = v

        else:
            result[mod_id] = mod

    compressed_data = compress_data(
        data=json.dumps(result).encode(),
        encryption_key=DATA_ENCRYPTION_KEY
    )

    with open(file_path, 'wb') as fr:
        fr.write(compressed_data)

    decompress_data(
        data=compressed_data,
        encryption_key=DATA_ENCRYPTION_KEY
    )


def update_item_stats():
    decapitator_file_path = os.path.join(TMR_DIR, 'decapitator\\itemstatcost.tsv')
    file_path = os.path.join(DATA_DIR, 'item_stats.dat')

    if os.path.exists(file_path):
        with open(file_path, 'rb') as fr:
            result = json.loads(decompress_data(data=fr.read(), encryption_key=DATA_ENCRYPTION_KEY))
    else:
        result = dict()

    raw_data = convert_tsv_to_json(
        open(decapitator_file_path, 'r').read()
    )

    for i in raw_data:
        code = i['Stat']
        try:
            stat_id = int(i['ID'])
        except ValueError:
            continue

        stat = {
            'code': code,
            'id': stat_id
        }

        try:
            save_add = int(i.get('Save Add'))
        except (TypeError, ValueError):
            save_add = 0

        try:
            save_bits = int(i.get('Save Bits'))
        except (TypeError, ValueError):
            save_bits = 0

        try:
            save_param_bits = int(i.get('Save Param Bits'))
        except (TypeError, ValueError):
            save_param_bits = 0

        stat['length'] = save_bits + save_add + save_param_bits

        if code not in result:
            result[code] = stat

    compressed_data = compress_data(
        data=json.dumps(result).encode(),
        encryption_key=DATA_ENCRYPTION_KEY
    )

    with open(file_path, 'wb') as fr:
        fr.write(compressed_data)

    with open(os.path.join(TMR_DIR, 'decapitator\\itemstatcost.json'), 'w') as fr:
        fr.write(json.dumps(raw_data))

    decompress_data(
        data=compressed_data,
        encryption_key=DATA_ENCRYPTION_KEY
    )


def update_base_items():
    decapitator_file_path = os.path.join(TMR_DIR, 'decapitator\\items.dat')
    file_path = os.path.join(DATA_DIR, 'base_items.dat')

    if os.path.exists(file_path):
        with open(file_path, 'rb') as fr:
            result = json.loads(decompress_data(data=fr.read(), encryption_key=DATA_ENCRYPTION_KEY))
    else:
        result = dict()

    for i in convert_tsv_to_json(
            decompress_dat_file_from_decapitator(decapitator_file_path)
    ):
        code = i['#code']

        base_item = {
            'code': code,
            'name': i['name'],
            'width': i['width'],
            'height': i['height'],
            'type_codes': i['type'].split(',')
        }
        try:
            class_id = int(i.get('class'))
            if class_id < 0:
                class_id = None
        except TypeError:
            class_id = None

        stackable = i.get('stackable')
        if stackable == '1':
            base_item['stackable'] = True

        base_item['class_id'] = class_id

        if code not in result:
            result[code] = base_item

    compressed_data = compress_data(
        data=json.dumps(result).encode(),
        encryption_key=DATA_ENCRYPTION_KEY
    )

    with open(file_path, 'wb') as fr:
        fr.write(compressed_data)

    decompress_data(
        data=compressed_data,
        encryption_key=DATA_ENCRYPTION_KEY
    )


def update_item_types():
    decapitator_file_path = os.path.join(TMR_DIR, 'decapitator\\itemtypes.dat')
    file_path = os.path.join(DATA_DIR, 'item_types.dat')

    if os.path.exists(file_path):
        with open(file_path, 'rb') as fr:
            result = json.loads(decompress_data(data=fr.read(), encryption_key=DATA_ENCRYPTION_KEY))
    else:
        result = dict()

    for i in convert_tsv_to_json(
            decompress_dat_file_from_decapitator(decapitator_file_path)
    ):
        code = i['#code']

        item_type = {
            'code': code,
            'name': i['name'],
        }

        equiv_codes = i.get('equiv')
        if equiv_codes:
            equiv_codes = set(equiv_codes.split(','))
        else:
            equiv_codes = set()
        item_type['equiv_codes'] = list(equiv_codes)

        if code not in result:
            result[code] = item_type

    compressed_data = compress_data(
        data=json.dumps(result).encode(),
        encryption_key=DATA_ENCRYPTION_KEY
    )

    with open(file_path, 'wb') as fr:
        fr.write(compressed_data)

    decompress_data(
        data=compressed_data,
        encryption_key=DATA_ENCRYPTION_KEY
    )


def update_skills():
    decapitator_file_path = os.path.join(TMR_DIR, 'decapitator\\skills.dat')
    file_path = os.path.join(DATA_DIR, 'skills.dat')

    if os.path.exists(file_path):
        with open(file_path, 'rb') as fr:
            result = json.loads(decompress_data(data=fr.read(), encryption_key=DATA_ENCRYPTION_KEY))
    else:
        result = dict()

    for i in convert_tsv_to_json(
            decompress_dat_file_from_decapitator(decapitator_file_path)
    ):
        skill_id = i['#code']

        skill = {
            'id': int(skill_id),
            'name': i['name'],
        }

        try:
            class_id = int(i['class'])
        except (TypeError, ValueError):
            class_id = -1

        skill['class_id'] = class_id

        if skill_id not in result:
            result[skill_id] = skill

    compressed_data = compress_data(
        data=json.dumps(result).encode(),
        encryption_key=DATA_ENCRYPTION_KEY
    )

    with open(file_path, 'wb') as fr:
        fr.write(compressed_data)

    decompress_data(
        data=compressed_data,
        encryption_key=DATA_ENCRYPTION_KEY
    )


if __name__ == '__main__':
    update_item_mods()
    update_item_stats()
    update_base_items()
    update_item_types()
    update_skills()
