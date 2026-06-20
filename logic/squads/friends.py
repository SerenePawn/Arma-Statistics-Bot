import json


def parse_friends_ids(v: object) -> list[int]:
    if v is None:
        return []
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except json.JSONDecodeError:
            return []
    if isinstance(v, list):
        return [int(item) for item in v]
    return []
