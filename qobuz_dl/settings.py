class QobuzDLSettings:
    def __init__(self, **kwargs):
        # basic options
        self.email = kwargs.get('email')
        self.password = kwargs.get('password')
        self.default_folder = kwargs.get('default_folder', 'Qobuz Downloads')
        self.default_quality = kwargs.get('default_quality', 6)
        self.default_limit = kwargs.get('default_limit', 20)
        self.no_m3u = kwargs.get('no_m3u', False)
        self.albums_only = kwargs.get('albums_only', False)
        self.no_fallback = not kwargs.get('no_fallback', False)
        self.no_database = kwargs.get('no_database', False)
        self.app_id = kwargs.get('app_id')
        self.secrets = kwargs.get('secrets')
        self.folder_format = kwargs.get('folder_format')
        self.track_format = kwargs.get('track_format')
        self.smart_discography = kwargs.get('smart_discography', False)

        # tag options
        self.no_album_artist_tag = kwargs.get('no_album_artist_tag', False)
        self.no_album_title_tag = kwargs.get('no_album_title_tag', False)
        self.no_track_artist_tag = kwargs.get('no_track_artist_tag', False)
        self.no_track_title_tag = kwargs.get('no_track_title_tag', False)
        self.no_release_date_tag = kwargs.get('no_release_date_tag', False)
        self.no_media_type_tag = kwargs.get('no_media_type_tag', False)
        self.no_genre_tag = kwargs.get('no_genre_tag', False)
        self.no_track_number_tag = kwargs.get('no_track_number_tag', False)
        self.no_track_total_tag = kwargs.get('no_track_total_tag', False)
        self.no_disc_number_tag = kwargs.get('no_disc_number_tag', False)
        self.no_disc_total_tag = kwargs.get('no_disc_total_tag', False)
        self.no_composer_tag = kwargs.get('no_composer_tag', False)
        self.no_explicit_tag = kwargs.get('no_explicit_tag', False)
        self.no_copyright_tag = kwargs.get('no_copyright_tag', False)
        self.no_label_tag = kwargs.get('no_label_tag', False)
        self.no_upc_tag = kwargs.get('no_upc_tag', False)
        self.no_isrc_tag = kwargs.get('no_isrc_tag', False)

        # FLAC auto-fix Unset MD5s option
        self.fix_md5s = kwargs.get('fix_md5s', False)

        # cover options
        self.embed_art = kwargs.get('embed_art', False)
        self.cover_og_quality = kwargs.get('og_cover', False)
        self.no_cover = kwargs.get('no_cover', False)
        self.embedded_art_size = kwargs.get('embedded_art_size', '600')
        self.saved_art_size = kwargs.get('saved_art_size', 'org')

        # multiple disc option
        self.multiple_disc_prefix = kwargs.get('multiple_disc_prefix', 'CD')

    @staticmethod
    def from_arguments_configparser(arguments, config):
        """Creating Configuration Objects from Command Line Parameters and Configuration Files
        
        Args:
            arguments: Parsed command line arguments
            config: ConfigParser object
            
        Returns:
            QobuzDLSettings: Configuration object
        """
        # basic options
        kwargs = {
            'email': config["DEFAULT"]["email"],
            'password': config["DEFAULT"]["password"],
            'default_folder': arguments.directory or config["DEFAULT"]["default_folder"],
            'default_quality': arguments.quality or config["DEFAULT"]["default_quality"],
            'default_limit': arguments.limit or config["DEFAULT"]["default_limit"],
            'no_m3u': arguments.no_m3u or config.getboolean("DEFAULT", "no_m3u"),
            'albums_only': arguments.albums_only or config.getboolean("DEFAULT", "albums_only"),
            'no_fallback': arguments.no_fallback or config.getboolean("DEFAULT", "no_fallback"),
            'no_database': arguments.no_db or config.getboolean("DEFAULT", "no_database"),
            'app_id': config["DEFAULT"]["app_id"],
            'secrets': [s for s in config["DEFAULT"]["secrets"].split(",") if s],
            'folder_format': arguments.folder_format or config["DEFAULT"]["folder_format"],
            'track_format': arguments.track_format or config["DEFAULT"]["track_format"],
            'smart_discography': arguments.smart_discography or config.getboolean("DEFAULT", "smart_discography"),
            
            # cover options
            'embed_art': arguments.embed_art or config.getboolean("DEFAULT", "embed_art"),
            'og_cover': arguments.og_cover or config.getboolean("DEFAULT", "og_cover"),
            'no_cover': arguments.no_cover or config.getboolean("DEFAULT", "no_cover"),
            'embedded_art_size': arguments.embedded_art_size or config["DEFAULT"]["embedded_art_size"],
            'saved_art_size': arguments.saved_art_size or config["DEFAULT"]["saved_art_size"],
            
            # multiple disc option
            'multiple_disc_prefix': arguments.multiple_disc_prefix or config["DEFAULT"]["multiple_disc_prefix"],
            
            # FLAC auto-fix Unset MD5s option
            'fix_md5s': arguments.fix_md5s or config.getboolean("DEFAULT", "fix_md5s"),
            
            # tag options
            'no_album_artist_tag': arguments.no_album_artist_tag or config.getboolean("DEFAULT", "no_album_artist_tag"),
            'no_album_title_tag': arguments.no_album_title_tag or config.getboolean("DEFAULT", "no_album_title_tag"), 
            'no_track_artist_tag': arguments.no_track_artist_tag or config.getboolean("DEFAULT", "no_track_artist_tag"),
            'no_track_title_tag': arguments.no_track_title_tag or config.getboolean("DEFAULT", "no_track_title_tag"),
            'no_release_date_tag': arguments.no_release_date_tag or config.getboolean("DEFAULT", "no_release_date_tag"),
            'no_media_type_tag': arguments.no_media_type_tag or config.getboolean("DEFAULT", "no_media_type_tag"),
            'no_genre_tag': arguments.no_genre_tag or config.getboolean("DEFAULT", "no_genre_tag"),
            'no_track_number_tag': arguments.no_track_number_tag or config.getboolean("DEFAULT", "no_track_number_tag"),
            'no_track_total_tag': arguments.no_track_total_tag or config.getboolean("DEFAULT", "no_track_total_tag"),
            'no_disc_number_tag': arguments.no_disc_number_tag or config.getboolean("DEFAULT", "no_disc_number_tag"),
            'no_disc_total_tag': arguments.no_disc_total_tag or config.getboolean("DEFAULT", "no_disc_total_tag"),
            'no_composer_tag': arguments.no_composer_tag or config.getboolean("DEFAULT", "no_composer_tag"),
            'no_explicit_tag': arguments.no_explicit_tag or config.getboolean("DEFAULT", "no_explicit_tag"),
            'no_copyright_tag': arguments.no_copyright_tag or config.getboolean("DEFAULT", "no_copyright_tag"),
            'no_label_tag': arguments.no_label_tag or config.getboolean("DEFAULT", "no_label_tag"),
            'no_upc_tag': arguments.no_upc_tag or config.getboolean("DEFAULT", "no_upc_tag"),
            'no_isrc_tag': arguments.no_isrc_tag or config.getboolean("DEFAULT", "no_isrc_tag"),
        }
        
        return QobuzDLSettings(**kwargs)