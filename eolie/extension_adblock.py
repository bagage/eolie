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

from urllib.parse import urlparse

from eolie.define import El
from eolie.database_adblock import DatabaseAdblock


class AdblockExtension:
    """
        Handle adblocking
    """

    def __init__(self, extension, settings):
        """
            Connect wanted signal
            @param extension as WebKit2WebExtension
            @param settings as Settings
        """
        self.__settings = settings
        self.__adblock = DatabaseAdblock()
        self.__not_blocked = []
        extension.connect("page-created", self.__on_page_created)

#######################
# PRIVATE             #
#######################
    def __on_page_created(self, extension, webpage):
        """
            Connect to send request
            @param extension as WebKit2WebExtension
            @param webpage as WebKit2WebExtension.WebPage
        """
        webpage.connect("send-request", self.__on_send_request)

    def __on_send_request(self, webpage, request, redirect):
        """
            Filter based on adblock db
            @param webpage as WebKit2WebExtension.WebPage
            @param request as WebKit2.URIRequest
            @param redirect as WebKit2WebExtension.URIResponse
        """
        uri = request.get_uri()
        parsed = urlparse(uri)
        if self.__settings.get_value("adblock") and\
                uri not in self.__not_blocked and\
                parsed.scheme in ["http", "https"] and\
                not El().adblock_exceptions.find_parsed(parsed):
            if self.__adblock.is_netloc_blocked(parsed.netloc) or\
                    self.__adblock.is_uri_blocked(uri, parsed.netloc):
                return True
            else:
                self.__not_blocked.append(uri)
        if self.__settings.get_value("do-not-track"):
            headers = request.get_http_headers()
            if headers is not None:
                headers.append("DNT", "1")
