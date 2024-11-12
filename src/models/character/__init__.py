import os
import numpy as np
import time
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon

from src.bases.models import IngameModel
from src.bases.errors import Error
from src.common.constants.character import (
    ITEM_LIST_HEADER, ITEM_LIST_FOOTER, ITEM_HEADER, STRUCTURE,
    MERC_ITEM_LIST_HEADER, FOOTER, STASH_SIZE, INVENTORY_SIZE
)
from src.models.item import Item
from src.common.utils import dec_to_hex, make_byte_array_from_hex, get_dict_key_from_value
from src.common.constants.dirs import D2S_STORAGE_DIR
from src.common.constants.items import HORADRIC_CUBE_SIZE, LOCATIONS, STORAGES


class Character(IngameModel):
    _hex_data_as_byte_array: list[str]
    
    _items: list[Item]
    _merc_items: list[Item]
    
    def __init__(self, **kwargs):
        super(Character, self).__init__(**kwargs)

        self._hex_data_as_byte_array = make_byte_array_from_hex(self.data)

        self._items = self._parse_items(self.item_start_index, self.item_list_footer_index)

        self._merc_items = []

        if self.merc_name_id:
            self._merc_items = self._parse_items(self.merc_item_start_index)

    @property
    def items(self):
        return self._items

    @property
    def version(self):
        index, length = STRUCTURE['version']
        value = self._hex_data_as_byte_array[index:index + length]
        value = ''.join(value[::-1])
        return int(value, 16)

    @property
    def item_list_header_index(self):
        return self.find_index(
            data=self._hex_data_as_byte_array,
            query=ITEM_LIST_HEADER
        )

    @property
    def item_list_footer_index(self):
        return self.find_index(
            data=self._hex_data_as_byte_array,
            query=ITEM_LIST_FOOTER
        )

    @property
    def item_start_index(self):
        return self.item_list_header_index + 4

    @property
    def merc_name_id(self):
        index, length = STRUCTURE['mercenary_name_id']
        value = self._hex_data_as_byte_array[index: index + length][::-1]
        value = ''.join(value)
        return int(value, 16)

    @property
    def merc_item_list_header_index(self):
        return self.find_index(
            data=self._hex_data_as_byte_array,
            query=MERC_ITEM_LIST_HEADER,
            offset=self.item_list_footer_index + len(ITEM_LIST_FOOTER)
        )

    @property
    def merc_item_start_index(self):
        return self.merc_item_list_header_index + 4

    @property
    def footer_index(self):
        return len(self._hex_data_as_byte_array) - len(FOOTER)

    def _parse_items(self, start: int, end: int = None):
        if not end:
            end = self.footer_index

        result = []
        items_data = self._hex_data_as_byte_array[start:end]
        items_data = ''.join(items_data)
        item_header_as_str = ''.join(ITEM_HEADER)
        items_data = items_data.split(item_header_as_str)

        for i in items_data:
            if not i:
                continue
            item_data = item_header_as_str + i
            result.append(Item(data=item_data))

        return result

    @staticmethod
    def calculate_checksum(data):
        index, length = STRUCTURE['checksum']
        result = np.int32(0)
        for i, b in enumerate(data):
            if index <= i < (index + length):
                b = '00'
            result = np.int32((result << 1) + np.int32(int(b, 16)) + (result < 0))
        if result < 0:
            result += (int('ffffffff', 16) + 1)
        return result

    def save(self, file_path: str, backup_path: str = None):
        result = self._hex_data_as_byte_array[:self.item_list_header_index]
        item_list_data = []
        item_list_data.extend(ITEM_LIST_HEADER)
        counted_items = list(filter(
            lambda x: x.location != 'socketed',
            self._items
        ))
        total_items_data = reversed(make_byte_array_from_hex(
            dec_to_hex(len(counted_items), length=4)
        ))
        item_list_data.extend(total_items_data)
        for item in self._items:
            item_list_data.extend(item.updated_data)
        item_list_data.extend(ITEM_LIST_FOOTER)
        result.extend(item_list_data)

        if self.merc_name_id:
            merc_item_list_data = []
            merc_item_list_data.extend(MERC_ITEM_LIST_HEADER)
            merc_counted_items = list(filter(
                lambda x: x.container != 'socketed',
                self._merc_items
            ))
            merc_item_list_data.extend(reversed(make_byte_array_from_hex(
                dec_to_hex(len(merc_counted_items),
                           length=4)
            )))
            for merc_item in self._merc_items:
                merc_item_list_data.extend(merc_item.updated_data)
            result.extend(merc_item_list_data)

        result.extend(FOOTER)

        file_size_index, file_size_length = STRUCTURE['file_size']
        file_size = make_byte_array_from_hex(dec_to_hex(len(result), length=file_size_length * 2))[::-1]
        result[file_size_index: file_size_index + file_size_length] = file_size

        checksum_index, checksum_length = STRUCTURE['checksum']
        checksum = self.calculate_checksum(result)
        checksum = make_byte_array_from_hex(dec_to_hex(
            checksum,
            length=checksum_length * 2
        ))[::-1]
        result[checksum_index: checksum_index + checksum_length] = checksum

        # backup
        if backup_path:
            with open(backup_path, 'wb') as file_ref:
                file_ref.write(bytes.fromhex(self.data))

        # origin = make_byte_array_from_hex(self._raw_data)
        #
        # for index, byte in enumerate(result):
        #     if byte != origin[index]:
        #         print('diff', index, byte, origin[index])

        with open(file_path, 'wb') as file_ref:
            file_ref.write(bytes.fromhex(''.join(result)))

    def scan_items_by_position(self,
                               location_code: int,
                               storage_code: int,
                               start_x: int = 0,
                               end_x: int = 0,
                               start_y: int = 0,
                               end_y: int = 0,
                               ) -> [Item]:
        result = []
        scanning_zone = Polygon([
            (start_x, start_y),
            (end_x, start_y),
            (start_x, end_y),
            (end_x, end_y),
        ])

        for item in self._items:

            item_storage_code = get_dict_key_from_value(
                data=STORAGES,
                value=item.storage
            )
            if item_storage_code != storage_code:
                continue

            item_location_code = get_dict_key_from_value(
                data=LOCATIONS,
                value=item.location
            )
            if item_location_code != location_code:
                continue

            for p in item.rect['points']:
                point = Point(*p)
                if not scanning_zone.contains(point):
                    break
            else:
                result.append(item)
        return result

    def add_items(self,
                  storage_code: int,
                  location_code: int,
                  from_dir: bool = False,
                  dir_path: str = None,
                  item_list: list[dict] = None,
                  storage_x: int = 0,
                  ):

        adding_items = []

        if from_dir:
            if not dir_path:
                raise Error(
                    'InvalidParams',
                    'Missing dir_path for add items from directory'
                )
            abs_dir_path = os.path.join(D2S_STORAGE_DIR, dir_path)
            for n in os.listdir(abs_dir_path):
                if not n.endswith('.d2s'):
                    continue
                item_full_path = os.path.join(abs_dir_path, n)
                with open(item_full_path, 'rb') as fr:
                    try:
                        item = Item(data=fr.read().hex())
                    except Exception as e:
                        raise Error(
                            'InvalidParams',
                            f'Invalid item from {item_full_path}: {e}'
                        )
                    adding_items.append(item)
        else:
            for item_data in item_list:
                try:
                    item_path = item_data['path']
                    quantity = item_data['quantity']
                except KeyError as e:
                    raise Error(
                        'InvalidParams',
                        f'Missing {e} for item data'
                    )
                item_full_path = os.path.join(D2S_STORAGE_DIR, item_path)
                with open(item_full_path, 'rb') as fr:
                    try:
                        item = Item(data=fr.read().hex())
                    except Exception as e:
                        raise Error(
                            'InvalidParams',
                            f'Invalid item from {item_full_path}: {e}'
                        )
                    for i in range(quantity):
                        adding_items.append(item.clone())

        storage = LOCATIONS.get(storage_code)
        if not storage:
            raise Error(
                'InvalidParams',
                f'Unsupported storage: {storage_code}'
            )
        if storage == 'inventory':
            max_x, max_y = INVENTORY_SIZE
        elif storage == 'horadric_cube':
            max_x, max_y = HORADRIC_CUBE_SIZE
        else:
            max_x, max_y = STASH_SIZE

        y = 0
        x = storage_x or 0

        for index, item in enumerate(adding_items):
            width, height = item.size

            item.change_position(
                storage_code=storage_code,
                location_code=location_code,
                storage_x=x,
                storage_y=y
            )
            item.update_id(int(time.time()))
            self._items.append(item)
            print(f'Added item: {item.code}')

            x += width
            if (x + width - 1) > max_x:
                x = 0
                y = min(y + height, max_y)

    def duplicate_items(self,
                        item: Item,
                        location_id: int,
                        container_id: int,
                        quantity: int = 1,
                        location_x_coordinate: int = 0):
        location = LOCATIONS.get(location_id)
        if not location:
            raise Error(
                'InvalidParams',
                f'Unsupported location: {location_id}'
            )

        if location == 'inventory':
            max_x, max_y = INVENTORY_SIZE
        elif location == 'horadric_cube':
            max_x, max_y = HORADRIC_CUBE_SIZE
        else:
            max_x, max_y = STASH_SIZE

        width, height = item.size

        y = 0
        x = location_x_coordinate or 0
        for i in range(quantity):
            cloned_item = item.clone()
            print(x, y, i)
            cloned_item.change_position(
                location_id=location_id,
                container_id=container_id,
                location_x_coordinate=x,
                location_y_coordinate=y
            )
            self._items.append(cloned_item)

            x += width
            if (x + width - 1) > max_x:
                x = 0
                y = min(y + height, max_y)
