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

from gi.repository import Gtk, GLib, WebKit2, Pango

from urllib.parse import urlparse
from gettext import gettext as _

from eolie.define import App
from eolie.popover_downloads import DownloadsPopover
from eolie.helper_passwords import PasswordsHelper
from eolie.logger import Logger


class ProgressBar(Gtk.ProgressBar):
    """
        Simple progress bar with width contraint
    """

    def __init__(self):
        Gtk.ProgressBar.__init__(self)
        self.set_property("valign", Gtk.Align.END)
        self.get_style_context().add_class("progressbar-button")

    def do_get_preferred_width(self):
        return (24, 24)


class ToolbarEnd(Gtk.Bin):
    """
        Toolbar end
    """

    def __init__(self, window, fullscreen):
        """
            Init toolbar
            @param window as Window
            @param fullscreen as bool
        """
        Gtk.Bin.__init__(self)
        self.__window = window
        self.__timeout_id = None
        self.__image_change_state_id = None
        self.set_hexpand(True)
        builder = Gtk.Builder()
        builder.add_from_resource("/org/gnome/Eolie/ToolbarEnd.ui")
        builder.connect_signals(self)
        self.__home_button = builder.get_object("home_button")
        self.__menu_button = builder.get_object("menu_button")
        self.__download_button = builder.get_object("download_button")
        self.__adblock_button = builder.get_object("adblock_button")
        self.__settings_button = builder.get_object("settings_button")
        self.__sync_button = builder.get_object("sync_button")
        self.__tls_button = builder.get_object("tls_button")
        if fullscreen:
            builder.get_object("fullscreen_button").show()
        self.__progress = ProgressBar()
        if App().download_manager.get():
            self.__progress.show()
        App().download_manager.connect("download-start",
                                       self.__on_download)
        App().download_manager.connect("download-finish",
                                       self.__on_download)
        overlay = builder.get_object("overlay")
        overlay.add_overlay(self.__progress)
        overlay.set_overlay_pass_through(self.__progress, True)
        self.add(builder.get_object("end"))

    def show_sync_button(self):
        """
            Show sync button allowing user to start sync
        """
        self.__sync_button.show()

    def show_tls_button(self, show):
        """
            Show TLS button allowing user to discard a certificate
            @param show as bool
        """
        if show:
            self.__tls_button.show()
        else:
            self.__tls_button.hide()

    def show_download(self, download):
        """
            Notify user about download
            @param download as WebKit2.Download
        """
        header = Gtk.Label()
        header.set_markup("<b>" + _("Downloading:") + "</b>")
        header.set_ellipsize(Pango.EllipsizeMode.END)
        header.show()
        destination = download.get_destination()
        try:
            uri = Gtk.Label.new(destination.split("/")[-1])
        except:
            uri = Gtk.Label.new(download.get_destination())
        uri.set_max_width_chars(30)
        uri.set_ellipsize(Pango.EllipsizeMode.END)
        uri.show()
        grid = Gtk.Grid()
        grid.set_margin_start(5)
        grid.set_margin_end(5)
        grid.set_margin_top(5)
        grid.set_margin_bottom(5)
        grid.set_orientation(Gtk.Orientation.VERTICAL)
        grid.show()
        grid.add(header)
        grid.add(uri)
        popover = Gtk.Popover.new()
        popover.get_style_context().add_class("dark")
        popover.add(grid)
        popover.set_modal(False)
        popover.set_relative_to(self.__download_button)
        popover.popup()
        GLib.timeout_add(2000, popover.destroy)

    def save_page(self):
        """
            Show a dialog allowing user to save current page
        """
        filechooser = Gtk.FileChooserNative.new(_("Save page"),
                                                self.__window,
                                                Gtk.FileChooserAction.SAVE,
                                                _("Save"),
                                                _("Cancel"))
        filechooser.connect("response", self.__on_save_response)
        filechooser.run()

    def save_images(self, uri, page_id):
        """
            Show a popover with all images for page id
            @param uri as str
            @param page_id as int
        """
        from eolie.popover_images import ImagesPopover
        popover = ImagesPopover(uri, page_id, self.__window)
        popover.set_relative_to(self.__download_button)
        popover.popup()

    def save_videos(self, page_id):
        """
            Show a popover with videos for page_id
            @param page_id as int
        """
        from eolie.menu_videos import VideosMenu
        menu = VideosMenu(page_id, self.__window)
        popover = Gtk.Popover.new_from_model(self.__download_button, menu)
        popover.set_modal(False)
        self.__window.register(popover)
        popover.connect("closed", self.__on_video_menu_popover_closed, menu)
        popover.popup()

    def move_control_in_menu(self, b):
        """
            Move home and download buttons in menu
            @param b as bool
        """
        if b:
            self.__download_button.hide()
            self.__home_button.hide()
            self.set_hexpand(False)
        else:
            self.__download_button.show()
            self.__home_button.show()
            self.set_hexpand(True)

    @property
    def download_button(self):
        """
            Get download button
            @return Gtk.ToogleButton
        """
        return self.__download_button

#######################
# PROTECTED           #
#######################
    def _on_download_button_toggled(self, button):
        """
            Show download popover
            @param button as Gtk.Button
        """
        self.__window.close_popovers()
        if not button.get_active():
            return
        popover = DownloadsPopover(self.__window)
        # We are relative to toolbar button, button can be in menu
        popover.set_relative_to(self.__download_button)
        popover.connect("closed", self.__on_popover_closed, button)
        popover.set_modal(False)
        self.__window.register(popover)
        popover.popup()

    def _on_sync_button_clicked(self, button):
        """
            Start sync
            @param button as Gtk.Button
        """
        helper = PasswordsHelper()
        helper.get_sync(self.__on_get_sync)
        button.hide()

    def _on_tls_button_clicked(self, button):
        """
            Do not accept TLS for this site by default
            @param button as Gtk.Button
        """
        button.hide()
        uri = self.__window.container.current.webview.uri
        App().websettings.set_accept_tls(uri, False)
        self.__window.container.close_view(self.__window.container.current)

    def _on_fullscreen_button_clicked(self, button):
        """
            Leave fullscreen mode
            @param button as Gtk.Button
        """
        self.__window.unfullscreen()

    def _on_home_button_clicked(self, button):
        """
            Go to home page
            @param button as Gtk.Button
        """
        self.__window.close_popovers()
        self.__window.container.current.webview.load_uri(App().start_page)

    def _on_menu_button_toggled(self, button):
        """
            Show settings menu
            @param button as Gtk.ToogleButton
        """
        self.__window.close_popovers()
        uri = self.__window.container.current.webview.uri
        if not button.get_active() or not uri:
            return
        from eolie.menu_toolbar import ToolbarMenu
        popover = ToolbarMenu(uri, self.__window, self)
        popover.set_relative_to(button)
        popover.set_modal(False)
        self.__window.register(popover)
        popover.connect("closed", self.__on_popover_closed, button)
        popover.popup()

    def _on_save_button_clicked(self, button):
        """
            Save current page
            @param button as Gtk.Button
        """
        button.get_ancestor(Gtk.Popover).hide()
        self.save_page()

    def _on_print_button_clicked(self, button):
        """
            Print current page
            @param button as Gtk.button
        """
        button.get_ancestor(Gtk.Popover).hide()
        action = self.__window.lookup_action("shortcut")
        action.activate(GLib.Variant("s", "print"))

#######################
# PRIVATE             #
#######################
    def __hide_progress(self):
        """
            Hide progress if needed
        """
        if self.__timeout_id is None:
            self.__progress.hide()

    def __update_progress(self, download_manager):
        """
            Update progress
        """
        fraction = 0.0
        nb_downloads = 0
        for download in download_manager.get():
            nb_downloads += 1
            fraction += download.get_estimated_progress()
        if nb_downloads:
            value = fraction / nb_downloads
            self.__progress.set_fraction(value)
            App().update_unity_badge(value)
        return True

    def __on_video_menu_popover_closed(self, popover, model):
        """
            Clean menu
            @param popover as Gtk.Popover
            @param model as Gio.Menu
        """
        # Let model activate actions, idle needed to action activate
        GLib.idle_add(model.clean)

    def __on_save_response(self, dialog, response_id):
        """
            Tell WebKit to save current page
            @param dialog as Gtk.NativeDialog
            @param response_id as int
        """
        if response_id == Gtk.ResponseType.ACCEPT:
            self.__window.container.current.webview.save_to_file(
                dialog.get_file(),
                WebKit2.SaveMode.MHTML,
                None,
                None)

    def __on_action_change_state(self, action, param, option):
        """
            Set adblock state
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
            @param option as str
        """
        action.set_state(param)
        App().settings.set_value(option, param)
        self.__window.container.current.webview.reload()

    def __on_trust_change_state(self, action, param):
        """
            Set trust state
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        App().settings.set_value("trust_websites", param)
        self.__window.container.current.webview.reload()

    def __on_popup_change_state(self, action, param):
        """
            Update popup block state
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        action.set_state(param)
        App().settings.set_value("popupblock", param)

    def __on_image_change_state(self, action, param):
        """
            Update image block state
            @param action as Gio.SimpleAction
            @param param as GLib.Variant
        """
        uri = self.__window.container.current.webview.uri
        parsed = urlparse(uri)
        if parsed.scheme in ["http", "https"]:
            action.set_state(param)
            if param.get_boolean():
                App().image_exceptions.add_exception(parsed.netloc)
            else:
                App().image_exceptions.remove_exception(parsed.netloc)

    def __on_download(self, download_manager, name=""):
        """
            Update progress bar
            @param download_manager as DownloadManager
            @param name as str (do not use this)
        """
        if download_manager.active:
            if self.__timeout_id is None:
                self.__progress.show()
                self.__timeout_id = GLib.timeout_add(1000,
                                                     self.__update_progress,
                                                     download_manager)
        elif self.__timeout_id is not None:
            self.__progress.set_fraction(1.0)
            App().update_unity_badge(1.0)
            GLib.timeout_add(1000, self.__hide_progress)
            GLib.source_remove(self.__timeout_id)
            self.__timeout_id = None
            self.__download_button.get_style_context().add_class("selected")

    def __on_popover_closed(self, popover, button):
        """
            Unlock focus
            @param popover as Gtk.Popover
            @param button as Gtk.Button
        """
        button.get_style_context().remove_class("selected")
        button.set_active(False)
        if self.__image_change_state_id is not None:
            self.__images_action.disconnect(self.__image_change_state_id)
            self.__image_change_state_id = None

    def __on_get_sync(self, attributes, password, uri, index, count):
        """
            Start sync
            @param attributes as {}
            @param password as str
            @param uri as None
            @param index as int
            @param count as int
        """
        try:
            App().sync_worker.new_session()
            App().sync_worker.login(attributes, password)
        except Exception as e:
            Logger.error("ToolbarEnd::__on_get_sync(): %s", e)
            self.__sync_button.show()
