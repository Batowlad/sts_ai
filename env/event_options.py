"""Human-readable descriptions for event-screen GameAction options.

The engine stores no option text; an event option is just an index into the switch in
GameContext::chooseEventOption (GameContext.cpp). This is a Python port of the engine's
own console UI text (ConsoleSimulator::printEventActions), driven by the `gc.cur_event`,
`gc.cur_event_name`, `gc.event_info` and `gc.neow_rewards` bindings.

Option indices are FIXED SLOTS per event (see GameAction::getValidEventSelectBits): an
unavailable option (e.g. not enough gold) is simply absent from legal actions, but the
remaining options keep their numbers.

    event_option_texts(gc)         -> dict[int, str]  all currently valid options
    describe_event_option(gc, idx) -> str             text for one option index
"""


def _name(enum_val) -> str:
    """RelicId.BLOOD_VIAL -> 'Blood Vial', Potion.FIRE_POTION -> 'Fire Potion'."""
    return str(enum_val).split(".")[-1].replace("_", " ").title()


def event_option_texts(gc) -> dict:
    """{option_idx: description} for the current EVENT_SCREEN state.

    Mirrors ConsoleSimulator::printEventActions, including which options are shown
    based on gold, deck contents, relics and event phase.
    """
    ev = gc.cur_event.name
    info = gc.event_info
    unfavorable = gc.ascension >= 15
    opts = {}

    if ev == "NEOW":
        for i, o in enumerate(gc.neow_rewards):
            text = o.bonus_text
            if o.drawback_text:
                text += " " + o.drawback_text
            opts[i] = text

    elif ev == "OMINOUS_FORGE":
        opts[0] = "[Forge] Upgrade a card."
        opts[1] = "[Rummage] Obtain Warped Tongs relic. Become Cursed - Pain."
        opts[2] = "[Leave] Nothing happens."

    elif ev == "PLEADING_VAGRANT":
        opts[0] = "[Give 85 Gold] Obtain a random Relic."
        opts[1] = "[Rob] Obtain a random Relic. Become Cursed - Shame."
        opts[2] = "[Leave] Nothing happens."

    elif ev == "ANCIENT_WRITING":
        opts[0] = "[Elegance] Remove a card from your deck."
        opts[1] = "[Simplicity] Upgrade all Strikes and Defends."

    elif ev == "OLD_BEGGAR":
        opts[0] = "[Offer Gold] Lose 75 Gold. Remove a card from your deck."
        opts[1] = "[Leave] Nothing happens."

    elif ev == "BIG_FISH":
        opts[0] = f"[Banana] Heal {info['hp_amount0']} HP."
        opts[1] = "[Donut] Max HP +5."
        opts[2] = "[Box] Receive a random Relic. Become Cursed - Regret."

    elif ev == "COLOSSEUM":
        if info["event_data"] == 0:
            opts[0] = "[Fight] Fight some weak enemies."
        else:
            opts[0] = "[COWARDICE] Escape."
            opts[1] = "[VICTORY] A powerful fight with many rewards."

    elif ev == "CURSED_TOME":
        phase = info["event_data"]
        if phase == 0:
            opts[0] = "[Read] Approach the book."
            opts[1] = "[Leave] Nothing happens."
        elif phase in (1, 2, 3):
            opts[phase + 1] = f"[Continue] Lose {phase} HP."
        elif phase == 4:
            opts[5] = f"[Take] Obtain the Book (random relic). Lose {15 if unfavorable else 10} HP."
            opts[6] = "[Stop] Lose 3 HP."

    elif ev == "DEAD_ADVENTURER":
        chance = info["phase"] * 25 + (35 if unfavorable else 25)
        opts[0] = f"[Search] Find loot. {chance}% chance an Elite returns to fight you."
        opts[1] = "[Escape] End the search and resume your journey."

    elif ev == "DESIGNER_IN_SPIRE":
        cost0 = 50 if unfavorable else 40
        cost1 = 75 if unfavorable else 60
        cost2 = 110 if unfavorable else 90
        if info["upgrade_one"]:
            opts[0] = f"[Adjustments] Lose {cost0} Gold. Upgrade a card."
        else:
            opts[1] = f"[Adjustments] Lose {cost0} Gold. Upgrade 2 random cards."
        if info["clean_up_is_remove_card"]:
            opts[2] = f"[Clean Up] Lose {cost1} Gold. Remove a card."
        else:
            opts[3] = f"[Clean Up] Lose {cost1} Gold. Transform 2 random cards."
        opts[4] = f"[Full Service] Lose {cost2} Gold. Remove a card, then upgrade a random card."
        opts[5] = f"[Punch] Lose {5 if unfavorable else 3} HP."

    elif ev == "AUGMENTER":
        opts[0] = "[Test J.A.X.] Obtain a J.A.X. card."
        opts[1] = "[Become Test Subject] Choose and Transform 2 cards in your deck."
        opts[2] = "[Ingest Mutagens] Obtain Mutagenic Strength relic."

    elif ev == "DUPLICATOR":
        opts[0] = "[Pray] Duplicate a card in your deck."
        opts[1] = "[Leave] Nothing happens."

    elif ev == "FACE_TRADER":
        opts[0] = f"[Touch] Lose {info['hp_amount0']} HP. Gain {50 if unfavorable else 75} Gold."
        opts[1] = "[Trade] Obtain a random Face relic (50% good, 50% bad)."
        opts[2] = "[Leave] Nothing happens."

    elif ev == "FALLING":
        deck = gc.deck
        if info["skill_card_deck_idx"] != -1:
            opts[0] = f"[Land] Lose {deck[info['skill_card_deck_idx']]} (Skill)."
        if info["power_card_deck_idx"] != -1:
            opts[1] = f"[Channel] Lose {deck[info['power_card_deck_idx']]} (Power)."
        if info["attack_card_deck_idx"] != -1:
            opts[2] = f"[Strike] Lose {deck[info['attack_card_deck_idx']]} (Attack)."
        if not opts:
            opts[3] = "[Splat] Lose nothing."

    elif ev == "FORGOTTEN_ALTAR":
        opts[0] = "[Offer: Golden Idol] Obtain Bloody Idol. Lose Golden Idol."
        opts[1] = f"[Sacrifice] Gain 5 Max HP. Lose {info['hp_amount0']} HP."
        opts[2] = "[Desecrate] Become Cursed - Decay."

    elif ev == "THE_DIVINE_FOUNTAIN":
        opts[0] = "[Drink] Remove all Curses from your deck."
        opts[1] = "[Leave] Nothing happens."

    elif ev == "GHOSTS":
        opts[0] = (f"[Accept] Receive {3 if unfavorable else 5} Apparition cards. "
                   f"Lose {info['hp_amount0']} Max HP.")
        opts[1] = "[Refuse] Nothing happens."

    elif ev == "GOLDEN_IDOL":
        opts[0] = "[Take] Obtain Golden Idol. Trigger a trap."
        opts[1] = "[Leave] Nothing happens."
        opts[2] = "[Outrun] Become Cursed - Injury."
        opts[3] = f"[Smash] Take {info['hp_amount0']} damage."
        opts[4] = f"[Hide] Lose {info['hp_amount1']} Max HP."

    elif ev == "GOLDEN_SHRINE":
        opts[0] = f"[Pray] Gain {50 if unfavorable else 100} Gold."
        opts[1] = "[Desecrate] Gain 275 Gold. Become Cursed - Regret."
        opts[2] = "[Leave] Nothing happens."

    elif ev == "WING_STATUE":
        opts[0] = "[Pray] Remove a card from your deck. Lose 7 HP."
        opts[1] = "[Destroy] Gain 50-80 Gold."
        opts[2] = "[Leave] Nothing happens."

    elif ev == "KNOWING_SKULL":
        opts[0] = f"[Riches?] Gain 90 Gold. Lose {info['hp_amount0']} HP."
        opts[1] = f"[Success?] Obtain a random colorless card. Lose {info['hp_amount1']} HP."
        opts[2] = f"[A Pick Me Up?] Obtain a random Potion. Lose {info['hp_amount2']} HP."
        opts[3] = "[How do I leave?] Lose 6 HP and leave."

    elif ev == "THE_SSSSSERPENT":
        opts[0] = f"[Agree] Gain {150 if unfavorable else 175} Gold. Become Cursed - Doubt."
        opts[1] = "[Disagree] Nothing happens."

    elif ev == "LIVING_WALL":
        opts[0] = "[Forget] Remove a card from your deck."
        opts[1] = "[Change] Transform a card in your deck."
        opts[2] = "[Grow] Upgrade a card in your deck."

    elif ev == "MASKED_BANDITS":
        opts[0] = "[Pay] Lose ALL of your Gold."
        opts[1] = "[Fight!] Fight the Masked Bandits (reward: Red Mask relic + gold)."

    elif ev == "MINDBLOOM":
        opts[0] = "[I am War] Fight an Act 1 Boss. Reward: Rare Relic and gold."
        opts[1] = "[I am Awake] Upgrade ALL cards. Obtain Mark of the Bloom (you can no longer heal)."
        if gc.floor_num <= 40:
            opts[2] = "[I am Rich] Gain 999 Gold. Become Cursed - 2 Normality."
        else:
            opts[3] = "[I am Healthy] Heal to full HP. Become Cursed - Doubt."

    elif ev == "HYPNOTIZING_COLORED_MUSHROOMS":
        # sim simplification: [Eat] grants gold instead of the game's heal + Parasite
        opts[0] = "[Stomp] Fight the Mushrooms (reward: Odd Mushroom relic + gold)."
        opts[1] = f"[Eat] Gain {50 if unfavorable else 99} Gold."

    elif ev == "MYSTERIOUS_SPHERE":
        opts[0] = "[Open Sphere] Fight. Reward: Rare Relic and gold."
        opts[1] = f"[Leave] Gain {50 if unfavorable else 99} Gold."

    elif ev == "THE_NEST":
        opts[0] = f"[Smash and Grab] Obtain {50 if unfavorable else 99} Gold."
        opts[1] = "[Stay in Line] Obtain Ritual Dagger card. Lose 6 HP."

    elif ev == "NLOTH":
        relics = gc.relics
        r1 = _name(relics[info["relic_idx0"]].id)
        r2 = _name(relics[info["relic_idx1"]].id)
        opts[0] = f"[Offer {r1}] Lose this relic. Obtain N'loth's Gift."
        opts[1] = f"[Offer {r2}] Lose this relic. Obtain N'loth's Gift."
        opts[2] = "[Leave] Nothing happens."

    elif ev == "NOTE_FOR_YOURSELF":
        opts[0] = (f"[Take and Give] Receive {gc.note_for_yourself_card}. "
                   f"Store a card from your deck in return.")
        opts[1] = "[Ignore] Nothing happens."

    elif ev == "PURIFIER":
        opts[0] = "[Pray] Remove a card from your deck."
        opts[1] = "[Leave] Nothing happens."

    elif ev == "SCRAP_OOZE":
        # sim: HP loss is flat 3/5 (does not grow per attempt like the real game)
        phase = info["event_data"]
        hp_loss = 5 if unfavorable else 3
        chance = 10 * phase + 25
        opts[0] = f"[Reach Inside] Lose {hp_loss} HP. {chance}% chance to find a Relic."
        opts[1] = "[Leave] Nothing happens."

    elif ev == "SECRET_PORTAL":
        opts[0] = "[Enter the Portal] Immediately travel to the Act boss."
        opts[1] = "[Leave] Nothing happens."

    elif ev == "SENSORY_STONE":
        opts[0] = "[Recall] Choose 1 colorless card to add to your deck."
        opts[1] = "[Recall] Choose 2 colorless cards to add to your deck. Lose 5 HP."
        opts[2] = "[Recall] Choose 3 colorless cards to add to your deck. Lose 10 HP."

    elif ev == "SHINING_LIGHT":
        opts[0] = f"[Enter] Upgrade 2 random cards. Take {info['hp_amount0']} damage."
        opts[1] = "[Leave] Nothing happens."

    elif ev == "THE_CLERIC":
        opts[0] = f"[Heal] Lose 35 Gold. Heal {info['hp_amount0']} HP."
        opts[1] = f"[Purify] Lose {75 if unfavorable else 50} Gold. Remove a card from your deck."
        opts[2] = "[Leave] Nothing happens."

    elif ev == "THE_JOUST":
        opts[0] = "[Murderer] Bet 50 Gold - 70% chance to win 100 Gold."
        opts[1] = "[Owner] Bet 50 Gold - 30% chance to win 250 Gold."

    elif ev == "THE_LIBRARY":
        opts[0] = "[Read] Choose 1 of 20 cards to add to your deck."
        opts[1] = f"[Sleep] Heal {info['hp_amount0']} HP."

    elif ev == "THE_MAUSOLEUM":
        opts[0] = (f"[Open Coffin] Obtain a random relic. "
                   f"{100 if unfavorable else 50}% chance: Become Cursed - Writhe.")
        opts[1] = "[Leave] Nothing happens."

    elif ev == "THE_MOAI_HEAD":
        opts[0] = f"[Jump Inside] Heal to full HP. Lose {info['hp_amount0']} Max HP."
        opts[1] = "[Offer: Golden Idol] Receive 333 Gold. Lose Golden Idol."
        opts[2] = "[Leave] Nothing happens."

    elif ev == "THE_WOMAN_IN_BLUE":
        # sim simplification: no gold is charged for the potions
        opts[0] = "[Buy 1 Potion] Receive 1 random Potion."
        opts[1] = "[Buy 2 Potions] Receive 2 random Potions."
        opts[2] = "[Buy 3 Potions] Receive 3 random Potions."
        if unfavorable:
            opts[3] = f"[Leave] Lose {info['hp_amount0']} HP."
        else:
            opts[3] = "[Leave] Nothing happens."

    elif ev == "TOMB_OF_LORD_RED_MASK":
        opts[0] = "[Don the Red Mask] Gain 222 Gold."
        opts[1] = f"[Offer Gold ({gc.gold})] Lose ALL Gold. Obtain the Red Mask relic."
        opts[2] = "[Leave] Nothing happens."

    elif ev == "TRANSMORGRIFIER":
        opts[0] = "[Pray] Transform a card in your deck."
        opts[1] = "[Leave] Nothing happens."

    elif ev == "UPGRADE_SHRINE":
        opts[0] = "[Pray] Upgrade a card in your deck."
        opts[1] = "[Leave] Nothing happens."

    elif ev == "VAMPIRES":
        opts[0] = "[Offer Blood Vial] Lose Blood Vial. Remove all Strikes. Receive 5 Bites."
        opts[1] = (f"[Accept] Remove all Strikes. Receive 5 Bites. "
                   f"Lose {info['hp_amount0']} Max HP.")
        opts[2] = "[Refuse] Nothing happens."

    elif ev == "WE_MEET_AGAIN":
        if info["potion_idx"] != -1:
            opts[0] = (f"[Give Potion] Lose {_name(gc.potions[info['potion_idx']])}. "
                       f"Obtain a random relic.")
        if info["gold"] != -1:
            opts[1] = f"[Give Gold] Lose {info['gold']} Gold. Obtain a random relic."
        if info["card_idx"] != -1:
            opts[2] = (f"[Give Card] Lose {gc.deck[info['card_idx']]}. "
                       f"Obtain a random relic.")
        opts[3] = "[Attack] Nothing happens."

    elif ev == "WHEEL_OF_CHANGE":
        opts[0] = ("[Play] Spin the wheel: random result among gold, a relic, full heal, "
                   "Decay curse, card removal, or HP loss.")

    elif ev == "WINDING_HALLS":
        opts[0] = f"[Embrace Madness] Receive 2 Madness cards. Lose {info['hp_amount0']} HP."
        opts[1] = f"[Press On] Become Cursed - Writhe. Heal {info['hp_amount1']} HP."
        opts[2] = f"[Retrace Your Steps] Lose {info['hp_amount2']} Max HP."

    elif ev == "WORLD_OF_GOOP":
        opts[0] = "[Gather Gold] Gain 75 Gold. Lose 11 HP."
        opts[1] = f"[Leave It] Lose {info['gold_loss']} Gold."

    return opts


def describe_event_option(gc, idx: int) -> str:
    """Text for one event option index, e.g. describe_event_option(gc, a.idx1)."""
    text = event_option_texts(gc).get(idx)
    if text is None:
        return f"option {idx}"
    return text
