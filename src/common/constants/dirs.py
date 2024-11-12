import os

from config import ROOT_PATH


D2S_STORAGE_DIR = os.path.join(ROOT_PATH, 'd2s_storage')
DATA_DIR = os.path.join(ROOT_PATH, 'data')
TMR_DIR = os.path.join(ROOT_PATH, 'tmp')

if not os.path.exists(TMR_DIR):
    try:
        os.makedirs(TMR_DIR)
    except:
        pass
