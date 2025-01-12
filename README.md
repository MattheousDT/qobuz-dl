# qobuz-dl modified version

## Intro
This is a modified version of qobuz-dl, new features and fixes are added.
- Refactored the tags function to support more tags, as well as all tags being configurable.
- ```folder_format``` and ```track_format``` supports more variables.
- Add fix md5 checksum option for FLAC.
- Multiple discs release allows saving to a single directory and supports the use of special filename templates for multiple discs.

## Install
```bash
pip3 install git+https://github.com/xwell/qobuz-dl.git
```

## Usage
```
qobuz-dl dl [URL] [OPTIONS]
```
**more options:**
```
usage: qobuz-dl dl [-h] [-d PATH] [-q int] [--albums-only] [--no-m3u] [--no-fallback] [--no-db] [-ff PATTERN] [-tf PATTERN] [-s] [--no-album-artist-tag] [--no-album-title-tag] [--no-track-artist-tag]
                   [--no-track-title-tag] [--no-release-date-tag] [--no-media-type-tag] [--no-genre-tag] [--no-track-number-tag] [--no-track-total-tag] [--no-disc-number-tag] [--no-disc-total-tag]
                   [--no-composer-tag] [--no-explicit-tag] [--no-copyright-tag] [--no-label-tag] [--no-upc-tag] [--no-isrc-tag] [--fix-md5s] [-e] [--og-cover] [--no-cover]
                   [--embedded-art-size {50,100,150,300,600,max,org}] [--saved-art-size {50,100,150,300,600,max,org}] [--multiple-disc-prefix PREFIX] [--multiple-disc-one-dir]
                   [--multiple-disc-track-format FORMAT]
                   SOURCE [SOURCE ...]

Download by album/track/artist/label/playlist/last.fm-playlist URL.

positional arguments:
  SOURCE                one or more URLs (space separated) or a text file

options:
  -h, --help            show this help message and exit
  -d PATH, --directory PATH
                        directory for downloads (default: "QobuzDownloads")
  -q int, --quality int
                        audio "quality" (5, 6, 7, 27) [320, LOSSLESS, 24B<=96KHZ, 24B>96KHZ] (default: 27)
  --albums-only         don't download singles, EPs and VA releases
  --no-m3u              don't create .m3u files when downloading playlists
  --no-fallback         disable quality fallback (skip releases not available in set quality)
  --no-db               don't call the database
  -ff PATTERN, --folder-format PATTERN
                        pattern for formatting folder names, e.g "{album_artist} - {album_title} ({year}) {{{barcode}}}". available keys: album_id, album_url, album_title, album_title, album_artist,
                        album_genre, album_composer, label, copyright, upc, barcode, release_date, year, media_type, format, bit_depth, sampling_rate, album_version, disc_count, track_count. Note1:
                        {album_title}, {track_title} will contain version information if available. Note2: {album_title_base}, {track_title_base} will contain only the title, Note3: {track_title},
                        {track_title_base} is only available if the given url is a track url. Cannot contain characters used by the system, which includes /:<>
  -tf PATTERN, --track-format PATTERN
                        pattern for formatting track names. e.g "{track_number} - {track_title}" available keys: album_title, album_title_base, album_artist, track_id, track_artist, track_composer,
                        track_number, isrc, bit_depth, sampling_rate, track_title, track_title_base version, year, disc_number, release_date. Note1: {album_title}, {track_title} will contain version
                        information if available. Note2: {album_title_base}, {track_title_base} will contain only the title. Cannot contain characters used by the system, which includes /:<>
  -s, --smart-discography
                        Try to filter out spam-like albums when requesting an artist's discography, and other optimizations. Filters albums not made by requested artist, and deluxe/live/collection
                        albums. Gives preference to remastered albums, high bit depth/dynamic range, and low sampling rates (to save space).

tag options:
  --no-album-artist-tag
                        don't add album artist tag
  --no-album-title-tag  don't add album title tag
  --no-track-artist-tag
                        don't add track artist tag
  --no-track-title-tag  don't add track title tag
  --no-release-date-tag
                        don't add release date tag
  --no-media-type-tag   don't add media type tag
  --no-genre-tag        don't add genre tag
  --no-track-number-tag
                        don't add track number tag
  --no-track-total-tag  don't add total tracks tag
  --no-disc-number-tag  don't add disc number tag
  --no-disc-total-tag   don't add total discs tag
  --no-composer-tag     don't add composer tag
  --no-explicit-tag     don't add explicit advisory tag
  --no-copyright-tag    don't add copyright tag
  --no-label-tag        don't add label tag
  --no-upc-tag          don't add UPC/barcode tag
  --no-isrc-tag         don't add ISRC tag

FLAC options:
  --fix-md5s            fix FLAC MD5 checksums

cover artwork options:
  -e, --embed-art       embed cover art into audio files
  --og-cover            download cover art in its original quality (bigger file). No longer available, recommended use: --embedded-art-size and --saved-art-size
  --no-cover            don't download cover art
  --embedded-art-size {50,100,150,300,600,max,org}
                        size of embedded artwork (default: 600)
  --saved-art-size {50,100,150,300,600,max,org}
                        size of saved artwork (default: org)

multiple disc options:
  --multiple-disc-prefix PREFIX
                        Setting folder prefix for multiple discs album (default: CD) If the album has multiple discs(media_count > 1), the album's tracks will be saved by folder. The names of the
                        folders: '{prefix} {media_number}', eg: 'CD 01'
  --multiple-disc-one-dir
                        store multiple disc releases in one directory
  --multiple-disc-track-format FORMAT
                        track format for multiple disc releases (default: "{disc_number}.{track_number} - {track_title}")
```

---
The original document is below.
---

# qobuz-dl
Search, explore and download Lossless and Hi-Res music from [Qobuz](https://www.qobuz.com/).
[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=VZWSWVGZGJRMU&source=url)

## Features

* Download FLAC and MP3 files from Qobuz
* Explore and download music directly from your terminal with **interactive** or **lucky** mode
* Download albums, tracks, artists, playlists and labels with **download** mode
* Download music from last.fm playlists (Spotify, Apple Music and Youtube playlists are also supported through this method)
* Queue support on **interactive** mode
* Effective duplicate handling with own portable database
* Support for albums with multiple discs
* Support for M3U playlists
* Downloads URLs from text file
* Extended tags
* And more

## Getting started

> You'll need an **active subscription**

#### Install qobuz-dl with pip
##### Linux / MAC OS
```
pip3 install --upgrade qobuz-dl
```
##### Windows
```
pip3 install windows-curses
pip3 install --upgrade qobuz-dl
```
#### Run qobuz-dl and enter your credentials
##### Linux / MAC OS
```
qobuz-dl
```
##### Windows
```
qobuz-dl.exe
```

> If something fails, run `qobuz-dl -r` to reset your config file.

## Examples

### Download mode
Download URL in 24B<96khz quality
```
qobuz-dl dl https://play.qobuz.com/album/qxjbxh1dc3xyb -q 7
```
Download multiple URLs to custom directory
```
qobuz-dl dl https://play.qobuz.com/artist/2038380 https://play.qobuz.com/album/ip8qjy1m6dakc -d "Some pop from 2020"
```
Download multiple URLs from text file
```
qobuz-dl dl this_txt_file_has_urls.txt
```
Download albums from a label and also embed cover art images into the downloaded files
```
qobuz-dl dl https://play.qobuz.com/label/7526 --embed-art
```
Download a Qobuz playlist in maximum quality
```
qobuz-dl dl https://play.qobuz.com/playlist/5388296 -q 27
```
Download all the music from an artist except singles, EPs and VA releases
```
qobuz-dl dl https://play.qobuz.com/artist/2528676 --albums-only
```

#### Last.fm playlists
> Last.fm has a new feature for creating playlists: you can create your own based on the music you listen to or you can import one from popular streaming services like Spotify, Apple Music and Youtube. Visit: `https://www.last.fm/user/<your profile>/playlists` (e.g. https://www.last.fm/user/vitiko98/playlists) to get started.

Download a last.fm playlist in the maximum quality
```
qobuz-dl dl https://www.last.fm/user/vitiko98/playlists/11887574 -q 27
```

Run `qobuz-dl dl --help` for more info.

### Interactive mode
Run interactive mode with a limit of 10 results
```
qobuz-dl fun -l 10
```
Type your search query
```
Logging...
Logged: OK
Membership: Studio


Enter your search: [Ctrl + c to quit]
- fka twigs magdalene
```
`qobuz-dl` will bring up a nice list of releases. Now choose whatever releases you want to download (everything else is interactive).

Run `qobuz-dl fun --help` for more info.

### Lucky mode
Download the first album result
```
qobuz-dl lucky playboi carti die lit
```
Download the first 5 artist results
```
qobuz-dl lucky joy division -n 5 --type artist
```
Download the first 3 track results in 320 quality
```
qobuz-dl lucky eric dolphy remastered --type track -n 3 -q 5
```
Download the first track result without cover art
```
qobuz-dl lucky jay z story of oj --type track --no-cover
```

Run `qobuz-dl lucky --help` for more info.

### Other
Reset your config file
```
qobuz-dl -r
```

By default, `qobuz-dl` will skip already downloaded items by ID with the message `This release ID ({item_id}) was already downloaded`. To avoid this check, add the flag `--no-db` at the end of a command. In extreme cases (e.g. lost collection), you can run `qobuz-dl -p` to completely reset the database.

## Usage
```
usage: qobuz-dl [-h] [-r] {fun,dl,lucky} ...

The ultimate Qobuz music downloader.
See usage examples on https://github.com/vitiko98/qobuz-dl

optional arguments:
  -h, --help      show this help message and exit
  -r, --reset     create/reset config file
  -p, --purge     purge/delete downloaded-IDs database

commands:
  run qobuz-dl <command> --help for more info
  (e.g. qobuz-dl fun --help)

  {fun,dl,lucky}
    fun           interactive mode
    dl            input mode
    lucky         lucky mode
```

## Module usage 
Using `qobuz-dl` as a module is really easy. Basically, the only thing you need is `QobuzDL` from `core`.

```python
import logging
from qobuz_dl.core import QobuzDL

logging.basicConfig(level=logging.INFO)

email = "your@email.com"
password = "your_password"

qobuz = QobuzDL()
qobuz.get_tokens() # get 'app_id' and 'secrets' attrs
qobuz.initialize_client(email, password, qobuz.app_id, qobuz.secrets)

qobuz.handle_url("https://play.qobuz.com/album/va4j3hdlwaubc")
```

Attributes, methods and parameters have been named as self-explanatory as possible.

## A note about Qo-DL
`qobuz-dl` is inspired in the discontinued Qo-DL-Reborn. This tool uses two modules from Qo-DL: `qopy` and `spoofer`, both written by Sorrow446 and DashLt.
## Disclaimer
* This tool was written for educational purposes. I will not be responsible if you use this program in bad faith. By using it, you are accepting the [Qobuz API Terms of Use](https://static.qobuz.com/apps/api/QobuzAPI-TermsofUse.pdf).
* `qobuz-dl` is not affiliated with Qobuz
