import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

@dataclass
class Token:
    """Stores a token in memory along with the time that its updated 
    """

    access_token: str
    refresh_token: str
    token_type: str
    scope: list[str]
    expires_at: datetime


    @classmethod
    def from_str(cls, string):
        return cls.from_json(json.loads(string))

    @classmethod
    def from_json(cls, json):
        if json.get("expires_at") is not None:
            expiry = datetime.fromtimestamp(json.get("expires_at"), tz=timezone.utc)
        else:
            now = datetime.now()
            exires_in = timedelta(seconds=json["expires_in"])
            expiry = now + exires_in
        return cls(json["access_token"], json["refresh_token"], json["token_type"], json["scope"], expiry)

    def to_json(self) -> str:
        expires_at = self.expires_at
        now = datetime.now()
        exires_in = expires_at - now

        data = asdict(self)
        del data["expires_at"]
        data["expires_in"] = expires_in.seconds
        data["expires_at"] = expires_at.timestamp()
        return json.dumps(data, default=str)