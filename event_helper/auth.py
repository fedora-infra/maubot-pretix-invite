import json
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class Token:
    """Stores a token in memory along with the time that its updated 
    """

    access_token: str
    refresh_token: str
    token_type: str
    expires_at: datetime.datetime


    @classmethod
    def from_str(cls, string):
        return cls.from_json(json.parse(string))

    @classmethod
    def from_json(cls, json):
        now = datetime.now()
        exires_in = timedelta(seconds=json["expires_in"])
        expiry = now + exires_in
        return cls(json["access_token"], json["refresh_token"], json["token_type"], expiry)

    def to_json(self):
        expires_at = self.expires_at
        now = datetime.now()
        exires_in = expires_at - now

        data = asdict(self)
        del data["expires_at"]
        data["expires_in"] = expires_in.seconds
        return json.dumps(data, default=str)