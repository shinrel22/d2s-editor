STRUCTURE = {
    'signature': (0, 4),
    'version': (4, 4),
    'file_size': (8, 4),
    'checksum': (12, 4),
    'active_weapon': (16, 4),
    'character_name': (20, 16),
    'character_status': (36, 1),
    'character_progression': (37, 1),
    'unknown_1': (38, 2),
    'character_class': (40, 1),
    'unknown_2': (41, 2),
    'character_level': (43, 1),
    'unknown_3': (44, 4),
    'time': (48, 4),
    'unknown_4': (52, 4),
    'hotkeys': (56, 64),
    'left_mouse': (120, 4),
    'right_mouse': (124, 4),
    'left_mouse_wp_switch': (128, 4),
    'right_mouse_wp_switch': (132, 4),
    'character_menu_appearance': (136, 32),
    'difficulty': (168, 3),
    'map': (171, 4),
    'unknown_5': (175, 2),
    'mercenary_dead': (177, 2),
    'mercenary_seed': (179, 4),
    'mercenary_name_id': (183, 2),
    'mercenary_type': (185, 2),
    'mercenary_exp': (187, 4),
    'unknown_6': (191, 144),
    'quest': (335, 298),
    'waypoint': (633, 81),
    'npc': (714, 51),
}

FOOTER = ['6b', '66', '00']
ITEM_LIST_HEADER = ['4a', '4d']
ITEM_LIST_FOOTER = ['4a', '4d', '00', '00', '6a', '66']
MERC_ITEM_LIST_HEADER = ['4a', '4d']
ITEM_HEADER = ['4a', '4d']

CHAR_CLASSES = {
    0: 'amazon',
    1: 'sorceress',
    2: 'necromancer',
    3: 'paladin',
    4: 'barbarian',
    5: 'druid',
    6: 'assassin',
}


INVENTORY_SIZE = (14, 9)
STASH_SIZE = (13, 13)
