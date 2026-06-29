import slaythespire as sts

gc = sts.GameContext(sts.CharacterClass.IRONCLAD, 42, 0)
print("HP:", gc.cur_hp, "deck:", gc.deck)
