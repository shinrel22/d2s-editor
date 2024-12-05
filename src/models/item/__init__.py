import copy
import time
from math import ceil

from src.bases.errors import Error
from src.bases.models import IngameModel, BaseModel
from src.common.constants.items import (
    NON_EAR_STRUCTURE, RARITIES,
    BASE_STRUCTURE, LOCATIONS, STORAGES, EQUIPPED_LOCATIONS, ITEM_FOOTER,
    START_DEFENSE_VALUE, START_MAX_DURABILITY_VALUE,
    START_CURRENT_DURABILITY_VALUE, MOD_ID_LENGTH,
    END_OF_MOD_SECTION,
    ADDING_DMG_WITH_DURATION_MOD_CODES,
    ADDING_DMG_MOD_CODES, AFFIX_MOD_CODES,
    ADDING_OSKILL_MOD_CODE, REANIMATE_MOD_CODE,
    ADDING_CLASS_SKILL_LEVEL_MOD_CODE, SKILL_ON_EVENT_MOD_CODES,
    DESC_TEXT_MOD_CODES, CUBE_UPGRADE_MOD_CODES,
    MO_COUNT_MOD_CODE, TROPHY_COUNTER_MOD_CODE, TOTAL_SOCKETS,
    ITEM_CORRUPTED_MOD_CODE,
    ITEM_UPGRADED_MOD_CODE,
    SHRINE_BLESSED_MOD_CODE
)
from src.common.data import ITEM_BASE_STATS, ITEM_TYPES, ITEM_BASE_MODS, BASE_ITEMS, SKILLS
from src.common.utils import (
    bin_to_hex, bin_to_dec, split_array,
    dec_to_bin, make_byte_array_from_hex, convert_byte_array_to_bit,
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
    is_2h_weapon: bool = False
    is_body_armor: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.is_armor = self.has_related_types(['armo'])
        self.is_weapon = self.has_related_types(['weap'])
        self.is_2h_weapon = self.has_related_types([
            '2hax',
            '2hsd',
            'anx2',
            'an2x',
            'el2x',
            'nagi',
        ])
        self.is_body_armor = self.has_related_types([
            'tors',
            'atrs',
        ])

    @staticmethod
    def find_item_type(code: str) -> ItemType | None:
        if code not in ITEM_TYPES:
            return None
        return ItemType(**ITEM_TYPES[code])

    def has_related_types(self, target_type_codes: list[str]) -> bool:
        for target_type_code in target_type_codes:
            if self.has_related_type(target_type_code):
                return True
        return False

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


class BaseModifierProperty(BaseModel):
    code: str
    length: int
    min_value: float | int
    conversion_rate: float | int = 1.0


class BaseModifier(BaseModel):
    id: int
    code: str
    length: int
    stat_code: str
    min_value: int | float = 0
    conversion_rate: int | float = 1


class ModPropertyValues(BaseModel):
    value: float | int | None = None
    monster_id: int | None = None
    mys_orb_id: int | None = None
    text_id: int | None = None
    class_id: int | None = None
    skill_id: int | None = None
    skill_name: str | None = None
    skill_level: int | None = None
    chance: int | None = None
    min_dmg: float | int | None = None
    max_dmg: float | int | None = None
    duration: int | None = None
    unknown: int | None = None


class Modifier(IngameModel):
    base: BaseModifier
    runeword: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def id(self):

        result = self.base.code

        property_values = self.property_values

        if self.base.code in [*SKILL_ON_EVENT_MOD_CODES, ADDING_OSKILL_MOD_CODE]:
            result += f'$skill-{property_values.skill_id}'

        elif self.base.code in [ADDING_CLASS_SKILL_LEVEL_MOD_CODE]:
            result += f'$class-{property_values.class_id}'

        elif self.base.code in [REANIMATE_MOD_CODE]:
            result += f'$monster-{property_values.monster_id}'

        elif self.base.code in DESC_TEXT_MOD_CODES:
            result += f'$text-{property_values.text_id}'

        elif self.base.code in [MO_COUNT_MOD_CODE]:
            result += f'$mo-{property_values.mys_orb_id}-{property_values.unknown}'

        elif self.base.code in ['special_syn1', 'special_syn2']:
            result += f'${property_values.value}'

        if self.runeword:
            result += '|rw'

        return result

    @property
    def property_values(self) -> ModPropertyValues:
        result = ModPropertyValues()
        start_index = MOD_ID_LENGTH

        for p in self.init_properties(self.base):
            prop_code_data_type_info = result.__fields__.get(p.code)
            if prop_code_data_type_info is None:
                raise Error(
                    'PropCodeNotFound',
                    f'Property code not found in ModPropertyValues: {p.code}'
                )

            prop_data = self.data[start_index:start_index + p.length]
            prop_value = (bin_to_dec(prop_data[::-1]) + p.min_value) * p.conversion_rate

            if not isinstance(prop_value, prop_code_data_type_info.annotation):
                prop_value = int(prop_value)

            setattr(result, p.code, prop_value)
            start_index += p.length

        if self.base.code in [
            *SKILL_ON_EVENT_MOD_CODES,
            ADDING_OSKILL_MOD_CODE
        ]:
            skill_id = result.skill_id
            skill = SKILLS.get(str(skill_id))
            if skill:
                result.skill_name = skill.get('name')

        return result

    def update(self, values: dict = None):
        if values is None:
            values = dict()

        prop_data = []

        for p in self.init_properties(self.base):

            min_value = p.min_value
            max_value = bin_to_dec('1' * p.length)

            value = values.get(p.code)

            if value is not None:
                value = value / p.conversion_rate
            else:
                value = max_value

            if value < min_value:
                value = min_value
            else:
                value = min(value - min_value, max_value)

            value = ceil(value)

            prop_data.extend(reversed(dec_to_bin(value, length=p.length)))

        data_as_array = list(reversed(dec_to_bin(self.base.id, length=MOD_ID_LENGTH)))
        data_as_array.extend(prop_data)

        self.data = ''.join(data_as_array)

    @staticmethod
    def init_properties(base_mod: BaseModifier) -> list[BaseModifierProperty]:
        default_property = BaseModifierProperty(
            code='value',
            min_value=base_mod.min_value,
            conversion_rate=base_mod.conversion_rate,
            length=base_mod.length
        )
        if base_mod.code in [
            ADDING_CLASS_SKILL_LEVEL_MOD_CODE
        ]:
            result = [
                BaseModifierProperty(length=3, min_value=0, code='class_id'),
                BaseModifierProperty(length=4, min_value=0, code='value'),
            ]
        elif base_mod.code in [
            ADDING_OSKILL_MOD_CODE
        ]:
            result = [
                BaseModifierProperty(length=12, min_value=0, code='skill_id'),
                BaseModifierProperty(length=7, min_value=-1, code='skill_level'),
            ]
        elif base_mod.code in [
            REANIMATE_MOD_CODE
        ]:
            result = [
                BaseModifierProperty(length=12, min_value=0, code='monster_id'),
                BaseModifierProperty(length=7, min_value=0, code='chance', conversion_rate=1),
            ]

        elif base_mod.code in SKILL_ON_EVENT_MOD_CODES:
            if base_mod.length == 25:
                result = [
                    BaseModifierProperty(length=6, min_value=0, code='skill_level'),
                    BaseModifierProperty(length=12, min_value=0, code='skill_id'),
                    BaseModifierProperty(length=7, min_value=0, code='chance', conversion_rate=2),
                ]
            else:
                result = [
                    BaseModifierProperty(length=6, min_value=0, code='skill_level'),
                    BaseModifierProperty(length=11, min_value=0, code='skill_id'),
                    BaseModifierProperty(length=7, min_value=0, code='chance', conversion_rate=1),
                ]

        elif base_mod.code in ADDING_DMG_MOD_CODES:
            result = [
                default_property
            ]

            related_dmg_base_mod = Item.find_base_mod_by_id(base_mod.id + 1)
            related_dmg_base_mod_prop = BaseModifierProperty(
                length=related_dmg_base_mod.length,
                code='max_dmg',
                min_value=related_dmg_base_mod.min_value,
                conversion_rate=related_dmg_base_mod.conversion_rate,
            )
            if base_mod.code == 'item_maxdamage_percent':
                related_dmg_base_mod_prop.code = 'min_dmg'

            result.append(related_dmg_base_mod_prop)

            if base_mod.code in ADDING_DMG_WITH_DURATION_MOD_CODES:
                adding_dmg_duration_base_mod = Item.find_base_mod_by_id(base_mod.id + 2)
                adding_dmg_duration_base_mod_prop = BaseModifierProperty(
                    length=adding_dmg_duration_base_mod.length,
                    code='duration',
                    min_value=related_dmg_base_mod.min_value,
                    conversion_rate=adding_dmg_duration_base_mod.conversion_rate
                )
                result.append(adding_dmg_duration_base_mod_prop)

        elif base_mod.code in DESC_TEXT_MOD_CODES:
            result = [
                BaseModifierProperty(length=base_mod.length, min_value=0, code='text_id'),
            ]

        elif base_mod.code in [MO_COUNT_MOD_CODE]:
            result = [
                BaseModifierProperty(length=8, min_value=0, code='mys_orb_id'),
                BaseModifierProperty(length=10, min_value=0, code='unknown'),
            ]

        else:
            result = [default_property]

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
        # reverse because little endian
        self._bin_data_as_array = list(reversed(
            convert_byte_array_to_bit(
                data=list(reversed(self._hex_data_as_byte_array))
            )
        ))
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
                    Modifier.init_properties(item_base_mod)
                ))
                next_mod_index = mod_data_index + mod_data_length

                mod_data_as_bin_array = total_mod_data[start_index: next_mod_index]
                mod_data = ''.join(mod_data_as_bin_array)
                mod = Modifier(data=mod_data,
                               runeword=rw_loading,
                               base=item_base_mod)

                if mod.id in mods:
                    raise Error(
                        'DuplicateMod',
                        message=f'Duplicate mod: {mod.id} - {mod.property_values.model_dump_json(exclude_none=True)}'
                    )

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
        if self.is_ear or self.is_simple:
            return None
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
    def quantity(self):
        if self.is_ear or self.is_simple:
            return None
        _, length = NON_EAR_STRUCTURE['quantity']
        result_as_bin = reversed(self._bin_data_as_array[self.quantity_index: self.quantity_index + length])
        return bin_to_dec(
            ''.join(result_as_bin)
        )

    @property
    def total_socket_index(self):
        quantity_index = self.quantity_index
        if self.stackable:
            _, quantity_length = NON_EAR_STRUCTURE['quantity']
            return quantity_index + quantity_length
        return quantity_index

    @property
    def total_sockets(self):
        if self.is_ear or self.is_simple:
            return None

        if not self.is_socketed:
            return 0

        index = self.total_socket_index

        _, length = NON_EAR_STRUCTURE['total_sockets']
        result_as_bin = reversed(self._bin_data_as_array[index: index + length])
        return bin_to_dec(
            ''.join(result_as_bin)
        )

    def maximize_sockets(self):
        if self.is_ear or self.is_simple:
            raise Error(
                'InvalidItem',
                message='Cannot maximize sockets for this kind of item'
            )

        # set flag
        if not self.is_socketed:
            flag_index, flag_length = BASE_STRUCTURE['is_socketed']
            flag_data = '1' * flag_length
            self.edit(flag_index, list(flag_data))

        _, length = NON_EAR_STRUCTURE['total_sockets']
        index = self.total_socket_index
        width, height = self.size

        total_sockets = min(width * height, TOTAL_SOCKETS)
        data_as_bin = dec_to_bin(value=total_sockets, length=length)
        self.edit(index, list(reversed(data_as_bin)))

        return self

    @property
    def updated_data(self) -> list[str]:
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

        return list(result)

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
                   include_affix_count: bool = False,
                   include_cube_upgrades: bool = False,
                   include_desc: bool = False,
                   include_trophy_counter: bool = False,
                   include_weapon_count: bool = False,
                   ):
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
            # some desc mods,
            # they only show info, no effects
            if mod.base.code in DESC_TEXT_MOD_CODES:
                if not include_desc:
                    continue

            # cube upgrade mods
            if mod.base.code in CUBE_UPGRADE_MOD_CODES:
                if not include_cube_upgrades:
                    continue

            if mod.base.code in [TROPHY_COUNTER_MOD_CODE]:
                if not include_trophy_counter:
                    continue

            if mod.base.code in AFFIX_MOD_CODES:
                if not include_affix_count:
                    continue

            if mod.base.code in ['weapon_count']:
                if not include_weapon_count:
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
                        storage_id: int,
                        location_id: int,
                        storage_x: int = None,
                        storage_y: int = None):

        if storage_id not in STORAGES:
            raise Error('UnsupportedStorage')

        if location_id not in LOCATIONS:
            raise Error('UnsupportedLocation')

        if storage_x is None:
            storage_x = 0
        if storage_y is None:
            storage_y = 0

        # update storage
        storage_index, storage_length = BASE_STRUCTURE['storage']
        storage_code_as_bin = dec_to_bin(storage_id, length=storage_length)[::-1]
        self._bin_data_as_array[storage_index: storage_index + storage_length] = list(storage_code_as_bin)

        # update location
        location_index, location_length = BASE_STRUCTURE['location']
        location_code_as_bin = dec_to_bin(location_id, length=location_length)[::-1]
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

    @property
    def is_ethereal(self):
        index, length = BASE_STRUCTURE['is_ethereal']
        value = self._bin_data_as_array[index]
        return value == '1'

    def set_ethereal(self, value: bool):
        index, length = BASE_STRUCTURE['is_ethereal']

        value_as_bin = '1' if value else '0'

        self.edit(index, [value_as_bin])

        return self

    def shrine_bless(self, shrine_name: str):
        shrine_mod_mappings = {
            # shrine names
            'Eerie': {
                # 1h, armors (except body)
                'minor': {
                    # mod, min-max value
                    'enr_factor': [dict(value=20), dict(value=30)],  # spell focus
                    'energy': [dict(value=4), dict(value=20)],
                    'item_energy_percent': [dict(value=4), dict(value=5)]
                },
                # 2h, body armors
                'greater': {
                    'enr_factor': [dict(value=40), dict(value=60)],
                    'energy': [dict(value=6), dict(value=28)],
                    'item_energy_percent': [dict(value=6), dict(value=12)]
                },
            },
            'Abandoned': {
                # 1h, armors (except body)
                'minor': {
                    # mod, min-max value
                    'item_tohit_percent': [dict(value=24), dict(value=120)],
                    'dexterity': [dict(value=4), dict(value=20)],
                    'item_dexterity_percent': [dict(value=4), dict(value=5)]
                },
                # 2h, body armors
                'greater': {
                    'item_tohit_percent': [dict(value=36), dict(value=170)],
                    'dexterity': [dict(value=6), dict(value=28)],
                    'item_dexterity_percent': [dict(value=6), dict(value=12)]
                },
            },
            'Shimmering': {
                # 1h, armors (except body)
                'minor': {
                    # mod, min-max value
                    'passive_pois_mastery': [dict(value=2), dict(value=8)],  # spell focus
                    'passive_pois_pierce': [dict(value=3), dict(value=5)],
                },
                # 2h, body armors
                'greater': {
                    'passive_pois_mastery': [dict(value=2), dict(value=15)],
                    'passive_pois_pierce': [dict(value=5), dict(value=10)],
                },
            },
        }

        if self.is_ear or self.is_simple:
            raise Error(
                'InvalidItem',
                'Item cannot be shrine blessed'
            )

        if self.rarity not in ['rare', 'crafted']:
            raise Error(
                'InvalidRarity',
                'Invalid Rarity'
            )

        if SHRINE_BLESSED_MOD_CODE in self._mods:
            raise Error(
                'AlreadyBlessed',
                'Item is already blessed'
            )

        if shrine_name not in shrine_mod_mappings:
            raise Error(
                'UnsupportedShrine',
                f'Unsupported shrine: {shrine_name}',
            )

        mapping = shrine_mod_mappings[shrine_name]

        bless_mods = mapping['minor']
        if self.base.is_body_armor or self.base.is_2h_weapon:
            bless_mods = mapping['greater']

        for mod_code, bless_values in bless_mods.items():
            bless_min_value, bless_max_value = bless_values
            mod = self._mods.get(mod_code)
            if mod:
                mod_values = mod.property_values.model_dump(exclude_none=True)
                for k, v in bless_max_value.items():
                    if k in mod_values:
                        mod_values[k] += v
                mod.update(values=mod_values)
            else:
                self.add_mod(mod_code=mod_code, values=bless_max_value)
        self.add_mod(mod_code=SHRINE_BLESSED_MOD_CODE)

    def upgrade(self, formular: str):
        formular_mappings = {
            # formular
            'LuckyBonus': {
                # item type
                'weapon': {
                    # mods
                    'item_maxdamage_percent': dict(value=20, min_dmg=20),  # Enhance Damage
                    'item_tohit_percent': dict(value=100),  # ATK rating
                },
                'elm_weapon': {
                    'item_fasterattackrate': dict(value=20),  # ATK speed
                    'item_tohit_percent': dict(value=100),  # ATK rating
                },
                'armor': {
                    'damageresist': dict(value=1),  # phys resist
                    'item_armor_percent': dict(value=20),  # enhance def
                },
                'amulet': {
                    'item_allskills': dict(value=1),  # add all skill level
                },
                'ring': {
                    # 5% spell dmg
                    'passive_cold_mastery': dict(value=5),
                    'passive_fire_mastery': dict(value=5),
                    'passive_ltng_mastery': dict(value=5),
                    'passive_pois_mastery': dict(value=5),
                    'passive_pm_mastery': dict(value=5),
                },
                'quiver': {
                    # 5% to all attrs
                    'item_strength_percent': dict(value=5),
                    'item_dexterity_percent': dict(value=5),
                    'item_vitality_percent': dict(value=5),
                    'item_energy_percent': dict(value=5),
                },
                'jewel': {
                    # +2 to all attrs
                    'strength': dict(value=2),
                    'dexterity': dict(value=2),
                    'vitality': dict(value=2),
                    'energy': dict(value=2),
                }
            },
            'LotteryBonus': {
                # item type
                'weapon': {
                    # mods
                    'item_ignoretargetac': dict(value=1),  # Ignore Target's Defense
                },
                'armor': {
                    'item_maxhp_percent': dict(value=2),
                },
                'amulet': {
                    'magicresist': dict(value=5),
                },
                'ring': {
                    'item_allskills': dict(value=1),  # add all skill level
                },
                'quiver': {
                    'item_magicbonus': dict(value=50),
                },
                'jewel': {
                    'poisonresist': dict(value=10),
                    'coldresist': dict(value=10),
                    'lightresist': dict(value=10),
                    'fireresist': dict(value=10),
                }
            },
        }

        if self.is_ear or self.is_simple:
            raise Error(
                'InvalidItem',
                'Item cannot be upgraded'
            )

        if ITEM_UPGRADED_MOD_CODE in self._mods:
            raise Error(
                'AlreadyUpgraded',
                'Item is already upgraded'
            )

        if formular not in formular_mappings:
            raise Error(
                'UnsupportedFormular',
                f'Unsupported formular: {formular}',
            )

        mapping = formular_mappings[formular]

        if formular == 'LuckyBonus':
            if self.rarity in ['superior', 'normal']:
                raise Error(
                    'InvalidRarity',
                    'Invalid Rarity'
                )

            if self.base.is_weapon:
                if self.base.has_related_types([
                    'elex'
                ]):
                    upgrading_mods = mapping['elm_weapon']
                else:
                    upgrading_mods = mapping['weapon']

            elif self.base.is_armor:
                upgrading_mods = mapping['armor']

            elif self.base.has_related_types([
                'amul'
            ]):
                upgrading_mods = mapping['amulet']
            elif self.base.has_related_types([
                'ring'
            ]):
                upgrading_mods = mapping['ring']
            elif self.base.has_related_types([
                'bowq',
                'qaqv',
                'xboq',
                'qcqv',
            ]):
                upgrading_mods = mapping['quiver']
            elif self.base.has_related_types([
                'jewl'
            ]):
                upgrading_mods = mapping['jewel']
            else:
                raise Error(
                    'InvalidItemType',
                    f'Invalid item types: {self.base.type_codes}'
                )
        elif formular == 'LotteryBonus':
            if self.rarity not in ['unique', 'set']:
                raise Error(
                    'InvalidRarity',
                    'Invalid Rarity'
                )

            if self.base.is_weapon:
                upgrading_mods = mapping['weapon']

            elif self.base.is_armor:
                upgrading_mods = mapping['armor']

            elif self.base.has_related_types([
                'amul'
            ]):
                upgrading_mods = mapping['amulet']
            elif self.base.has_related_types([
                'ring'
            ]):
                upgrading_mods = mapping['ring']
            elif self.base.has_related_types([
                'bowq',
                'qaqv',
                'xboq',
                'qcqv',
            ]):
                upgrading_mods = mapping['quiver']
            elif self.base.has_related_types([
                'jewl'
            ]):
                upgrading_mods = mapping['jewel']
            else:
                raise Error(
                    'InvalidItemType',
                    f'Invalid item types: {self.base.type_codes}'
                )

        else:
            raise Error(
                'UnsupportedFormular',
                f'Unsupported formular: {formular}'
            )

        for mod_code, upgrading_values in upgrading_mods.items():
            mod = self._mods.get(mod_code)
            if mod:
                mod_values = mod.property_values.model_dump(exclude_none=True)
                for k, v in upgrading_values.items():
                    if k in mod_values:
                        mod_values[k] += v
                mod.update(values=mod_values)
            else:
                self.add_mod(mod_code=mod_code, values=upgrading_values)
        self.add_mod(mod_code=ITEM_UPGRADED_MOD_CODE)

    def corrupt(self, mod_data: list[dict]):
        if self.is_ear or self.is_simple:
            raise Error(
                'InvalidItem',
                'Item cannot be corrupted'
            )

        if self.rarity in ['normal']:
            raise Error(
                'InvalidRarity',
                'Invalid Rarity'
            )

        if ITEM_CORRUPTED_MOD_CODE in self._mods:
            raise Error(
                'AlreadyCorrupted',
                'Item is already corrupted'
            )

        for i in mod_data:
            mod_code = i['mod_code']
            corrupting_values = i['values']
            mod = self._mods.get(mod_code)
            if mod:
                mod_values = mod.property_values.model_dump(exclude_none=True)
                for k, v in corrupting_values.items():
                    if k in mod_values:
                        mod_values[k] += v
                mod.update(values=mod_values)
            else:
                self.add_mod(mod_code=mod_code, values=corrupting_values)
        self.add_mod(mod_code=ITEM_CORRUPTED_MOD_CODE)

    def clone(self):
        result = copy.deepcopy(self)
        result.update_id(int(time.time()))
        return result

    def print_all_mods(self):
        print('=' * 20, 'MODS', '=' * 20)
        for mod in self.mods:
            print(mod.base.id, mod.id, mod.property_values.model_dump_json(exclude_none=True))

        if self.is_runeword:
            print('=' * 20, 'RW MODS', '=' * 20)
            for mod in self.rw_mods:
                print(mod.base.id, mod.id, mod.property_values.model_dump_json(exclude_none=True))

    def print_data(self, offset: int = None, length: int = None):
        if not offset:
            offset = 0
        if length:
            data = self._bin_data_as_array[offset:offset + length]
        else:
            data = self._bin_data_as_array[offset:]

        print(''.join(data))
