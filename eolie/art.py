# Copyright (c) 2017-2018 Cedric Bellegarde <cedric.bellegarde@adishatz.org>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gdk, GdkPixbuf, Gio, GLib

from hashlib import sha256
from time import time
from urllib.parse import urlparse

from eolie.define import EOLIE_CACHE_PATH
from eolie.utils import remove_www


class Art:
    """
        Base art manager
    """

    __CACHE_DELTA = 43200

    def __init__(self):
        """
            Init base art
        """
        self.__use_cache = True
        self.__create_cache()

    def disable_cache(self):
        """
            Disable cache
        """
        self.__use_cache = False

    def save_artwork(self, uri, surface, suffix):
        """
            Save artwork for uri with suffix
            @param uri as str
            @param surface as cairo.surface
            @param suffix as str
        """
        try:
            filepath = self.get_path(uri, suffix)
            pixbuf = Gdk.pixbuf_get_from_surface(surface, 0, 0,
                                                 surface.get_width(),
                                                 surface.get_height())
            pixbuf.savev(filepath, "png", [None], [None])
        except Exception as e:
            print("Art::save_artwork():", e)

    def get_artwork(self, uri, suffix, scale_factor, width, heigth):
        """
            @param uri as str
            @param suffix as str
            @param scale factor as int
            @param width as int
            @param height as int
            @return cairo.surface
        """
        if uri is None:
            return None
        filepath = self.get_path(uri, suffix)
        try:
            if GLib.file_test(filepath, GLib.FileTest.IS_REGULAR):
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filepath,
                                                                 width,
                                                                 heigth,
                                                                 True)
                surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf,
                                                               scale_factor,
                                                               None)
                return surface
        except:
            pass
        return None

    def get_icon_theme_artwork(self, uri, ephemeral):
        """
            Get artwork from icon theme
            @param uri as str
            @param ephemeral as bool
            @return artwork as str/None
        """
        if ephemeral:
            return "user-not-tracked-symbolic"
        elif uri == "populars://":
            return "emote-love-symbolic"
        elif uri == "about://":
            return "applications-internet"
        else:
            return None

    def get_favicon_path(self, uri):
        """
            Return favicon cache path for uri
            @param uri as str/None
            @return str/None
        """
        if uri is None:
            return None
        for favicon_type in ["favicon", "favicon_alt"]:
            favicon_path = self.get_path(uri, favicon_type)
            if GLib.file_test(favicon_path, GLib.FileTest.IS_REGULAR):
                return favicon_path
        return None

    def get_path(self, uri, suffix):
        """
            Return cache image path
            @param uri as str
            @param suffix as str
            @return str/None
        """
        if uri is None:
            return None
        parsed = urlparse(uri)
        cached_uri = remove_www(parsed.netloc)
        cached_path = parsed.path.rstrip("/")
        if cached_path:
            cached_uri += cached_path
        encoded = sha256(cached_uri.encode("utf-8")).hexdigest()
        filepath = "%s/%s_%s.png" % (EOLIE_CACHE_PATH, encoded, suffix)
        return filepath

    def exists(self, uri, suffix):
        """
            Check if file exists and is cached
            @param uri as str
            @param suffix as str
            @return (exists as bool, cached as bool)
        """
        f = Gio.File.new_for_path(self.get_path(uri, suffix))
        exists = f.query_exists()
        if exists and self.__use_cache:
            info = f.query_info('time::modified',
                                Gio.FileQueryInfoFlags.NONE,
                                None)
            mtime = int(info.get_attribute_as_string('time::modified'))
            return (True, time() - mtime < self.__CACHE_DELTA)
        else:
            return (False, False)

    def vacuum(self):
        """
            Remove artwork older than 1 month
        """
        current_time = time()
        try:
            d = Gio.File.new_for_path(EOLIE_CACHE_PATH)
            children = d.enumerate_children("standard::name",
                                            Gio.FileQueryInfoFlags.NONE,
                                            None)
            for child in children:
                f = children.get_child(child)
                if child.get_file_type() == Gio.FileType.REGULAR:
                    info = f.query_info("time::modified",
                                        Gio.FileQueryInfoFlags.NONE,
                                        None)
                    mtime = info.get_attribute_uint64("time::modified")
                    if current_time - mtime > 2592000:
                        f.delete()
        except Exception as e:
            print("Art::vacuum():", e)

    @property
    def base_uri(self):
        """
            Get cache base uri
            @return str
        """
        return GLib.filename_to_uri(EOLIE_CACHE_PATH)

#######################
# PROTECTED           #
#######################

#######################
# PRIVATE             #
#######################
    def __create_cache(self):
        """
            Create cache dir
        """
        if not GLib.file_test(EOLIE_CACHE_PATH, GLib.FileTest.IS_DIR):
            try:
                GLib.mkdir_with_parents(EOLIE_CACHE_PATH, 0o0750)
            except Exception as e:
                print("Art::__create_cache():", e)
