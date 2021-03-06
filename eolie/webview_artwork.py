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

from gi.repository import GLib, WebKit2, Gio

from urllib.parse import urlparse

from eolie.define import App
from eolie.helper_task import TaskHelper
from eolie.utils import get_snapshot, resize_favicon, get_char_surface
from eolie.utils import remove_www


class WebViewArtwork:
    """
        Handle webview artwork: snapshot and favicon
    """

    def __init__(self):
        """
            Init class
        """
        self.__helper = TaskHelper()
        self.__snapshot_id = None
        self.__save_favicon_timeout_id = None
        self.__cancellable = Gio.Cancellable()
        self.__initial_uri = None
        self.__favicon_width = {}
        self.__current_netloc = None
        self.connect("notify::uri", self.__on_uri_changed)

    def set_favicon(self):
        """
            Set favicon based on current webview favicon
        """
        if self.ephemeral or\
                self.error or\
                self.current_event != WebKit2.LoadEvent.FINISHED:
            return

        self.__set_favicon_from_surface(
            self.get_favicon(),
            self.uri,
            self.__initial_uri)

    def set_current_favicon(self):
        """
            Set favicon based on current webview favicon
            Use this for JS update (do not update initial uri)
        """
        self.__set_favicon_from_surface(
            self.get_favicon(),
            self.uri,
            None)

#######################
# PROTECTED           #
#######################
    def _on_load_changed(self, webview, event):
        """
            Update sidebar/urlbar
            @param webview as WebView
            @param event as WebKit2.LoadEvent
        """
        parsed = urlparse(self.uri)
        if event == WebKit2.LoadEvent.STARTED:
            self.__cancellable.cancel()
            self.__cancellable.reset()
            if parsed.scheme in ["http", "https"]:
                self.__initial_uri = self.uri.rstrip('/')
            else:
                self.__initial_uri = None
        elif event == WebKit2.LoadEvent.FINISHED:
            is_http = parsed.scheme in ["http", "https"]
            if self.__snapshot_id is not None:
                GLib.source_remove(self.__snapshot_id)
            self.__snapshot_id = GLib.timeout_add(2500,
                                                  self.__set_snapshot,
                                                  is_http)
            self.set_favicon()
            self.__current_netloc = parsed.netloc or None

#######################
# PRIVATE             #
#######################
    def __set_snapshot(self, save):
        """
            Set webpage preview
            @param save as bool
        """
        self.__snapshot_id = None
        self.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                          WebKit2.SnapshotOptions.NONE,
                          self.__cancellable,
                          get_snapshot,
                          self.__on_snapshot,
                          save,
                          True)

    def __set_favicon_from_surface(self, surface, uri, initial_uri):
        """
            Set favicon for surface
            @param favicon_db as WebKit2.FaviconDatabase
            @param result as Gio.AsyncResult
            @param uri as str
            @param initial_uri as str
        """
        resized = None
        # Save webview favicon
        if surface is not None:
            favicon_width = surface.get_width()
            if uri not in self.__favicon_width.keys() or\
                    favicon_width >= self.__favicon_width[uri]:
                if self.__save_favicon_timeout_id is not None:
                    GLib.source_remove(self.__save_favicon_timeout_id)
                    self.__save_favicon_timeout_id = None
                self.__favicon_width[uri] = favicon_width
                resized = resize_favicon(surface)
                favicon_type = "favicon"
        else:
            netloc = remove_www(urlparse(uri).netloc)
            if netloc:
                resized = App().art.get_favicon(uri,
                                                self.get_scale_factor())
                if resized is None:
                    resized = get_char_surface(netloc[0])
                favicon_type = "favicon_alt"

        # We wait for a better favicon
        if resized is not None and uri == self.uri:
            self.__save_favicon_timeout_id = GLib.timeout_add(
                500,
                self.__save_favicon_to_cache,
                resized,
                uri,
                initial_uri,
                favicon_type)

    def __save_favicon_to_cache(self, surface, uri, initial_uri, favicon_type):
        """
            Save favicon to cache
            @param surface as cairo.Surface
            @param uri as str
            @param initial_uri as str
            @param favicon_type as str
        """
        self.__save_favicon_timeout_id = None
        self.emit("favicon-changed", surface)
        # Save favicon for URI
        if not App().art.exists(uri, favicon_type):
            self.__helper.run(App().art.save_artwork,
                              uri,
                              surface,
                              favicon_type)
        # Save favicon for initial URI
        if initial_uri is not None and\
                not App().art.exists(initial_uri, favicon_type):
            striped_uri = uri.rstrip("/")
            if initial_uri != striped_uri:
                self.__helper.run(App().art.save_artwork,
                                  initial_uri,
                                  surface,
                                  favicon_type)

    def __on_uri_changed(self, webview, param):
        """
            Handle JS updates
            @param webview as WebKit2.WebView
            @param param as GObject.ParamSpec
        """
        if not webview.is_loading() and not webview.ephemeral:
            self.__initial_uri = None
            if self.__snapshot_id is not None:
                GLib.source_remove(self.__snapshot_id)
            self.__snapshot_id = GLib.timeout_add(2500,
                                                  self.__set_snapshot,
                                                  True)

    def __on_snapshot(self, surface, save, first_pass):
        """
            Cache snapshot
            @param surface as cairo.Surface
            @param uri as str
            @param save as bool
            @param first_pass as bool
        """
        # The 32767 limit on the width/height dimensions
        # of an image surface is new in cairo 1.10,
        # try with WebKit2.SnapshotRegion.VISIBLE
        if surface is None:
            if first_pass:
                self.get_snapshot(WebKit2.SnapshotRegion.VISIBLE,
                                  WebKit2.SnapshotOptions.NONE,
                                  self.__cancellable,
                                  get_snapshot,
                                  self.__on_snapshot,
                                  save,
                                  False)
            return
        self.emit("snapshot-changed", surface)
        if not save or self.error:
            return
        uri = self.uri
        # We also cache initial URI
        uris = [uri.rstrip("/")]
        if self.__initial_uri is not None and\
                self.__initial_uri not in uris:
            uris.append(self.__initial_uri)
        for uri in uris:
            exists = App().art.exists(uri, "start")
            if not exists:
                App().art.save_artwork(uri, surface, "start")
