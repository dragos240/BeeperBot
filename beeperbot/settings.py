from typing import Any, List, Dict

import yaml


SETTINGS_PATH = "beeperbot.yaml"


class Params:
    repetition_penalty: float
    temperature: float
    top_k: int
    top_p: float

    # Defaults from simple-1 preset
    defaults: Dict = {
        "repetition_penalty": 1.15,
        "temperature": 0.7,
        "top_k": 20,
        "top_p": 0.9,
    }

    def __init__(self,
                 repetition_penalty: float,
                 temperature: float,
                 top_k: int,
                 top_p: float):
        self.repetition_penalty = repetition_penalty
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p

    def to_dict(self):
        """Converts the params into a Dict that can be exported"""
        return {
            "repetition_penalty": self.repetition_penalty,
            "temperature": self.temperature,
            "top_k": self.top_k,
            "top_p": self.top_p,
        }

    @classmethod
    def from_defaults(cls):
        """Sets values to defaults"""
        defaults = cls.defaults

        return cls(defaults["repetition_penalty"],
                   defaults["temperature"],
                   defaults["top_k"],
                   defaults["top_p"])


class Settings:
    character: str
    starting_channel: str
    channel_blacklist: str
    channel_whitelist: str
    params: Params

    def __init__(self):
        self.load_from_file()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character": self.character,
            "starting_channel": self.starting_channel,
            "channel_blacklist": self.channel_blacklist,
            "channel_whitelist": self.channel_whitelist,
            "params": self.params.to_dict(),
        }

    def save_to_file(self):
        with open(SETTINGS_PATH, "w") as f:
            f.write(yaml.dump(self.to_dict()))

    def load_from_file(self):
        try:
            with open(SETTINGS_PATH, "r") as f:
                data = yaml.full_load(f.read())
            self.character = data["character"]
            self.starting_channel = data.get("starting_channel", "")
            self.channel_blacklist = data.get("channel_blacklist", "")
            self.channel_whitelist = data.get("channel_whitelist", "")
            params = data.get("params")
            self.params = Params.from_defaults()
            if type(params) is dict:
                self.params = Params(**params)
        except OSError:
            pass
