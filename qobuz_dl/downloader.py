import concurrent.futures
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Tuple

import requests
from pathvalidate import sanitize_filename, sanitize_filepath
from tqdm import tqdm

import qobuz_dl.metadata as metadata
from qobuz_dl.color import CYAN, GREEN, OFF, RED, YELLOW
from qobuz_dl.constants import (DEFAULT_FOLDER, DEFAULT_MULTIPLE_DISC_TRACK,
                                DEFAULT_TRACK, OK_MAX_CHARACTER_LENGTH)
from qobuz_dl.db import handle_download_id
from qobuz_dl.exceptions import NonStreamable
from qobuz_dl.settings import QobuzDLSettings
from qobuz_dl.utils import clean_filename, get_album_artist


def process_folder_format_with_subdirs(folder_format, attr_dict, path=None):
    """
    Process folder_format with subdirectories support.
    First splits the path, applies formatting and cleaning to each part, then recombines.
    
    :param folder_format: Format string, may contain path separator '/'
    :param attr_dict: Attribute dictionary for formatting
    :param path: Base path, default is None
    :return: Processed path
    """
    # Split path into parts
    path_parts = folder_format.split('/')
    
    # Process each part individually
    cleaned_parts = []
    for part in path_parts:
        if part:  # Skip empty parts
            # Apply formatting with metadata
            try:
                formatted_part = part.format(**attr_dict)
                # Clean filename without processing path separators
                cleaned_part = sanitize_filepath(clean_filename(formatted_part), replacement_text="_")
                cleaned_parts.append(cleaned_part)
            except KeyError as e:
                # If formatting fails, log error and use original part
                logger.warning(f"{YELLOW}Format error ({e}), using original text.")
                cleaned_part = sanitize_filepath(clean_filename(part), replacement_text="_")
                cleaned_parts.append(cleaned_part)
    
    # Recombine into path
    final_path = os.path.join(*cleaned_parts) if cleaned_parts else ""
    
    # If base path is provided, join with final path
    if path and final_path:
        return os.path.join(path, final_path)
    
    return final_path

QL_DOWNGRADE = "FormatRestrictedByFormatAvailability"
# used in case of error
DEFAULT_FORMATS = {
    "MP3": [
        "{album_artist} - {album_title} ({year}) [MP3]",
        "{track_number} - {track_title}",
    ],
    "Unknown": [
        "{album_artist} - {album_title}",
        "{track_number} - {track_title}",
    ],
}

EMB_COVER_NAME = "embed_cover.jpg"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Download:
    def __init__(
        self,
        client,
        item_id: str,
        path: str,
        quality: int,
        embed_art: bool = False,
        albums_only: bool = False,
        downgrade_quality: bool = False,
        cover_og_quality: bool = False,
        no_cover: bool = False,
        folder_format=None,
        track_format=None,
        settings: QobuzDLSettings = None,
        download_db=None,
    ):
        self.client = client
        self.item_id = item_id
        self.path = path
        self.quality = quality
        self.albums_only = albums_only
        self.embed_art = embed_art
        self.downgrade_quality = downgrade_quality
        self.cover_og_quality = cover_og_quality
        self.no_cover = no_cover
        self.folder_format = folder_format or DEFAULT_FOLDER
        self.track_format = track_format or DEFAULT_TRACK
        self.settings = settings or QobuzDLSettings()
        self.download_db = download_db
        
        # Save original formatting settings
        self._original_folder_format = folder_format or DEFAULT_FOLDER
        self._original_track_format = track_format or DEFAULT_TRACK
        self._original_multiple_disc_track_format = settings.multiple_disc_track_format if settings else DEFAULT_MULTIPLE_DISC_TRACK

    def download_id_by_type(self, track=True):
        # Reset to original format
        self.folder_format = self._original_folder_format
        self.track_format = self._original_track_format
        if self.settings:
            self.settings.multiple_disc_track_format = self._original_multiple_disc_track_format
        
        if not track:
            self.download_release()
        else:
            self.download_track()

    def download_release(self):
        count = 0
        album_meta = self.client.get_album_meta(self.item_id)

        if not album_meta.get("streamable"):
            raise NonStreamable("This release is not streamable")

        if self.albums_only and (
            album_meta.get("release_type") != "album"
            or album_meta.get("artist").get("name") == "Various Artists"
        ):
            logger.info(f'{OFF}Ignoring Single/EP/VA: {album_meta.get("title", "n/a")}')
            return

        album_title = _get_title(album_meta)

        url = album_meta.get("url", "")
        release_date = album_meta.get("release_date_original", "")

        format_info = self._get_format(album_meta)
        file_format, quality_met, bit_depth, sampling_rate = format_info

        if not self.downgrade_quality and not quality_met:
            logger.info(
                f"{OFF}Skipping {album_title} as it doesn't meet quality requirement"
            )
            return

        logger.info(
            f"\n{YELLOW}Downloading: {album_title}\nQuality: {file_format}"
            f" ({bit_depth}/{sampling_rate})\n"
        )
        album_attr = self._get_album_attr(
            album_meta, album_title, file_format, bit_depth, sampling_rate
        )
        # If the album track path exceeds 180 characters, use fallback formatting.
        self._determine_formats(album_meta=album_meta, album_attr=album_attr, tracks_meta=album_meta["tracks"]["items"],
                                track_attr=None, is_track=False,file_format=file_format, settings=self.settings)
        
        # Use new function to process paths with subdirectories
        dirn = process_folder_format_with_subdirs(self.folder_format, album_attr, self.path)
        os.makedirs(dirn, exist_ok=True)

        if self.settings.no_cover:
            logger.info(f"{OFF}Skipping cover")
        else:
            _get_extra(album_meta["image"]["large"], dirn, art_size=self.settings.saved_art_size)

        if self.settings.embed_art:
            _get_extra(album_meta["image"]["large"], dirn, extra=EMB_COVER_NAME, art_size=self.settings.embedded_art_size)
        else:
            logger.info(f"{OFF}Skipping embedded art")

        if "goodies" in album_meta:
            _download_goodies(album_meta, dirn)
        # media_numbers = [track["media_number"] for track in album_meta["tracks"]["items"]]
        # is_multiple = True if len([*{*media_numbers}]) > 1 else False
        media_count = album_meta.get("media_count", 1)
        is_multiple = True if media_count > 1 else False
        
        # Use the configured max_workers value
        with ThreadPoolExecutor(max_workers=self.settings.max_workers) as executor:
            futures = []
            for i in album_meta["tracks"]["items"]:
                parse = self.client.get_track_url(i["id"], fmt_id=self.quality)
                if "sample" not in parse and parse["sampling_rate"]:
                    is_mp3 = True if int(self.quality) == 5 else False
                    futures.append(
                        executor.submit(
                            self._download_and_tag,
                            dirn,
                            count,
                            parse,
                            i,
                            album_meta,
                            False,
                            is_mp3,
                            i["media_number"] if is_multiple else None,
                        )
                    )
                else:
                    logger.info(f"{OFF}Demo. Skipping")
                count = count + 1
                
            # wait for all downloads to complete
            concurrent.futures.wait(futures)
            
        # clean embed_art jpg
        _clean_embed_art(dirn, self.settings)
        # add download info to log
        handle_download_id(db_path=self.download_db, item_id=self.item_id, add_id=True, media_type="album",
                           quality=self.quality, file_format=file_format, quality_met=quality_met,
                           bit_depth=bit_depth, sampling_rate=sampling_rate, saved_path=dirn,
                           url=url, release_date=release_date)
        logger.info(f"{GREEN}Completed")

    def download_track(self):
        parse = self.client.get_track_url(self.item_id, self.quality)

        if "sample" not in parse and parse["sampling_rate"]:
            track_meta = self.client.get_track_meta(self.item_id)
            track_title = _get_title(track_meta)
            artist = _safe_get(track_meta, "performer", "name")
            logger.info(f"\n{YELLOW}Downloading: {artist} - {track_title}")
            url = track_meta.get("album", {}).get("url", "")
            release_date = track_meta.get("release_date_original", "")
            format_info = self._get_format(track_meta, is_track_id=True, track_url_dict=parse)
            file_format, quality_met, bit_depth, sampling_rate = format_info

            folder_format, track_format = _clean_format_str(
                self.folder_format, self.track_format, str(bit_depth)
            )

            if not self.downgrade_quality and not quality_met:
                logger.info(
                    f"{OFF}Skipping {track_title} as it doesn't "
                    "meet quality requirement"
                )
                return
            track_attr = self._get_track_attr(
                track_meta, track_title, bit_depth, sampling_rate, file_format
            )
            # If the track path exceeds 180 characters, use fallback formatting.
            self._determine_formats(album_meta=track_meta.get("album", {}), album_attr=None, tracks_meta=[track_meta],
                                    track_attr=track_attr, is_track=True, file_format=file_format, settings=self.settings)
            
            # Use new function to process paths with subdirectories
            dirn = process_folder_format_with_subdirs(folder_format, track_attr, self.path)
            os.makedirs(dirn, exist_ok=True)

            if self.settings.no_cover:
                logger.info(f"{OFF}Skipping cover")
            else:
                _get_extra(track_meta["album"]["image"]["large"], dirn, art_size=self.settings.saved_art_size)

            if self.settings.embed_art:
                _get_extra(track_meta["album"]["image"]["large"], dirn, extra=EMB_COVER_NAME,
                           art_size=self.settings.embedded_art_size)
            else:
                logger.info(f"{OFF}Skipping embedded art")
            is_mp3 = True if int(self.quality) == 5 else False
            self._download_and_tag(
                dirn,
                1,
                parse,
                track_meta,
                track_meta,
                True,
                is_mp3,
                False,
            )
            # clean embed_art jpg
            _clean_embed_art(dirn, self.settings)
            # add download info to log
            handle_download_id(db_path=self.download_db, item_id=self.item_id, add_id=True, media_type="track",
                               quality=self.quality, file_format=file_format, quality_met=quality_met,
                               bit_depth=bit_depth, sampling_rate=sampling_rate, saved_path=dirn,
                               url=url, release_date=release_date)
        else:
            logger.info(f"{OFF}Demo. Skipping")
        logger.info(f"{GREEN}Completed")

    def _download_and_tag(
        self,
        root_dir,
        tmp_count,
        track_url_dict,
        track_metadata,
        album_or_track_metadata,
        is_track,
        is_mp3,
        multiple=None,
    ):
        extension = ".mp3" if is_mp3 else ".flac"

        try:
            url = track_url_dict["url"]
        except KeyError:
            logger.info(f"{OFF}Track not available for download")
            return

        if multiple and (not self.settings.multiple_disc_one_dir):
            root_dir = os.path.join(root_dir, f"{self.settings.multiple_disc_prefix} {multiple:02}")
            os.makedirs(root_dir, exist_ok=True)

        filename = os.path.join(root_dir, f".{tmp_count:02}.tmp")

        # Determine the filename
        track_title = track_metadata.get("title")
        track_artist = _safe_get(track_metadata, "performer", "name")

        filename_attr = self._get_filename_attr(
            track_artist,
            track_metadata,
            album_or_track_metadata.get("album", {}) if is_track else album_or_track_metadata
        )

        # track_format is a format string
        # e.g. '{tracknumber}. {trackartist} - {tracktitle}'
        if multiple and self.settings.multiple_disc_one_dir:
            formatted_path = sanitize_filename(clean_filename(self.settings.multiple_disc_track_format.format(**filename_attr)),
                                               replacement_text="_")
        else:
            formatted_path = sanitize_filename(clean_filename(self.track_format.format(**filename_attr)), replacement_text="_")
        final_file = os.path.join(root_dir, formatted_path)[:250] + extension

        if os.path.isfile(final_file):
            logger.info(f"{OFF}{track_title} was already downloaded")
            return

        tqdm_download(url, filename, filename)
        tag_function = metadata.tag_mp3 if is_mp3 else metadata.tag_flac
        try:
            tag_function(
                filename,
                root_dir,
                final_file,
                track_metadata,
                album_or_track_metadata,
                is_track,
                self.embed_art,
                settings=self.settings,
            )
        except Exception as e:
            logger.error(f"{RED}Error tagging the file: {e}", exc_info=True)

    @staticmethod
    def _get_filename_attr(track_artist, track_metadata: dict, album_metadata: dict):
        return {
            "album_title":  _get_title(album_metadata),
            "album_title_base": album_metadata.get("title"),
            "album_artist": get_album_artist(album_metadata) if get_album_artist(album_metadata) else track_artist,
            "track_id": track_metadata.get("id"),
            "track_artist": track_artist,
            "track_composer": _safe_get(track_metadata,"composer", "name"),
            "track_number": f'{track_metadata.get("track_number"):02}',
            "isrc": track_metadata.get("isrc"),
            "bit_depth": track_metadata.get("maximum_bit_depth"),
            "sampling_rate": track_metadata.get("maximum_sampling_rate"),
            "track_title": _get_title(track_metadata),
            "track_title_base": track_metadata.get("title"),
            "version": track_metadata.get("version"),
            "year": track_metadata.get("release_date_original").split("-")[0],
            "disc_number": f'{track_metadata.get("media_number"):02}',
            "release_date": track_metadata.get("release_date_original"),
        }

    @staticmethod
    def _get_track_attr(meta, track_title, bit_depth, sampling_rate, file_format):
        album_meta = meta.get("album", {})
        return {
            "track_title": track_title,
            "track_title_base": meta.get("title", ""),
            "album_id": meta.get("id", ""),
            "album_url": meta.get("url", ""),
            "album_title": _get_title(album_meta),
            "album_title_base": album_meta.get("title", ""),
            "album_artist": get_album_artist(album_meta) if get_album_artist(album_meta) else _safe_get(meta, "performer", "name"),
            "album_genre": meta.get("genre", {}).get("name", ""),
            "album_composer": meta.get("composer", {}).get("name", ""),
            # Qobuz sometimes has multiple spaces in place of where a single space should be when it comes to Labels
            "label": re.sub(r'\s*[\;\/]\s*|\s+\-\s+',' ／ ', ' '.join(meta.get("label",{}).get("name", "").split())).strip(),
            "copyright": meta.get("copyright", ""),
            "upc": meta.get("upc", ""),
            "barcode": meta.get("upc", ""),
            "release_date": meta.get("release_date_original", ""),
            "year": meta.get("release_date_original", "").split("-")[0],
            "media_type": meta.get("product_type", "").capitalize(),
            "format": file_format,
            "bit_depth": bit_depth,
            "sampling_rate": sampling_rate,
            "album_version": meta.get("version", ""),
            "disc_count": meta.get("media_count", ""),
            "track_count": meta.get("track_count", ""),
        }

    @staticmethod
    def _get_album_attr(meta, album_title, file_format, bit_depth, sampling_rate):
        return {
            "album_id": meta.get("id", ""),
            "album_url": meta.get("url", ""),
            "album_title": album_title,
            "album_title_base": meta.get("title", ""),
            "album_artist": get_album_artist(meta),
            "album_genre": meta.get("genre", {}).get("name", ""),
            "album_composer": meta.get("composer", {}).get("name", ""),
            # Qobuz sometimes has multiple spaces in place of where a single space should be when it comes to Labels
            "label": re.sub(r'\s*[\;\/]\s*|\s+\-\s+',' ∕ ', ' '.join(meta.get("label",{}).get("name", "").split())).strip(),
            "copyright": meta.get("copyright", ""),
            "upc": meta.get("upc", ""),
            "barcode": meta.get("upc", ""),
            "release_date": meta.get("release_date_original", ""),
            "year": meta.get("release_date_original", "").split("-")[0],
            "media_type": meta.get("product_type", "").capitalize(),
            "format": file_format,
            "bit_depth": bit_depth,
            "sampling_rate": sampling_rate,
            "album_version": meta.get("version", ""),
            "disc_count": meta.get("media_count", 1),
            "track_count": meta.get("track_count", 1),
        }

    def _get_format(self, item_dict, is_track_id=False, track_url_dict=None):
        quality_met = True
        if int(self.quality) == 5:
            return ("MP3", quality_met, None, None)
        track_dict = item_dict
        if not is_track_id:
            track_dict = item_dict["tracks"]["items"][0]

        try:
            new_track_dict = (
                self.client.get_track_url(track_dict["id"], fmt_id=self.quality)
                if not track_url_dict
                else track_url_dict
            )
            restrictions = new_track_dict.get("restrictions")
            if isinstance(restrictions, list):
                if any(
                    restriction.get("code") == QL_DOWNGRADE
                    for restriction in restrictions
                ):
                    quality_met = False

            return (
                "FLAC",
                quality_met,
                new_track_dict["bit_depth"],
                new_track_dict["sampling_rate"],
            )
        except (KeyError, requests.exceptions.HTTPError):
            return ("Unknown", quality_met, None, None)


    def _determine_formats(self, album_meta, album_attr, tracks_meta, track_attr, is_track, file_format, settings: QobuzDLSettings):
        """
        Determine appropriate naming formats, ensuring all file paths don't exceed maximum length.
        Try the following combinations in order of priority:
        1. folder_format + track_format/multiple_disc_track_format
        2. fallback_folder_format + track_format/multiple_disc_track_format  
        3. fallback_folder_format + fallback_track_format/fallback_multiple_disc_track_format
        4. default_folder_format + default_track_format/fallback_multiple_disc_track_format
        
        Note: Format changes only affect current download, not subsequent ones.
        """
        # Prepare all possible format combinations
        format_combinations = [
            (self._original_folder_format, self._original_track_format, self._original_multiple_disc_track_format),
            (settings.fallback_folder_format, self._original_track_format, self._original_multiple_disc_track_format),
            (settings.fallback_folder_format, DEFAULT_TRACK, DEFAULT_MULTIPLE_DISC_TRACK),
            (DEFAULT_FOLDER, DEFAULT_TRACK, DEFAULT_MULTIPLE_DISC_TRACK)
        ]

        # Check if it's a multi-disc album
        media_count = album_meta.get("media_count", 1)
        is_multiple = True if media_count > 1 else False
        extension = ".flac" if file_format.lower() == "flac" else ".mp3"

        # Iterate through each format combination until finding a suitable one
        for folder_fmt, track_fmt, multi_disc_fmt in format_combinations:
            folder_fmt, track_fmt = _clean_format_str(folder_fmt, track_fmt, file_format)
            valid_combination = True
            
            try:
                # Get cleaned folder path
                if is_track:
                    # Process folder_format that may contain subdirectories
                    root_dir = process_folder_format_with_subdirs(folder_fmt, track_attr)
                else:
                    # Process folder_format that may contain subdirectories
                    root_dir = process_folder_format_with_subdirs(folder_fmt, album_attr)

                # Check complete path length for each track
                for track_metadata in tracks_meta:
                    track_artist = _safe_get(track_metadata, "performer", "name")
                    filename_attr = self._get_filename_attr(track_artist, track_metadata, album_meta)

                    curr_root_dir = root_dir
                    if is_multiple and self.settings.multiple_disc_one_dir:
                        # Multiple discs in single directory
                        track_path = sanitize_filename(
                            clean_filename(multi_disc_fmt.format(**filename_attr)),
                            replacement_text="_"
                        )
                    else:
                        # Single disc or multiple discs in separate directories
                        if is_multiple and not self.settings.multiple_disc_one_dir:
                            disc_dir = f"{self.settings.multiple_disc_prefix} {track_metadata['media_number']:02}"
                            curr_root_dir = os.path.join(root_dir, disc_dir)
                        
                        track_path = sanitize_filename(
                            clean_filename(track_fmt.format(**filename_attr)),
                            replacement_text="_"
                        )

                    final_path = os.path.join(curr_root_dir, track_path + extension)
                    
                    if len(final_path) > OK_MAX_CHARACTER_LENGTH:
                        valid_combination = False
                        break
            except (KeyError, ValueError) as e:
                # Format failed, try next combination
                logger.debug(f"Format combination failed: {e}")
                valid_combination = False
                continue

            if valid_combination:
                # Found suitable combination, update instance attributes only
                self.folder_format = folder_fmt
                self.track_format = track_fmt
                if self.settings:
                    self.settings.multiple_disc_track_format = multi_disc_fmt
                return

        # If no combinations are suitable, use the last (default) combination
        logger.warning(f"{YELLOW}Path length too long. Using default formats for this item.")
        self.folder_format = DEFAULT_FOLDER
        self.track_format = DEFAULT_TRACK
        if self.settings:
            self.settings.multiple_disc_track_format = DEFAULT_MULTIPLE_DISC_TRACK


def tqdm_download(url, fname, desc):
    r = requests.get(url, allow_redirects=True, stream=True)
    total = int(r.headers.get("content-length", 0))
    download_size = 0
    with open(fname, "wb") as file, tqdm(
        total=total,
        unit="iB",
        unit_scale=True,
        unit_divisor=1024,
        desc=desc,
        bar_format=CYAN + "{n_fmt}/{total_fmt} /// {desc}",
    ) as bar:
        for data in r.iter_content(chunk_size=1024):
            size = file.write(data)
            bar.update(size)
            download_size += size

    if total != download_size:
        # https://stackoverflow.com/questions/69919912/requests-iter-content-thinks-file-is-complete-but-its-not
        raise ConnectionError("File download was interrupted for " + fname)


def _get_description(item: dict, track_title, multiple=None):
    downloading_title = f"{track_title} "
    f'[{item["bit_depth"]}/{item["sampling_rate"]}]'
    if multiple:
        downloading_title = f"[CD {multiple}] {downloading_title}"
    return downloading_title


def _get_title(item_dict):
    """
    Get the title of the album/track with version if available.
    """
    item_title = item_dict.get("title")
    version = item_dict.get("version")
    if version:
        item_title = (
            f"{item_title} ({version})"
            if version.lower() not in item_title.lower()
            else item_title
        )
    return item_title


def _get_extra(item, dirn, extra="cover.jpg", art_size=None):
    """
    Download extra artwork to the specified directory.
    param: item: the url to download
    param: dirn: the directory to download
    param: extra: the name of the file to save
    param: art_size: the size of the artwork to download (if available)
    """
    extra_file = os.path.join(dirn, extra)
    if os.path.isfile(extra_file):
        logger.info(f"{OFF}{extra} was already downloaded")
        return
        
    # Construct URLs based on the art_size parameter
    if art_size in ["50", "100", "150", "300", "600", "max", "org"]:
        item = item.replace("_600.", f"_{art_size}.")
        
    tqdm_download(item, extra_file, extra)


def _clean_format_str(folder: str, track: str, file_format: str) -> Tuple[str, str]:
    """Cleans up the format strings, avoids errors
    with MP3 files.
    """
    final = []
    for i, fs in enumerate((folder, track)):
        if fs.endswith(".mp3"):
            fs = fs[:-4]
        elif fs.endswith(".flac"):
            fs = fs[:-5]
        fs = fs.strip()

        # default to pre-chosen string if format is invalid
        if file_format in ("MP3", "Unknown") and (
            "bit_depth" in fs or "sampling_rate" in fs
        ):
            default = DEFAULT_FORMATS[file_format][i]
            logger.error(
                f"{RED}invalid format string for format {file_format}"
                f". defaulting to {default}"
            )
            fs = default
        final.append(fs)

    return tuple(final)


def _safe_get(d: dict, *keys, default=None):
    """A replacement for chained `get()` statements on dicts:
    >>> d = {'foo': {'bar': 'baz'}}
    >>> _safe_get(d, 'baz')
    None
    >>> _safe_get(d, 'foo', 'bar')
    'baz'
    """
    curr = d
    res = default
    for key in keys:
        res = curr.get(key, default)
        if res == default or not hasattr(res, "__getitem__"):
            return res
        else:
            curr = res
    return res


def _download_goodies(album_meta, dirn):
    """
    Download all goodies from an album if available.
    """
    try:
        for goody in album_meta.get("goodies", []):
            if not goody.get("url"):
                logger.warning("No URL found for the goody, skipping.")
                continue
            goody_name = sanitize_filename(clean_filename(f'{album_meta.get("title")} ({goody.get("id")}).pdf'))
            _get_extra(goody.get("url"), dirn, extra=goody_name)
    except:  # noqa
        logger.error(f"{RED}Error downloading goodies", exc_info=True)


def _clean_embed_art(dirn, settings: QobuzDLSettings = None):
    """
    Clean up the embedded artwork jpg file.
    """
    if settings.embed_art:
        embed_file = os.path.join(dirn, EMB_COVER_NAME)
        if os.path.isfile(embed_file):
            os.remove(embed_file)