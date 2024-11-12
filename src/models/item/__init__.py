import copy
import time
import hashlib
from math import ceil

from src.bases.errors import Error
from src.bases.models import IngameModel, BaseModel
from src.common.constants.items import (
    NON_EAR_STRUCTURE, RARITIES, ITEM_TYPES,
    BASE_STRUCTURE, LOCATIONS, STORAGES, EQUIPPED_LOCATIONS, ITEM_FOOTER,
    BASE_ITEMS, START_DEFENSE_VALUE, START_MAX_DURABILITY_VALUE,
    START_CURRENT_DURABILITY_VALUE, MOD_ID_LENGTH, ITEM_BASE_MODS,
    ITEM_BASE_STATS, END_OF_MOD_SECTION,
    ADDING_DMG_WITH_DURATION_MOD_CODES, ADDING_DMG_MOD_CODES, AFFIX_MOD_CODES
)
from src.common.utils import (
    bin_to_hex, bin_to_dec, split_array,
    dec_to_bin, make_byte_array_from_hex,
)


class ItemType(BaseModel):
    code: str
    name: str

    equiv_codes: list[str] = []


class BaseItem(BaseModel):
    code: str
    name: str
    width: int
    height: int
    stackable: bool = False
    class_id: int | None = None
    type_codes: list[str]

    is_armor: bool = False
    is_weapon: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.is_armor = self.has_related_type('armo')
        self.is_weapon = self.has_related_type('weap')

    @staticmethod
    def find_item_type(code: str) -> ItemType | None:
        if code not in ITEM_TYPES:
            return None
        return ItemType(**ITEM_TYPES[code])

    def has_related_type(self, target_type_code: str) -> bool:

        if target_type_code in self.type_codes:
            return True

        def handle_regression(_target_type_code: str, _type_code: str) -> bool:
            item_type = self.find_item_type(_type_code)
            if not item_type:
                return False
            if _target_type_code in item_type.equiv_codes:
                return True
            for i in item_type.equiv_codes:
                if handle_regression(_target_type_code=_target_type_code, _type_code=i):
                    return True
            return False

        for type_code in self.type_codes:
            if handle_regression(
                    _target_type_code=target_type_code,
                    _type_code=type_code
            ):
                return True
        return False


class BaseStat(BaseModel):
    id: int
    code: str
    length: int


class Stat(IngameModel):
    pass


class BaseModifierFactor(BaseModel):
    code: str
    length: int
    min_value: float
    conversion_rate: float = 1


class BaseModifier(BaseModel):
    id: int
    code: str
    length: int
    stat_code: str
    factors: list[BaseModifierFactor] = []


class ModFactorValues(BaseModel):
    value: float | int | None = None
    monster_id: int | None = None
    class_id: int | None = None
    skill_id: int | None = None
    skill_level: int | None = None
    chance: int | None = None
    max_dmg: float | int | None = None
    duration: int | None = None


class Modifier(IngameModel):
    base: BaseModifier
    runeword: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def id(self):
        return str(int(hashlib.sha256(self.data.encode('utf-8')).hexdigest(), 16) % 10 ** 8)

    @property
    def factor_values(self) -> ModFactorValues:
        result = ModFactorValues()
        start_index = MOD_ID_LENGTH

        for f in self.refine_factors(self.base):
            factor_data = self.data[start_index:start_index + f.length]
            factor_value = (bin_to_dec(factor_data[::-1]) * f.conversion_rate) + f.min_value

            factor_code_data_type_info = result.__fields__.get(f.code)
            if factor_code_data_type_info is None:
                raise Error(
                    'FactorCodeNotFound',
                    f'Factor code not found in ModFactorValues: {f.code}'
                )

            if not isinstance(factor_value, factor_code_data_type_info.annotation):
                factor_value = int(factor_value)

            setattr(result, f.code, factor_value)
            start_index += f.length

        return result

    def update(self, values: dict = None):
        if values is None:
            values = dict()

        factor_data = []

        for f in self.refine_factors(self.base):

            min_value = f.min_value
            max_value = bin_to_dec('1' * f.length)

            value = values.get(f.code)

            if value is None:
                value = max_value
            else:
                value = min(value - min_value, max_value)

            converted_value = value / f.conversion_rate
            converted_value = ceil(converted_value)

            factor_data.extend(reversed(dec_to_bin(converted_value, length=f.length)))

        data_as_array = list(reversed(dec_to_bin(self.base.id, length=MOD_ID_LENGTH)))
        data_as_array.extend(factor_data)

        self.data = ''.join(data_as_array)

    @staticmethod
    def refine_factors(base_mod: BaseModifier) -> list[BaseModifierFactor]:

        default_base_factor = BaseModifierFactor(
            code='value',
            min_value=0,
            length=base_mod.length
        )

        if not base_mod.factors:
            return [default_base_factor]

        result = [*base_mod.factors]

        if base_mod.code in ADDING_DMG_MOD_CODES:
            adding_max_dmg_base_mod = Item.find_base_mod_by_id(base_mod.id + 1)
            adding_max_dmg_base_mod.factors[0].code = 'max_dmg'
            result.append(adding_max_dmg_base_mod.factors[0])

            if base_mod.code in ADDING_DMG_WITH_DURATION_MOD_CODES:
                adding_dmg_duration_base_mod = Item.find_base_mod_by_id(base_mod.id + 2)
                adding_dmg_duration_base_mod.factors[0].code = 'duration'
                result.append(adding_dmg_duration_base_mod.factors[0])

        return result


class Item(IngameModel):
    _hex_data_as_byte_array: list[str]
    _bin_data_as_array: list[str]

    _base: BaseItem

    _mods: dict[str, Modifier]

    _stats: dict[str, Stat]

    def __init__(self, **kwargs):
        super(Item, self).__init__(**kwargs)

        self._hex_data_as_byte_array = make_byte_array_from_hex(self.data)
        self._bin_data_as_array = self._parse_data_to_bit()

        self._base = self._load_base_item()

        self._mods = self._load_mods()

    @property
    def mods(self):
        return list(filter(lambda m: not m.runeword, self._mods.values()))

    @property
    def rw_mods(self):
        return list(filter(lambda m: m.runeword, self._mods.values()))

    @staticmethod
    def get_base_mod_from_stat_code(stat_code: str) -> BaseModifier | None:
        for i in ITEM_BASE_MODS.values():
            if i['stat_code'] == stat_code:
                return BaseModifier(**i)
        return None

    @property
    def base(self):
        return self._base

    def _load_base_item(self) -> BaseItem:
        data = BASE_ITEMS.get(self.code)

        if not data:
            raise Error(
                message=f'Base item not found: {self.code}, {self.location}'
            )
        return BaseItem(**data)

    def _read_data(self, index, length):
        value = self._bin_data_as_array[index: index + length]
        return bin_to_dec(''.join(reversed(value)))

    def _parse_data_to_bit(self):

        # little endian
        reversed_data = reversed(self._hex_data_as_byte_array)

        joined_data = ''.join(reversed_data)

        bin_data = dec_to_bin(int(joined_data, 16))

        return list(reversed(bin_data))

    @staticmethod
    def find_item_stat_from_id(stat_id: int) -> BaseStat | None:
        for stat in ITEM_BASE_STATS.values():
            if stat['id'] == stat_id:
                return BaseStat(**stat)
        return None

    @staticmethod
    def find_base_mod_by_id(id: int) -> BaseModifier | None:
        id_as_str = str(id)
        if id_as_str not in ITEM_BASE_MODS:
            return None
        return BaseModifier(**ITEM_BASE_MODS[id_as_str])

    @staticmethod
    def find_base_mod_by_code(code: str) -> BaseModifier | None:
        for i in ITEM_BASE_MODS.values():
            if i['code'] == code:
                return BaseModifier(**i)
        return None

    def _load_mods(self):
        mods = dict()

        if self.is_ear or self.is_simple:
            return mods

        length = len(self._bin_data_as_array) - self.start_mod_index

        total_mod_data = self._bin_data_as_array[self.start_mod_index: self.start_mod_index + length]

        start_index = 0

        rw_loading = False

        while start_index < (len(total_mod_data) - 1):
            mod_data_index = start_index + MOD_ID_LENGTH
            base_mod_id_as_bin_array = total_mod_data[start_index:mod_data_index]
            base_mod_id = bin_to_dec(''.join(reversed(base_mod_id_as_bin_array)))

            if base_mod_id == bin_to_dec(''.join(END_OF_MOD_SECTION)):
                # continue to load rw mods
                if self.is_runeword:
                    start_index += len(END_OF_MOD_SECTION)
                    rw_loading = True
                    continue
                else:
                    break

            item_base_mod = self.find_base_mod_by_id(id=base_mod_id)
            if item_base_mod:
                mod_data_length = sum(map(
                    lambda f: f.length,
                    Modifier.refine_factors(item_base_mod)
                ))

                next_mod_index = mod_data_index + mod_data_length
                mod_data_as_bin_array = total_mod_data[start_index: next_mod_index]
                mod_data = ''.join(mod_data_as_bin_array)

                mod = Modifier(data=mod_data,
                               runeword=rw_loading,
                               base=item_base_mod)
                mods[mod.id] = mod

            else:
                # if we encounter an unknown mod,
                # we find the item stat using mod_code as stat id
                # then we use the bit length from stat to skip to the next mod
                print(f'Mod not found: {base_mod_id} at index {start_index}'
                      f' - item: {self._base.model_dump_json()} - id: {self.id}')

                item_stat = self.find_item_stat_from_id(stat_id=base_mod_id)
                # if there's no such stat,
                # we stop
                if not item_stat:
                    print(f'Stat not found: {base_mod_id} at index {start_index}'
                          f' - item: {self._base.name} - id: {self.id}')
                    break

                stat_length = item_stat.length
                next_mod_index = mod_data_index + stat_length

            start_index = next_mod_index

        return mods

    @property
    def is_socketed(self):
        index, length = BASE_STRUCTURE['is_socketed']
        value = self._bin_data_as_array[index]
        return value == '1'

    @property
    def is_runeword(self):
        index, length = BASE_STRUCTURE['is_runeword']
        value = self._bin_data_as_array[index]
        return value == '1'

    @property
    def is_ear(self):
        index, length = BASE_STRUCTURE['is_ear']
        value = self._bin_data_as_array[index]
        return value == '1'

    @property
    def is_simple(self):
        index, length = BASE_STRUCTURE['is_simple']
        value = self._bin_data_as_array[index]
        return value == '1'

    @property
    def location(self):
        index, length = BASE_STRUCTURE['location']
        value = self._bin_data_as_array[index:index + length][::-1]
        value = ''.join(value)
        value = bin_to_dec(value)
        return LOCATIONS.get(value)

    @property
    def equipped_location(self):
        index, length = BASE_STRUCTURE['equipped_location']
        value = self._bin_data_as_array[index:index + length][::-1]
        value = ''.join(value)
        value = bin_to_dec(value)
        return EQUIPPED_LOCATIONS.get(value)

    @property
    def storage(self):
        index, length = BASE_STRUCTURE['storage']
        value = self._bin_data_as_array[index: index + length][::-1]
        value = ''.join(value)
        value = bin_to_dec(value)
        return STORAGES.get(value)

    @property
    def storage_x(self):
        index, length = BASE_STRUCTURE['storage_x']
        value = self._bin_data_as_array[index: index + length][::-1]
        value = ''.join(value)
        return bin_to_dec(value)

    @property
    def storage_y(self):
        index, length = BASE_STRUCTURE['storage_y']
        value = self._bin_data_as_array[index: index + length][::-1]
        value = ''.join(value)
        return bin_to_dec(value)

    @property
    def code(self):
        if self.is_ear:
            return None
        index, length = NON_EAR_STRUCTURE['code']
        value = self._bin_data_as_array[index:index + length]
        result = ''
        for v in split_array(value, 8, padding='0'):
            joined_v = ''.join(reversed(v))
            dec_v = bin_to_dec(joined_v)
            letter = chr(dec_v)
            result += letter
        return result.strip()

    @property
    def id(self):
        if self.is_ear or self.is_simple:
            return None
        index, length = NON_EAR_STRUCTURE['unique_id']
        value = self._bin_data_as_array[index:index + length][::-1]
        return bin_to_dec(''.join(value))

    @property
    def level(self):
        if self.is_ear or self.is_simple:
            return None
        return self._read_data(*NON_EAR_STRUCTURE['level'])

    @property
    def rarity(self):
        if self.is_ear or self.is_simple:
            return None
        return RARITIES.get(self._read_data(*NON_EAR_STRUCTURE['rarity']))

    @property
    def has_custom_graphic(self):
        if self.is_ear or self.is_simple:
            return None
        return self._read_data(*NON_EAR_STRUCTURE['has_custom_graphic']) > 0

    @property
    def has_class_spec_index(self):
        has_custom_graphic_index, has_custom_graphic_length = NON_EAR_STRUCTURE['has_custom_graphic']
        _, custom_graphic_length = NON_EAR_STRUCTURE['custom_graphic']

        result = has_custom_graphic_index + has_custom_graphic_length

        if self.has_custom_graphic:
            result += custom_graphic_length

        return result

    @property
    def has_class_spec(self):
        _, length = NON_EAR_STRUCTURE['has_class_spec']
        return self._read_data(self.has_class_spec_index, length) > 0

    @property
    def class_spec_index(self):
        _, has_class_spec_length = NON_EAR_STRUCTURE['has_class_spec']
        result = self.has_class_spec_index + has_class_spec_length

        return result

    @property
    def class_spec(self):
        if not self.has_class_spec:
            return None

        _, length = NON_EAR_STRUCTURE['class_spec']
        class_spec_data = self._read_data(self.class_spec_index, length)
        return class_spec_data

    @property
    def rarity_details(self):
        if self.is_ear or self.is_simple:
            return None

        result = {
            'rarity': self.rarity
        }
        details_index = self.class_spec_index

        if self.has_class_spec:
            _, class_spec_length = NON_EAR_STRUCTURE['class_spec']
            details_index += class_spec_length

        result['index'] = details_index

        if self.rarity in ['rare', 'crafted']:
            _, prefix_id_length = NON_EAR_STRUCTURE[
                'cr_pf_type_id'
            ]
            _, suffix_id_length = NON_EAR_STRUCTURE[
                'cr_sf_type_id'
            ]

            prefix_id_index = details_index
            bin_prefix_id = reversed(
                self._bin_data_as_array[prefix_id_index: prefix_id_index + prefix_id_length]
            )
            prefix_id = bin_to_dec(''.join(bin_prefix_id))
            result['prefix_id_index'] = prefix_id_index
            result['prefix_id'] = prefix_id

            suffix_id_index = prefix_id_index + prefix_id_length
            bin_suffix_id = reversed(self._bin_data_as_array[suffix_id_index: suffix_id_index + suffix_id_length])
            suffix_id = bin_to_dec(''.join(bin_suffix_id))
            result['suffix_id_index'] = suffix_id_index
            result['suffix_id'] = suffix_id

            affixes_index = suffix_id_index + suffix_id_length
            result['affixes_index'] = affixes_index

            affixes = []

            # there are total of 6 affixes
            current_aff_index = affixes_index
            aff_id_length = 11
            for i in range(6):
                aff_exist = self._bin_data_as_array[current_aff_index: current_aff_index + 1] == ['1']
                if aff_exist:
                    aff_id_index = current_aff_index + 1
                    bin_aff_id = reversed(
                        self._bin_data_as_array[aff_id_index: aff_id_index + aff_id_length]
                    )
                    aff_id = bin_to_dec(''.join(bin_aff_id))
                    affixes.append({
                        'id': aff_id,
                        'id_index': aff_id_index
                    })
                    current_aff_index += (aff_id_length + 1)
                else:
                    current_aff_index += 1
            result['affixes'] = affixes

            result['length'] = current_aff_index - details_index

        elif self.rarity == 'magic':
            _, pf_type_id_length = NON_EAR_STRUCTURE['magic_pf_type_id']
            _, sf_type_id_length = NON_EAR_STRUCTURE['magic_sf_type_id']

            prefix_id_index = details_index
            result['prefix_id_index'] = prefix_id_index
            bin_prefix_id = reversed(self._bin_data_as_array[
                                     prefix_id_index: prefix_id_index + pf_type_id_length])
            prefix_id = bin_to_dec(''.join(bin_prefix_id))
            result['prefix_id'] = prefix_id

            suffix_id_index = prefix_id_index + pf_type_id_length
            bin_suffix_id = reversed(self._bin_data_as_array[suffix_id_index: suffix_id_index + sf_type_id_length])
            suffix_id = bin_to_dec(''.join(bin_suffix_id))
            result['suffix_id_index'] = suffix_id_index
            result['suffix_id'] = suffix_id

            result['length'] = suffix_id_index + sf_type_id_length - details_index

        elif self.rarity == 'unique':
            _, quality_id_length = NON_EAR_STRUCTURE['unique_quality_id']
            bin_quality_id = reversed(
                self._bin_data_as_array[details_index: details_index + quality_id_length]
            )
            quality_id = bin_to_dec(''.join(bin_quality_id))
            result['quality_id'] = quality_id

            result['length'] = quality_id_length

        elif self.rarity == 'set':
            _, quality_id_length = NON_EAR_STRUCTURE['set_quality_id']
            bin_quality_id = reversed(
                self._bin_data_as_array[details_index: details_index + quality_id_length]
            )
            quality_id = bin_to_dec(''.join(bin_quality_id))
            result['quality_id'] = quality_id

            result['length'] = quality_id_length

        elif self.rarity == 'superior':
            _, quality_id_length = NON_EAR_STRUCTURE['superior_quality_id']
            bin_quality_id = self._bin_data_as_array[details_index: details_index + quality_id_length]
            quality_id = bin_to_dec(''.join(reversed(bin_quality_id)))
            result['quality_id'] = quality_id
            result['length'] = quality_id_length
        else:
            result['length'] = 0

        return result

    # index of modifier bit field for set items
    @property
    def set_mod_bit_field_index(self):
        total_socket_index = self.total_socket_index

        if self.is_socketed:
            _, total_socket_length = NON_EAR_STRUCTURE['total_sockets']
            return total_socket_index + total_socket_length

        return total_socket_index

    @property
    def start_mod_index(self):
        set_mod_bit_field_index = self.set_mod_bit_field_index

        if self.rarity == 'set':
            _, set_mod_bit_field_length = NON_EAR_STRUCTURE['set_mod_bit_field']
            return set_mod_bit_field_index + set_mod_bit_field_length

        return set_mod_bit_field_index

    @property
    def has_defense(self):
        if self.is_ear or self.is_simple:
            return False

        return self._base.is_armor

    @property
    def has_durability(self):
        if self.is_ear or self.is_simple:
            return False

        return self._base.is_armor or self._base.is_weapon

    @property
    def stackable(self):
        if self.is_ear or self.is_simple:
            return False

        return self._base.stackable

    @property
    def runeword_index(self):
        rarity_details = self.rarity_details
        result = rarity_details['index'] + rarity_details['length']

        if self.is_runeword:
            _, length = NON_EAR_STRUCTURE['runeword']
            result += length

        return result

    @property
    def runeword(self):
        if not self.is_runeword:
            return None

        index = self.runeword_index

        _, length = NON_EAR_STRUCTURE['runeword']

        result_as_bin = reversed(self._bin_data_as_array[index: index + length])

        result = list(result_as_bin)

        return result

    @property
    def defense_index(self):
        result = self.runeword_index

        # unknown_11 bit
        result += 1

        return result

    @property
    def max_durability_index(self):
        defense_index = self.defense_index
        if self.has_defense:
            _, defense_length = NON_EAR_STRUCTURE['defense_value']
            return defense_index + defense_length
        return defense_index

    @property
    def defense(self):
        if not self.has_defense:
            return None
        index = self.defense_index
        _, length = NON_EAR_STRUCTURE['defense_value']
        result_as_bin = reversed(self._bin_data_as_array[index: index + length])
        return bin_to_dec(''.join(result_as_bin)) + START_DEFENSE_VALUE

    @property
    def max_durability(self):
        if not self.has_durability:
            return None

        index = self.max_durability_index
        _, length = NON_EAR_STRUCTURE['max_durability']
        result_as_bin = list(reversed(self._bin_data_as_array[index: index + length]))
        return bin_to_dec(''.join(result_as_bin)) + START_MAX_DURABILITY_VALUE

    @property
    def current_durability_index(self):
        result = self.max_durability_index
        if self.has_durability:
            _, max_durability_length = NON_EAR_STRUCTURE['max_durability']
            result += max_durability_length

        return result

    @property
    def current_durability(self):
        if not self.max_durability:
            return None
        index = self.current_durability_index
        _, length = NON_EAR_STRUCTURE['current_durability']
        result_as_bin = reversed(self._bin_data_as_array[index: index + length])
        return bin_to_dec(
            ''.join(result_as_bin)
        ) + START_CURRENT_DURABILITY_VALUE

    @property
    def quantity_index(self):
        result = self.current_durability_index
        if self.max_durability:
            _, current_durability_length = NON_EAR_STRUCTURE['current_durability']
            result += current_durability_length
        return result

    @property
    def total_socket_index(self):
        quantity_index = self.quantity_index
        if self.stackable:
            _, quantity_length = NON_EAR_STRUCTURE['quantity']
            return quantity_index + quantity_length
        return quantity_index

    @property
    def updated_data(self):
        # strip the data to the start mod index
        if self.is_ear or self.is_simple:
            bin_data_as_array = self._bin_data_as_array
        else:
            bin_data_as_array = self._bin_data_as_array[:self.start_mod_index]

            # update data from mods
            for mod in self.mods:
                bin_data_as_array.extend(list(mod.data))

            # add mod ending section
            bin_data_as_array.extend(ITEM_FOOTER)

            if self.rw_mods:
                for mod in self.rw_mods:
                    bin_data_as_array.extend(list(mod.data))
                # add mod ending section
                bin_data_as_array.extend(ITEM_FOOTER)

        hex_data = bin_to_hex(
            ''.join(reversed(bin_data_as_array))
        )
        result = reversed(
            make_byte_array_from_hex(hex_data)
        )

        return result

    def save(self, file_path):
        with open(file_path, 'wb') as file_ref:
            file_ref.write(
                bytes.fromhex(''.join(self.updated_data))
            )

    def update_id(self, value: int):
        if self.is_ear or self.is_simple:
            return
        id_index, id_length = NON_EAR_STRUCTURE['unique_id']
        value_as_bin = dec_to_bin(value, length=id_length)
        self._bin_data_as_array[id_index: id_index + id_length] = list(
            value_as_bin[::-1]
        )

    def clear_mods(self,
                   include_affixes: bool = False,
                   include_class_spec: bool = False):
        if self.is_ear:
            raise Error(
                'UnsupportedAction',
                'Cannot clear mods for ear items'
            )

        if self.is_simple:
            raise Error(
                'UnsupportedAction',
                'Cannot clear mods for simple items'
            )

        if self.is_runeword:
            raise Error(
                'UnsupportedAction',
                'Cannot clear mods for runeword items'
            )

        for mod in self.mods:
            if mod.base.code in AFFIX_MOD_CODES:
                if not include_affixes:
                    continue

            self._mods.pop(mod.id)

    def change_max_durability(self, value: int):
        if not self.has_durability:
            raise Error('UnsupportedAction',
                        'Item does not have durability')

        index = self.max_durability_index
        _, length = NON_EAR_STRUCTURE['max_durability']

        bin_value = dec_to_bin(value - START_MAX_DURABILITY_VALUE, length=length)

        self.edit(index, list(reversed(bin_value)))

    def change_position(self,
                        storage_code: int,
                        location_code: int,
                        storage_x: int = None,
                        storage_y: int = None):

        if storage_code not in STORAGES:
            raise Error('UnsupportedStorage')

        if location_code not in LOCATIONS:
            raise Error('UnsupportedLocation')

        if storage_x is None:
            storage_x = 0
        if storage_y is None:
            storage_y = 0

        # update storage
        storage_index, storage_length = BASE_STRUCTURE['storage']
        storage_code_as_bin = dec_to_bin(storage_code, length=storage_length)[::-1]
        self._bin_data_as_array[storage_index: storage_index + storage_length] = list(storage_code_as_bin)

        # update location
        location_index, location_length = BASE_STRUCTURE['location']
        location_code_as_bin = dec_to_bin(location_code, length=location_length)[::-1]
        self._bin_data_as_array[location_index: location_index + location_length] = list(location_code_as_bin)

        # update location coordinate
        storage_x_index, storage_x_length = BASE_STRUCTURE['storage_x']
        storage_y_index, storage_y_length = BASE_STRUCTURE['storage_y']
        storage_x_as_bin = dec_to_bin(storage_x, length=storage_x_length)[::-1]
        storage_y_as_bin = dec_to_bin(storage_y, length=storage_y_length)[::-1]
        self._bin_data_as_array[storage_x_index: storage_x_index + storage_x_length] = list(storage_x_as_bin)
        self._bin_data_as_array[storage_y_index: storage_y_index + storage_y_length] = list(storage_y_as_bin)

    def edit(self, index: int, data: list):
        length = len(data)
        before = ''.join(self._bin_data_as_array[index - length:])
        self._bin_data_as_array[index: index + length] = data
        after = (' ' * length) + ''.join(self._bin_data_as_array[index:index + length])

        print('===== changes =====')
        print(before)
        print(after)

    def insert(self, index, data: list):
        length = len(data)
        before = '{}{}{}'.format(
            ''.join(self._bin_data_as_array[index - length:index]),
            (' ' * length),
            ''.join(self._bin_data_as_array[index: index + length])
        )
        for bit in reversed(data):
            self._bin_data_as_array.insert(index, bit)

        after = '{}{}'.format(
            ' ' * length,
            ''.join(data),
        )

        print('===== changes =====')
        print(before)
        print(after)

    def delete_data(self, index: int, length: int):
        before = ''.join(self._bin_data_as_array[index - length: index + length])
        after = '{}{}{}'.format(
            ''.join(self._bin_data_as_array[index - length:index]),
            ' ' * length,
            ''.join(self._bin_data_as_array[index + length:])
        )
        del self._bin_data_as_array[index: index + length]
        print('===== changes =====')
        print(before)
        print(after)

    def change_level(self, value: int):
        if self.is_ear or self.is_simple:
            return

        level_index, level_length = NON_EAR_STRUCTURE['level']
        bin_value = dec_to_bin(value, length=level_length)
        self.edit(level_index, list(reversed(bin_value)))

    def add_mod(self,
                mod_code: str,
                values: dict = None,
                runeword: bool = False):
        if self.is_ear or self.is_simple:
            raise Error(code='UnsupportedAction',
                        message='Cannot add mod of simple or ear item.')

        base_mod = self.find_base_mod_by_code(code=mod_code)
        if not base_mod:
            raise Error(
                'UnsupportedModCode',
                f'Unsupported mod code: {mod_code}'
            )

        if runeword and not self.is_runeword:
            raise Error(
                'InvalidParams',
                'This item is not runeword'
            )

        init_mod_data = dec_to_bin(base_mod.id, length=MOD_ID_LENGTH)[::-1]
        init_mod_data += ('0' * base_mod.length)
        mod = Modifier(data=init_mod_data,
                       runeword=runeword,
                       base=base_mod)
        mod.update(values=values)

        self._mods[mod.id] = mod

        return mod

    def edit_mod(self,
                 mod_id: str,
                 values: dict = None):
        if self.is_ear or self.is_simple:
            raise Error(code='UnsupportedAction',
                        message='Cannot add mod of simple or ear item.')

        mod = self._mods.pop(mod_id, None)
        if not mod:
            raise Error('ModNotFoundInItem', message=f'Mod not found in item: {mod_id}')

        mod.update(values=values)

        # update mod id
        self._mods[mod.id] = mod

        return mod

    def delete_mod(self, mod_id: str):
        if self.is_ear or self.is_simple:
            raise Error(code='UnsupportedAction',
                        message='Cannot delete mod from simple or ear item.')

        mod = self._mods.get(mod_id)
        if not mod:
            raise Error('ModNotFoundInItem', message=f'Mod not found in item: {mod_id}')

        return self._mods.pop(mod_id, None)

    def change_rarity(self, rarity_id: int, **kwargs):
        if self.is_ear or self.is_simple:
            raise Error('UnsupportedAction',
                        'Cannot change rarity of simple or ear item')
        rarity = RARITIES[rarity_id]

        current_rarity_details = self.rarity_details

        detail_index = current_rarity_details['index']

        new_detail_data = []

        if rarity == 'unique':
            _, quality_id_length = NON_EAR_STRUCTURE['unique_quality_id']
            quality_id = kwargs.get('quality_id') or 0
            bin_quality_id = dec_to_bin(value=quality_id,
                                        length=quality_id_length)
            new_detail_data.extend(reversed(bin_quality_id))

        elif rarity == 'magic':
            _, prefix_id_length = NON_EAR_STRUCTURE['magic_pf_type_id']
            _, suffix_id_length = NON_EAR_STRUCTURE['magic_sf_type_id']

            prefix_id = kwargs.get('prefix_id') or 0
            suffix_id = kwargs.get('suffix_id') or 0
            bin_prefix_id = dec_to_bin(
                value=prefix_id,
                length=prefix_id_length
            )
            bin_suffix_id = dec_to_bin(
                value=suffix_id,
                length=suffix_id_length
            )
            new_detail_data.extend(reversed(bin_prefix_id))
            new_detail_data.extend(reversed(bin_suffix_id))

        elif rarity in ['rare', 'crafted']:
            _, prefix_id_length = NON_EAR_STRUCTURE['cr_pf_type_id']
            _, suffix_id_length = NON_EAR_STRUCTURE['cr_sf_type_id']
            _, affix_lengths = NON_EAR_STRUCTURE['cr_affixes']
            affix_min_length, affix_max_length = affix_lengths

            prefix_id = kwargs.get('prefix_id') or 0
            suffix_id = kwargs.get('suffix_id') or 0
            bin_prefix_id = dec_to_bin(
                value=prefix_id,
                length=prefix_id_length
            )
            bin_suffix_id = dec_to_bin(
                value=suffix_id,
                length=suffix_id_length
            )
            bin_affixes = dec_to_bin(
                value=0,
                length=affix_min_length
            )
            new_detail_data.extend(reversed(bin_prefix_id))
            new_detail_data.extend(reversed(bin_suffix_id))
            new_detail_data.extend(reversed(bin_affixes))

        else:
            raise Error('UnsupportedRarity',
                        'Cannot change to this rarity')

        # delete current rarity details
        self.delete_data(
            index=current_rarity_details['index'],
            length=current_rarity_details['length']
        )

        # insert new detail data
        self.insert(detail_index, new_detail_data)

        # update rarity
        rarity_index, rarity_length = NON_EAR_STRUCTURE['rarity']
        bin_rarity = dec_to_bin(value=rarity_id, length=rarity_length)
        self.edit(rarity_index, list(reversed(bin_rarity)))

    @property
    def size(self):
        return self._base.width, self._base.height

    @property
    def rect(self) -> dict:
        width, height = self.size
        return dict(
            storage_x=self.storage_x,
            storage_y=self.storage_y,
            width=width,
            height=height,
            points=[
                (self.storage_x, self.storage_y),
                (self.storage_x + width - 1, self.storage_y),
                (self.storage_x, self.storage_y + height - 1),
                (self.storage_x + width - 1, self.storage_y + height - 1),
            ]
        )

    def change_code(self, value: str):
        if self.is_ear:
            raise Error('UnsupportedAction',
                        'Cannot change code of ear items')

        new_data = []

        index, length = NON_EAR_STRUCTURE['code']

        max_char = length / 8

        if len(value) > max_char:
            raise Error(
                'InvalidParams',
                f'Max length of value is: {max_char}'
            )
        if len(value) < max_char:
            value += (' ' * int(max_char - len(value)))

        for char in value:
            char_as_bin = dec_to_bin(
                value=ord(char),
                length=8
            )
            new_data.extend(reversed(char_as_bin))

        self.edit(index, new_data)

    def maximize_affixes(self):
        max_values = dict(value=3)

        for mod_code in AFFIX_MOD_CODES:
            affix_mod = None

            for mod in self.mods:
                if mod.base.code == mod_code:
                    affix_mod = mod
                    break

            if affix_mod:
                self.edit_mod(mod_id=affix_mod.id,
                              values=max_values)
            else:
                self.add_mod(
                    mod_code=mod_code,
                    values=max_values
                )

        return self

    def clone(self):
        result = copy.deepcopy(self)
        result.update_id(int(time.time()))
        return result

    def print_all_mods(self):
        print('=' * 20, 'MODS', '=' * 20)
        for mod in self.mods:
            print(mod.id, mod.base.id, mod.base.code, mod.factor_values.model_dump_json(exclude_none=True))

        if self.is_runeword:
            print('=' * 20, 'RW MODS', '=' * 20)
            for mod in self.rw_mods:
                print(mod.id, mod.base.id, mod.base.code, mod.factor_values.model_dump_json(exclude_none=True))

    def print_data(self, offset: int = None, length: int = None):
        if not offset:
            offset = 0
        if length:
            data = self._bin_data_as_array[offset:offset + length]
        else:
            data = self._bin_data_as_array[offset:]

        print(''.join(data))
