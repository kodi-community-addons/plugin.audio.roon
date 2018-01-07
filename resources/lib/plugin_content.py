#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
    plugin.audio.roon
    Roon remote for Kodi
    plugin_content.py
    plugin entry point to browse media
'''

import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
from utils import log_msg, KODI_VERSION, log_exception, ADDON_ID, addon_setting
import urlparse
import urllib
import sys
from roonserver import RoonServer

PLUGIN_BASE = "plugin://%s/" % ADDON_ID
ADDON_HANDLE = int(sys.argv[1])


class PluginContent:
    '''Hidden plugin entry point providing some helper features'''
    roonserver = None
    addon = None

    def __init__(self):

        # initialize roonserver object - grab details from window props set by the service
        host = addon_setting("proxy_host")
        port = addon_setting("proxy_port")
        self.zone_id = addon_setting("zone_id")
        self.zone_name = addon_setting("zone_name")

        # open addon settings if server not yet set
        if not host or not port:
            xbmc.executebuiltin("Addon.OpenSettings(%s)" % ADDON_ID)
            xbmcplugin.endOfDirectory(handle=ADDON_HANDLE)
            return

        # init roonserver object
        self.roonserver = RoonServer(host, port, self.zone_id)
        
        if "select_zone" in sys.argv[2]:
            self.select_zone()
        elif not self.zone_id:
            xbmcplugin.endOfDirectory(handle=ADDON_HANDLE)
            self.select_zone()
        else:
            # show plugin listing
            try:
                params = dict(urlparse.parse_qsl(sys.argv[2].replace('?', '').decode("utf-8")))
                log_msg("plugin called with parameters: %s" % params, xbmc.LOGDEBUG)
                action = params.get("action","")
                if action == "browse":
                    self.browse(params)
                elif action == "action" or action == "load":
                    self.action(params)
                elif action == "show_actions":
                    self.show_actions(params)
                elif action == "input_prompt":
                    self.input_prompt(params)
                elif action == "osd":
                    self.osd()
                else:
                    self.main()
            except Exception as exc:
                log_exception(__name__, exc)
                xbmcplugin.endOfDirectory(handle=ADDON_HANDLE)


    def main(self):
        ''' show main listing '''
        base_details = { 
            "title": "Mainmenu", 
            "item_path": "",
            "artist": "",
            "album": "",
            "dbtype": "",
            "mediatype": "files",
            "icon": ""
            }
        xbmcplugin.setContent(ADDON_HANDLE, "files")
        items = self.roonserver.browse_main()
        for item in self.roonserver.browse_main():
            self.create_listitem(item, base_details)
        # add zone-select ListItem
        label = "Zone: %s" % self.zone_name
        url = "%s?action=select_zone" %PLUGIN_BASE
        listitem = xbmcgui.ListItem(label)
        listitem.setProperty("isPlayable", "false")
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE,
                                    url=url, listitem=listitem, isFolder=False)
        # add OSDListItem
        label = "OSD"
        url = "%s?action=osd" %PLUGIN_BASE
        listitem = xbmcgui.ListItem(label)
        listitem.setProperty("isPlayable", "false")
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE,
                                    url=url, listitem=listitem, isFolder=False)
        xbmcplugin.endOfDirectory(handle=ADDON_HANDLE)

    def input_prompt(self, pluginparams):
        ''' ask input before browsing (used for search) '''
        dialog = xbmcgui.Dialog()
        input = dialog.input("Enter text").decode("utf-8")
        del dialog
        browse_params = {
            "hierarchy": "browse",
            "item_key": pluginparams["item_key"],
            "input": input
        }
        result = self.roonserver.send_request("browseload", browse_params)
        if result:
            details = self.parse_folder_details(result["list"], pluginparams)
            xbmcplugin.setProperty(ADDON_HANDLE, 'FolderName', details["title"])
            for item in result["items"]:
                self.create_listitem(item, details)
            xbmcplugin.addSortMethod(ADDON_HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.endOfDirectory(handle=ADDON_HANDLE)


    def browse(self, pluginparams):
        '''main action, load correct function'''
        offset = int(pluginparams.get("offset", 0))
        result = self.roonserver.browse(pluginparams["item_key"], pluginparams["item_path"], offset)
        if result:
            details = self.parse_folder_details(result["list"], pluginparams)
            xbmcplugin.setContent(ADDON_HANDLE, details["mediatype"])
            xbmcplugin.setProperty(ADDON_HANDLE, 'FolderName', details["title"])
            for item in result["items"]:
                self.create_listitem(item, details)
            xbmcplugin.addSortMethod(ADDON_HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
            # add next page button if needed
            if details["count"] > (len(result["items"]) + offset):
                label = "Next page..."
                offset += len(result["items"])
                url = "%s?action=browse&item_key=%s&offset=%s&item_path=%s" % (
                        PLUGIN_BASE, pluginparams["item_key"], offset, pluginparams["item_path"])
                listitem = xbmcgui.ListItem(label)
                listitem.setProperty("isPlayable", "false")
                xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE,
                                            url=url, listitem=listitem, isFolder=True)

        xbmcplugin.endOfDirectory(handle=ADDON_HANDLE)


    def osd(self):
        # launch our special OSD dialog
        from osd import RoonOSD
        addon = xbmcaddon.Addon(ADDON_ID)
        addon_path = addon.getAddonInfo('path').decode("utf-8")
        del addon
        osd = RoonOSD("plugin-audio-roon-OSD.xml",
                                     addon_path, "Default", "1080i")
        osd.roon = self.roonserver
        osd.doModal()
        del osd


    def show_actions(self, pluginparams):
        ''' show actions for given Roon item'''
        xbmc.executebuiltin("ActivateWindow(busydialog")
        result = self.roonserver.browse(pluginparams["item_key"], pluginparams["item_path"])
        if result:
            actions = [item["title"] for item in result["items"]]
            dialog = xbmcgui.Dialog()
            ret = dialog.select(result["list"]["title"], actions)
            if ret != -1:
                selected_action = result["items"][ret]
                self.roonserver.browse_by_key(selected_action["item_key"])
            del dialog
        xbmc.executebuiltin("Dialog.Close(busydialog)")

    def action(self, pluginparams):
        ''' execute action for given Roon item'''
        result = self.roonserver.browse(pluginparams["item_key"], pluginparams["item_path"])
        xbmc.executebuiltin("Container.Refresh")


    def parse_folder_details(self, listdetails, pluginparams):
        ''' try to parse the details from the breadcrumb history and list details'''
        item_path = pluginparams.get("item_path","")
        details = listdetails
        details["item_path"] = item_path
        details["artist"] = ""
        details["album"] = ""
        details["mediatype"] = "files"
        item_path = item_path.split("//")
        item_path = filter(None, item_path)
        item_path_len = len(item_path)
        if listdetails["title"] == "Artists":
            # main artists listing
            details["mediatype"] = "artists"
        elif listdetails["title"] == "Albums":
            # main albums listing
            details["mediatype"] = "albums"
        elif listdetails["title"] == "Tracks":
            # main tracks listing
            details["mediatype"] = "songs"
        elif "Playlists" in item_path and item_path_len > 1 and not "TIDAL" in item_path:
            # tracks listing for Playlists
            details["mediatype"] = "songs"
        elif "Artists" in item_path:
            # albums or songs listing, but initiated from other library path (e.g. genres)
            path_pos = item_path.index("Artists") + 1
            path_parts = len(item_path[path_pos:])
            if path_parts == 1:
                # most likely album listing
                details["mediatype"] = "albums"
                details["artist"] = details["title"]
            else:
                # most likely songs listing for album
                details["mediatype"] = "songs"
                details["artist"] = details["subtitle"]
                details["album"] = listdetails["title"]
        elif "Albums" in item_path:
            # albums or songs listing, but initiated from other library path (e.g. genres)
            path_pos = item_path.index("Albums") + 1
            path_parts = len(item_path[path_pos:])
            if path_parts == 0:
                # most likely album listing
                details["mediatype"] = "albums"
                details["artist"] = details["title"]
            else:
                # most likely songs listing for album
                details["mediatype"] = "songs"
                details["artist"] = details["subtitle"]
                details["album"] = listdetails["title"]

        details["dbtype"] = details["mediatype"][:-1]
        details["icon"] = self.roonserver.get_thumb(listdetails["image_key"])
        return details


    def create_listitem(self, item, folderdetails):
        ''' create listitem from roon browse object'''
        is_folder = True
        title = item["title"]
        dbtype = folderdetails["dbtype"]
        artist = folderdetails["artist"]
        album = folderdetails["album"]

        item_type = item.get("hint","list")
        icon = self.roonserver.get_thumb(item["image_key"])
        if not icon:
            icon = folderdetails["icon"]
        item_path = folderdetails["item_path"]
        item_path += "%s//" % title
        listitem = xbmcgui.ListItem(title, iconImage=icon)
        args = {
            "item_key": item["item_key"],
            "item_path": item_path.encode("utf-8")
            }

        action = "browse"
        if "input_prompt" in item:
            action = "input_prompt"
            is_folder = True
        elif item_type == "list":
            is_folder = True
        elif item_type == "action_list":
            is_folder = False
            action = "show_actions"
            if not item.get("subtitle"):
                # this is an action button ?
                dbtype = ""
        elif item_type == "action":
            is_folder = False
            action = "action"
        else:
            dbtype = ""
            is_folder = False

        # set additional metadata
        if dbtype in ["song", "album", "artist"]:
            
            if dbtype == "album" and not artist and not album:
                artist = item["subtitle"]
                album = item["title"]
            elif dbtype == "album" and not artist:
                artist = item["subtitle"]
            elif dbtype == "album" and not album:
                album = item["title"]
            elif dbtype == "artist" and not artist:
                artist = item["title"]
            if dbtype == "song" and not artist and not album:
                artist = item["subtitle"]
                #album = item["title"]

            listitem.setInfo('music',
                 {
                     'title': title,
                     'artist': artist.replace(", ", " / "),
                     'album': album,
                     "mediatype": dbtype
                 })
            listitem.setProperty("DBYPE", dbtype)
        else:
            # all other items
            if item.get("subtitle"):
                label = "%s (%s)" %(title, item["subtitle"])
                listitem.setLabel(label)

        url = "{}?action={}&{}".format(PLUGIN_BASE, action, urllib.urlencode(args))

        contextmenu = []
        contextmenu.append(("Zone: %s" % self.zone_name,
                            "RunPlugin(%s?action=select_zone)" %PLUGIN_BASE))
        listitem.addContextMenuItems(contextmenu, True)
        listitem.setProperty("isPlayable", "false")
        xbmcplugin.addDirectoryItem(handle=ADDON_HANDLE,
                                    url=url, listitem=listitem, isFolder=is_folder)

            
    def select_zone(self):
        ''' select active zone '''
        xbmc.executebuiltin("ActivateWindow(busydialog")
        all_zones = self.roonserver.send_request("zones")
        if all_zones:
            all_zones = all_zones["zones"].values()
            all_zone_names = [item["display_name"] for item in all_zones]
        else:
            all_zone_names = []
            addon_setting("proxy_host","")
        dialog = xbmcgui.Dialog()
        ret = dialog.select("Select zone", all_zone_names)
        if ret != -1:
            selected_zone = all_zones[ret]
            addon_setting("zone_id", selected_zone["zone_id"])
            addon_setting("zone_name", selected_zone["display_name"])
        del dialog
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        xbmc.executebuiltin("Container.Refresh")
            