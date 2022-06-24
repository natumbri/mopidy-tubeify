import re

uri_playlist_regex = re.compile(
    "^tubeify:(?P<service>.+)_playlist:(?P<playlistid>.+)$"
)
uri_user_regex = re.compile("^tubeify:(?P<service>.+)_user:(?P<userid>.+)$")


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
