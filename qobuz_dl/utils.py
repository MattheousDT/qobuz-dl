import re
import string
import os
import logging
import subprocess
import time
import unicodedata

from mutagen.mp3 import EasyMP3
from mutagen.flac import FLAC

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EXTENSIONS = (".mp3", ".flac")


class PartialFormatter(string.Formatter):
    def __init__(self, missing="n/a", bad_fmt="n/a"):
        self.missing, self.bad_fmt = missing, bad_fmt

    def get_field(self, field_name, args, kwargs):
        try:
            val = super(PartialFormatter, self).get_field(field_name, args, kwargs)
        except (KeyError, AttributeError):
            val = None, field_name
        return val

    def format_field(self, value, spec):
        if not value:
            return self.missing
        try:
            return super(PartialFormatter, self).format_field(value, spec)
        except ValueError:
            if self.bad_fmt:
                return self.bad_fmt
            raise


def make_m3u(pl_directory):
    track_list = ["#EXTM3U"]
    rel_folder = os.path.basename(os.path.normpath(pl_directory))
    pl_name = rel_folder + ".m3u"
    for local, dirs, files in os.walk(pl_directory):
        dirs.sort()
        audio_rel_files = [
            os.path.join(os.path.basename(os.path.normpath(local)), file_)
            for file_ in files
            if os.path.splitext(file_)[-1] in EXTENSIONS
        ]
        audio_files = [
            os.path.abspath(os.path.join(local, file_))
            for file_ in files
            if os.path.splitext(file_)[-1] in EXTENSIONS
        ]
        if not audio_files or len(audio_files) != len(audio_rel_files):
            continue

        for audio_rel_file, audio_file in zip(audio_rel_files, audio_files):
            try:
                pl_item = (
                    EasyMP3(audio_file) if ".mp3" in audio_file else FLAC(audio_file)
                )
                title = pl_item["TITLE"][0]
                artist = pl_item["ARTIST"][0]
                length = int(pl_item.info.length)
                index = "#EXTINF:{}, {} - {}\n{}".format(
                    length, artist, title, audio_rel_file
                )
            except:  # noqa
                continue
            track_list.append(index)

    if len(track_list) > 1:
        with open(os.path.join(pl_directory, pl_name), "w") as pl:
            pl.write("\n\n".join(track_list))


def smart_discography_filter(
    contents: list, save_space: bool = False, skip_extras: bool = False
) -> list:
    """When downloading some artists' discography, many random and spam-like
    albums can get downloaded. This helps filter those out to just get the good stuff.

    This function removes:
        * albums by other artists, which may contain a feature from the requested artist
        * duplicate albums in different qualities
        * (optionally) removes collector's, deluxe, live albums

    :param list contents: contents returned by qobuz API
    :param bool save_space: choose highest bit depth, lowest sampling rate
    :param bool remove_extras: remove albums with extra material (i.e. live, deluxe,...)
    :returns: filtered items list
    """

    # for debugging
    def print_album(album: dict) -> None:
        logger.debug(
            f"{album['title']} - {album.get('version', '~~')} "
            "({album['maximum_bit_depth']}/{album['maximum_sampling_rate']}"
            " by {album['artist']['name']}) {album['id']}"
        )

    TYPE_REGEXES = {
        "remaster": r"(?i)(re)?master(ed)?",
        "extra": r"(?i)(anniversary|deluxe|live|collector|demo|expanded)",
    }

    def is_type(album_t: str, album: dict) -> bool:
        """Check if album is of type `album_t`"""
        version = album.get("version", "")
        title = album.get("title", "")
        regex = TYPE_REGEXES[album_t]
        return re.search(regex, f"{title} {version}") is not None

    def essence(album: dict) -> str:
        """Ignore text in parens/brackets, return all lowercase.
        Used to group two albums that may be named similarly, but not exactly
        the same.
        """
        r = re.match(r"([^\(]+)(?:\s*[\(\[][^\)][\)\]])*", album)
        return r.group(1).strip().lower()

    requested_artist = contents[0]["name"]
    items = [item["albums"]["items"] for item in contents][0]

    # use dicts to group duplicate albums together by title
    title_grouped = dict()
    for item in items:
        title_ = essence(item["title"])
        if title_ not in title_grouped:  # ?
            #            if (t := essence(item["title"])) not in title_grouped:
            title_grouped[title_] = []
        title_grouped[title_].append(item)

    items = []
    for albums in title_grouped.values():
        best_bit_depth = max(a["maximum_bit_depth"] for a in albums)
        get_best = min if save_space else max
        best_sampling_rate = get_best(
            a["maximum_sampling_rate"]
            for a in albums
            if a["maximum_bit_depth"] == best_bit_depth
        )
        remaster_exists = any(is_type("remaster", a) for a in albums)

        def is_valid(album: dict) -> bool:
            return (
                album["maximum_bit_depth"] == best_bit_depth
                and album["maximum_sampling_rate"] == best_sampling_rate
                and album["artist"]["name"] == requested_artist
                and not (  # states that are not allowed
                    (remaster_exists and not is_type("remaster", album))
                    or (skip_extras and is_type("extra", album))
                )
            )

        filtered = tuple(filter(is_valid, albums))
        # most of the time, len is 0 or 1.
        # if greater, it is a complete duplicate,
        # so it doesn't matter which is chosen
        if len(filtered) >= 1:
            items.append(filtered[0])

    return items


def format_duration(duration):
    return time.strftime("%H:%M:%S", time.gmtime(duration))


def create_and_return_dir(directory):
    fix = os.path.normpath(directory)
    os.makedirs(fix, exist_ok=True)
    return fix


def get_url_info(url):
    """Returns the type of the url and the id.

    Compatible with urls of the form:
        https://www.qobuz.com/us-en/{type}/{name}/{id}
        https://open.qobuz.com/{type}/{id}
        https://play.qobuz.com/{type}/{id}
        /us-en/{type}/-/{id}
    """

    r = re.search(
        r"(?:https:\/\/(?:w{3}|open|play)\.qobuz\.com)?(?:\/[a-z]{2}-[a-z]{2})"
        r"?\/(album|artist|track|playlist|label)(?:\/[-\w\d]+)?\/([\w\d]+)",
        url,
    )
    return r.groups()


def get_album_artist(qobuz_album: dict) -> str:
    """
    Get the album's main artists from the Qobuz API response.
    If there are multiple main artists, they are separated by " & ".
    :param qobuz_album: Qobuz API response.
    :return: The album's main artists.
    """
    try:
        if not qobuz_album.get("artists"):
            return qobuz_album.get("artist", {}).get("name", "")

        main_artists = list(filter(lambda a: "main-artist" in a.get("roles", []),
                                   qobuz_album.get("artists", [])))
        if len(main_artists) > 1:
            all_but_last_artist = ", ".join(map(lambda a: a["name"], main_artists[:-1]))
            last_artist = main_artists[-1]["name"]
            return f"{all_but_last_artist} & {last_artist}"
        else:
            return qobuz_album.get("artist", {}).get("name", "")
    except Exception as e:
        logger.error(f"Error getting album artist: {str(e)}")
        return qobuz_album.get("artist", {}).get("name", "")


def clean_filename(filename: str) -> str:
    """
    Clean up redundant special characters, spaces, separators in filenames
    and normalize Unicode characters to NFC form
    :param filename:
    :return:
    """
    # First normalize the Unicode string to NFC form
    filename = unicodedata.normalize('NFC', filename)
    
    # Clean up redundant spaces, separators, and brackets

    # Merge multiple separators (supports spaces, commas, periods, Chinese commas, colons, semicolons, vertical bars, slashes, backslashes, underscores. Does not support the - symbol) into one
    filename = re.sub(r'(?:\s*([,\.\:\;\|/\\_])\s*){2,}', r'\1 ', filename)

    # Define all paired bracket patterns
    patterns = [
        # Handle paired brackets containing only special characters
        (r'\(\s*\W*\s*\)', ''),  # (...)
        (r'\[\s*\W*\s*\]', ''),  # [...]
        (r'\{\s*\W*\s*\}', ''),  # {...}
        (r'<\s*\W*\s*>', ''),  # <...>
        (r'《\s*\W*\s*》', ''),  # 《...》
        (r'〈\s*\W*\s*〉', ''),  # 〈...〉
        (r'「\s*\W*\s*」', ''),  # 「...」
        (r'『\s*\W*\s*』', ''),  # 『...』
        (r'（\s*\W*\s*）', ''),  # （...）
        (r'［\s*\W*\s*］', ''),  # ［...］
        (r'【\s*\W*\s*】', ''),  # 【...】

        # Handle edge cases - remove all special characters and spaces at boundaries
        # If a left bracket is followed by a separator, or a separator is followed by a right bracket, remove them
        (r'(?<=[\(\[\{<《〈「『（［【])(\s*[,\.\:\;\|/\\_]\s*)\b', ''),
        (r'\b(\s*[,\.\:\;\|/\\_]\s*)(?=[】］）』」〉》>\}\]\)])', ''),
    ]

    # Apply each pattern sequentially
    for pattern, replacement in patterns:
        filename = re.sub(pattern, replacement, filename)

    # Merge multiple spaces
    filename = re.sub(r'\s+', ' ', filename)
    return invalid_chars_to_fullwidth(filename.strip().strip(".").strip())


def invalid_chars_to_fullwidth(filename):
    """
    Convert illegal characters in filenames to full-width characters
    :param filename:
    :return:
    """
    # Illegal characters to full-width characters
    invalid_to_fullwidth = {
        '/': '／',
        '\\': '＼',
        ':': '：',
        '*': '＊',
        '?': '？',
        '"': '＂',
        '<': '＜',
        '>': '＞',
        '|': '｜',
    }

    for invalid_char, fullwidth_char in invalid_to_fullwidth.items():
        filename = filename.replace(invalid_char, fullwidth_char)
    return filename


def _run_cmd(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr

def flac_fix_md5s(flac_file_path: str) -> bool:
    """
    Fix the MD5s of FLAC files by re-encoding them with the -sf8 option.
    :param flac_file_path: Path to the FLAC file.
    :return: True if successful, False otherwise
    """
    if not os.path.isfile(flac_file_path):
        logger.error(f"File not found: {flac_file_path}")
        return False
        
    logger.info(f"Fixing MD5s in {flac_file_path}")
    md5sum_cmd = f'flac -sf8 "{flac_file_path}"'
    logger.debug(f"Running command: {md5sum_cmd}")
    
    returncode, stdout, stderr = _run_cmd(md5sum_cmd)
    if returncode == 0:
        if stderr.strip():
            logger.warning(stderr.strip())
        return True
    else:
        logger.error(f'Error: md5sum command failed with return code {returncode}')
        logger.error(f'Error: {stderr.strip()}')
        return False