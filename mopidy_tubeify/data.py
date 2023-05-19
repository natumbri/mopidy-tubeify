import re

uri_playlist_regex = re.compile(
    "^tubeify:(?P<service>.+):playlist_(?P<playlistid>.+)$"
)
uri_user_regex = re.compile("^tubeify:(?P<service>.+):user_(?P<userid>.+)$")


def extract_playlist_id(uri) -> str:
    match = uri_playlist_regex.match(uri)
    if match:
        return match.group("service"), match.group("playlistid")
    return ""


def extract_user_id(uri) -> str:
    match = uri_user_regex.match(uri)
    if match:
        return match.group("service"), match.group("userid")
    return ""


def find_in_obj(obj, condition, kind):
    # In case this is a list
    if isinstance(obj, list):
        for index, value in enumerate(obj):
            for result in find_in_obj(value, condition, kind):
                yield result
    # In case this is a dictionary
    if isinstance(obj, dict):
        for key, value in obj.items():
            for result in find_in_obj(value, condition, kind):
                yield result
            if condition == key and obj[key] == kind:
                yield obj


def flatten(items):
    """Yield items from any nested list; see Reference."""
    for x in items:
        if isinstance(x, list) and not isinstance(x, (str, bytes)):
            for sub_x in flatten(x):
                yield sub_x
        else:
            yield x
