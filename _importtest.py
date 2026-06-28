import os, sys

BUILD_DIR = r"D:\Dev\sts_ai\sts_lightspeed\cmake-build-mingw"
MINGW_BIN = r"C:\msys64\mingw64\bin"

sys.path.insert(0, BUILD_DIR)
os.add_dll_directory(MINGW_BIN)

import slaythespire as sts
print("import OK from", sys.executable)
gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 42, 0)
print("HP:", gc.cur_hp, "deck:", gc.deck)
