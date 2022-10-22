# based on original source from https://github.com/spotDL/spotify-downloader v3
# https://github.com/spotDL/spotify-downloader/blob/v3/spotdl/providers/yt_provider.py
# https://github.com/spotDL/spotify-downloader/blob/v3/spotdl/providers/provider_utils.py

import re
from concurrent.futures.thread import ThreadPoolExecutor

# ! Just for static typing
from typing import List, Optional

from cachetools import TTLCache, cached
# from mopidy_youtube.apis import youtube_japi
# from mopidy_youtube.timeformat import ISO8601_to_seconds
from rapidfuzz import fuzz
from unidecode import unidecode

from mopidy_tubeify import logger

bracked_re = re.compile(r"[\(\[](?P<bracketed>.*?)[\)\]]")

cache_max_len = 4000
cache_ttl = 21600

yt_matcher_cache = TTLCache(maxsize=cache_max_len, ttl=cache_ttl)


# Custom Decorator function
def listToTuple(function):
    def wrapper(*args, **kwargs):
        _args = tuple([tuple(x) if type(x) == list else x for x in args])
        _kwargs = {
            k: (tuple(v) if type(v) == list else v) for k, v in kwargs.items()
        }
        result = function(*_args, **_kwargs)
        return result

    return wrapper


def search_and_get_best_match(tracks, ytmusic):
    def search_and_get_best_match_wrapper(track):
        yt_track = _do_search_and_match(**track, ytmusic=ytmusic)
        if yt_track:
            track.update(yt_track)
        return track

    results = []

    with ThreadPoolExecutor(4) as executor:
        futures = executor.map(search_and_get_best_match_wrapper, tracks)
        [results.append(value) for value in futures if value is not None]

    return results


def search_and_get_best_album(artists_albumtitle, ytmusic):
    # this is extremely hacky - just searches for "album" in "albums"
    # and returns a list with one result. no sorting, no checking, etc

    def get_albums(query, types):
        return [
            album
            for album in ytmusic.search(query, filter="albums", limit=10)
            if album["type"] in types
        ]

    def check_album(album, album_info_results):
        lower_album_name = album[1].lower()
        album_name_words = lower_album_name.replace("-", " ").split(" ")

        lower_album_artists = [artist.lower().strip() for artist in album[0]]

        for album_result in album_info_results:
            lower_result_name = album_result["title"].lower()
            lower_result_artists = [
                artist["name"].lower() for artist in album_result["artists"]
            ]

            # ! check for common album name word
            for album_name_word in album_name_words:
                if (
                    album_name_word not in ["", "a", "the", "of", "and"]
                    and album_name_word in lower_result_name
                ):

                    if lower_album_artists[0] in ["unknown", "various artists"]:
                        return [album_result]

                    for lower_album_artist in lower_album_artists:
                        for lower_result_artist in lower_result_artists:
                            if _match_percentage(
                                lower_album_artist,
                                lower_result_artist,
                                85,
                            ):
                                return [album_result]

        logger.warn(f"No match for {album}")  # " ({album_info_results})")

        return []

    result = None

    if artists_albumtitle[1] == "(self titled)":
        artists_albumtitle == (artists_albumtitle[0], artists_albumtitle[0][0])

    types = ["Album"]

    # EPs are hard.
    if re.match(r"^.+EP$", artists_albumtitle[1]):
        types.append("EP")
        # for some reason having "EP" at the end of a search string wrecks
        # search results for EPs?!
        artists_albumtitle = (
            artists_albumtitle[0],
            re.sub(r"\ EP$", "", artists_albumtitle[1]),
        )

    album_info_results = get_albums(
        f"{artists_albumtitle[0][0]} {artists_albumtitle[1]}", types
    )

    result = check_album(artists_albumtitle, album_info_results)

    if not result:
        # chuck in a couple of title only, might help.
        album_info_results = get_albums(f"{artists_albumtitle[1]}", types)
        result = check_album(artists_albumtitle, album_info_results)

    if bracked_re.search(artists_albumtitle[1]):
        if not result:
            # try without stuff in brackets
            album_info_results = get_albums(
                f"{artists_albumtitle[0][0]} {bracked_re.sub('', artists_albumtitle[1])}",
                types,
            )
            result = check_album(
                (
                    artists_albumtitle[0],
                    bracked_re.sub("", artists_albumtitle[1]),
                ),
                album_info_results,
            )

        if not result:
            # try with only stuff in brackets
            album_info_results = get_albums(
                f"{artists_albumtitle[0][0]} {bracked_re.search(artists_albumtitle[1])['bracketed']}",
                types,
            )
            result = check_album(
                (
                    artists_albumtitle[0],
                    bracked_re.search(artists_albumtitle[1])["bracketed"],
                ),
                album_info_results,
            )

    return result


def _match_percentage(str1: str, str2: str, score_cutoff: float = 0) -> float:
    """
    A wrapper around `rapidfuzz.fuzz.partial_ratio` to handle UTF-8 encoded
    emojis that usually cause errors
    `str` `str1` : a random sentence
    `str` `str2` : another random sentence
    `float` `score_cutoff` : minimum score required to consider it a match
        returns 0 when similarity < score_cutoff
    RETURNS `float`
    """

    # ! this will throw an error if either string contains a UTF-8 encoded emoji
    try:
        return fuzz.partial_ratio(
            str1, str2, processor=None, score_cutoff=score_cutoff
        )

    # ! we build new strings that contain only alphanumerical characters and spaces
    # ! and return the partial_ratio of that
    except:  # noqa:E722
        new_str1 = "".join(
            each_letter
            for each_letter in str1
            if each_letter.isalnum() or each_letter.isspace()
        )

        new_str2 = "".join(
            each_letter
            for each_letter in str2
            if each_letter.isalnum() or each_letter.isspace()
        )

        return fuzz.partial_ratio(
            new_str1, new_str2, processor=None, score_cutoff=score_cutoff
        )


@listToTuple
@cached(cache=yt_matcher_cache)
def _do_search_and_match(
    song_name: str,
    song_artists: List[str],
    isrc: str,
    ytmusic,
    song_duration: int = 0,
    videoId: str = None,
) -> Optional[str]:
    """
    `str` `song_name` : name of song
    `list<str>` `song_artists` : list containing name of contributing artists
    `str` `song_album_name` : name of song's album
    `int` `song_duration` : duration of the song, in seconds
    `str` `isrc` :  code for identifying sound recordings and music video recordings
    RETURNS `str` : videoId of the best match
    """

    # if isrc is not None then we try to find song with it
    if isrc is not None:
        sorted_isrc_results = []
        try:
            isrc_results = ytmusic.search(isrc, limit=1)
            # make sure the isrc result is relevant
            sorted_isrc_results = _order_yt_results(
                isrc_results, song_name, song_artists, song_duration
            )
        except Exception as e:
            logger.warn(
                f"_do_search_and_match error {e} with isrc {isrc} ({song_name})"
            )

        if sorted_isrc_results:
            return sorted_isrc_results[0]["result"]
        else:
            logger.warn(f"No suitable result for isrc {isrc}")
            logger.warn(
                f"search for {song_name}, {song_artists}, {song_duration}"
            )

    if videoId:
        sorted_videoId_results = []
        try:
            videoId_results = [ytmusic.get_song(videoId)["videoDetails"]]

            # .get_song["videoDetails"] is slightly different to .search
            videoId_results[0]["artists"] = [
                {"name": videoId_results[0]["author"]}
            ]
            videoId_results[0]["duration_seconds"] = videoId_results[0][
                "lengthSeconds"
            ]

            # do we need to make sure the videoId result is relevant?
            # sorted_videoId_results = _order_yt_results(
            #     videoId_results, song_name, song_artists, song_duration
            # )
            sorted_videoId_results = [{"result": videoId_results[0]}]

        except Exception as e:
            logger.warn(
                f"_do_search_and_match error {e} with videoId {videoId} ({song_name})"
            )

        if sorted_videoId_results:
            return sorted_videoId_results[0]["result"]
        else:
            logger.warn(f"No suitable result for videoId {videoId}")
            logger.warn(
                f"search for {song_name}, {song_artists}, {song_duration}"
            )

    song_title = f"{', '.join(song_artists)} - {song_name}".lower()

    # Query YTM by songs only first, this way if we get correct result on the first try
    # we don't have to make another request to ytmusic api that could result in us
    # getting rate limited sooner
    song_info_results = ytmusic.search(song_title, filter="songs")

    # Order results
    ordered_song_info_results = _order_yt_results(
        song_info_results, song_name, song_artists, song_duration
    )

    # No matches found
    if len(ordered_song_info_results) == 0:
        if bracked_re.search(song_name) or any(
            [bracked_re.search(artist) for artist in song_artists]
        ):
            return _do_search_and_match(
                song_name=bracked_re.sub("", song_name),
                song_artists=[
                    bracked_re.sub("", artist) for artist in song_artists
                ],
                isrc=None,
                ytmusic=ytmusic,
                song_duration=song_duration,
                videoId=None,
            )

        else:

            # is this a good idea?
            logger.warn(
                f"Couldn't find the song on YouTube Music: {song_title}, trying videos"
            )
            song_info_results = ytmusic.search(song_title, filter="videos")

            # Order results
            ordered_song_info_results = _order_yt_results(
                song_info_results, song_name, song_artists, song_duration
            )

            if song_info_results is None:
                logger.warn(
                    f"Gave up looking for {song_title} on YouTube Music; returning None"
                )
                return None

            # # try normal youtube
            # # is this a good idea? Slows things down, and matches
            # # things that are not songs
            # results = youtube_japi.jAPI.search(
            #     song_name.join(song_artists), params=["EgIQAQ%3D%3D"]
            # )

            # converted_results = [
            #     {
            #         "videoId": item["id"]["videoId"],
            #         "title": item["snippet"]["title"],
            #         "artists": [
            #             {
            #                 "name": song_artist,
            #                 "id": item["snippet"]["channelId"],
            #             } for song_artist in song_artists
            #         ],
            #         "duration_seconds": ISO8601_to_seconds(
            #             item["contentDetails"]["duration"]
            #         ),
            #         "lengthSeconds": ISO8601_to_seconds(
            #             item["contentDetails"]["duration"]
            #         ),
            #         "thumbnail": {
            #             "thumbnails": [item["snippet"]["thumbnails"]["default"]]
            #         },
            #     }
            #     for item in results["items"]
            # ]

            # ordered_song_info_results = _order_yt_results(
            #     converted_results, song_name, song_artists, song_duration
            # )
            # logger.info(f"{song_name}, {song_artists}, ({song_d}) matched using youtube: ")
            # if len(ordered_song_info_results) > 0:
            #     logger.info(

            #         f"{sorted(ordered_song_info_results, key=lambda x: x['average_match'],reverse=True)[0]}"
            #         )
            # else:
            #     logger.info("no match")

    # Sort results by highest score
    if ordered_song_info_results:
        sorted_song_info_results = sorted(
            ordered_song_info_results,
            key=lambda x: x["average_match"],
            reverse=True,
        )

        # ! In theory, the first 'TUPLE' in sorted_results should have the highest match
        # ! value, we send back only the videoId
        return sorted_song_info_results[0]["result"]


def _order_yt_results(
    results: List[dict],
    song_name: str,
    song_artists: List[str],
    song_duration: int,
) -> dict:
    # Assign an overall avg match value to each result
    videoIds_with_match_value = []

    for result in results:
        # ! skip results without videoId, this happens if you are country restricted or
        # ! video is unavailabe
        if result["videoId"] is None:
            continue

        lower_song_name = song_name.lower()
        lower_result_name = result["title"].lower()

        sentence_words = lower_song_name.replace("-", " ").split(" ")

        common_word = False

        # ! check for common word
        for word in sentence_words:
            if word != "" and word in lower_result_name:
                common_word = True

        # ! if there are no common words, skip result
        if common_word is False:
            continue

        # Find artist match
        # ! match  =
        #               (no of artist names in result) /
        #               (no. of artist names on spotify) * 100
        artist_match_number = 0

        # ! we use fuzzy matching because YouTube spellings might be
        # ! mucked up i.e if video
        for artist in song_artists:
            # ! something like _match_percentage('rionos', 'aiobahn,
            # ! rionos Motivation(remix)' would return 100, so we're
            # ! absolutely corrent in matching artists to song name.
            if result["artists"] and _match_percentage(
                str(unidecode(artist.lower())),
                str(unidecode(result["artists"][0]["name"]).lower()),
                85,
            ):
                artist_match_number += 1

        # ! Skip if there are no artists in common, (else, results like
        # ! 'Griffith Swank - Madness' will be the top match for
        # ! 'Ruelle - Madness')
        if artist_match_number == 0:
            continue

        artist_match = (artist_match_number / len(song_artists)) * 100

        song_title = f"{', '.join(song_artists)} - {song_name}".lower()
        name_match = round(
            max(
                # case where artist is included in title
                _match_percentage(
                    str(unidecode(song_title.lower())),
                    str(unidecode(result["title"].lower())),
                    60,
                ),
                # case where artist is author and video title is only
                # the track name
                _match_percentage(
                    str(unidecode(song_name.lower())),
                    str(unidecode(result["title"].lower())),
                    60,
                ),
            ),
            ndigits=3,
        )

        # skip results with name match of 0, these are obviously wrong
        # but can be identified as correct later on due to other factors
        # such as time_match or artist_match
        if name_match == 0:
            continue

        # Find duration match
        # ! time match = 100 - (delta(duration)**2 / original duration * 100)
        # ! difference in song duration (delta) is usually of the magnitude of
        # ! a few seconds, we need to amplify the delta if it is to have any
        # ! meaningful impact when we calculate the avg match value
        if song_duration and song_duration > 0:
            delta = result["duration_seconds"] - song_duration  # ! check this
            non_match_value = (delta ** 2) / song_duration * 100

            time_match = 100 - non_match_value

            average_match = (artist_match + name_match + time_match) / 3
        else:
            average_match = (artist_match + name_match) / 2

        # the results along with the avg Match
        videoIds_with_match_value.append(
            {"average_match": average_match, "result": result}
        )

    return videoIds_with_match_value
