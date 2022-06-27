# original source https://github.com/spotDL/spotify-downloader
# spotdl/providers/yt_provider.py

from concurrent.futures.thread import ThreadPoolExecutor
# ! Just for static typing
from typing import List, Optional

from spotdl.providers.provider_utils import (
    _create_song_title,
    _match_percentage,
)
from unidecode import unidecode

from mopidy_tubeify import logger


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


def _do_search_and_match(
    song_name: str, song_artists: List[str], isrc: str, ytmusic, song_duration=0, 
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
            sorted_isrc_results = _order_yt_results(isrc_results, song_name, song_artists, song_duration)
        except Exception as e:
            logger.warn(f"_do_search_and_match error {e} with isrc {isrc} ({song_name})")

        if sorted_isrc_results:
            sorted_isrc_results[0]["result"]
        else:
            logger.warn(f"No suitable result for isrc {isrc}")
            logger.warn(f"search for {song_name}, {song_artists}, {song_duration}")

    song_title = _create_song_title(song_name, song_artists).lower()

    # Query YTM by songs only first, this way if we get correct result on the first try
    # we don't have to make another request to ytmusic api that could result in us
    # getting rate limited sooner
    song_info_results = ytmusic.search(song_title, filter="songs")
    # logger.info([result["artists"] for result in song_info_results if not isinstance(result["artists"], list)])

    if song_info_results is None:
        logger.warn(f"Couldn't find the song on YouTube Music: {song_title}")
        return None
    # logger.info([result["artists"] for result in results])
    # Order results
    ordered_song_info_results = _order_yt_results(song_info_results, song_name, song_artists, song_duration)

    # No matches found
    if len(ordered_song_info_results) == 0:
        return None

    # result_items = list(results.items())

    # Sort results by highest score
    sorted_song_info_results = sorted(ordered_song_info_results, key=lambda x: x["average_match"], reverse=True)

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

        song_title = _create_song_title(song_name, song_artists)
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
        if song_duration:
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
