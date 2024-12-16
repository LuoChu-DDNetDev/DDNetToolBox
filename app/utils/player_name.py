from app.globals import GlobalsVal

def name_length_limit(name):
    while len(name.encode('utf-8')) > 15:
        name = name[:-1]
    return name


def get_player_name():
    player_name = GlobalsVal.ddnet_setting_config.get("player_name", None)
    if player_name is None:
        return GlobalsVal.ddnet_setting_config.get("steam_name", "nameless tee")
    else:
        return player_name

def get_dummy_name():
    dummy_name = GlobalsVal.ddnet_setting_config.get("dummy_name", None)
    if dummy_name is None:
        return name_length_limit("[D] " + GlobalsVal.ddnet_setting_config.get("steam_name", "nameless tee"))
    else:
        return dummy_name