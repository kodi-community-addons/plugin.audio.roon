#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
    plugin.audio.roon
    osd.py
    Special window to display an OSD for remote control of zone player
'''

import threading
import thread
import xbmc
import xbmcgui
from utils import log_msg, log_exception
from metadatautils import MetadataUtils
from roonserver import RoonServer


class RoonOSD(xbmcgui.WindowXMLDialog):
    ''' Special OSD to control Roon zone'''
    update_thread = None
    roon = None
    is_playing = True
    shuffle_state = False
    repeat_state = "off"

    def __init__(self, *args, **kwargs):
        self.metadatautils = MetadataUtils()
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):
        '''triggers on initialization of the dialog'''
        if not self.roon:
            host = addon_setting("proxy_host")
            port = addon_setting("proxy_port")
            zone_id = addon_setting("zone_id")
            self.roon = RoonServer(host, port, zone_id)
        self.update_thread = RoonOSDUpdateThread()
        self.update_thread.set_dialog(self)
        self.update_thread.start()

    def onAction(self, action):
        '''triggers on kodi navigation events'''
        action_id = action.getId()
        log_msg("onAction: %s" % action_id)
        if action_id in (9, 10, 92, 216, 247, 257, 275, 61467, 61448, 13):
            self.close_dialog()
        elif action_id in (12, 68, 79, 229):
            self.toggle_playback()
        elif action_id in (184, 14, 97):
            self.roon.next_track()
        elif action_id in (185, 15, 98):
            self.roon.previous_track()

    def close_dialog(self):
        '''stop background thread and close the dialog'''
        self.update_thread.stop_running()
        #self.roon.pause_playback()
        self.metadatautils.close()
        self.close()

    def onClick(self, control_id):
        '''Kodi builtin: triggers if window is clicked'''
        if control_id == 3201:
            self.roon.previous_track()
        elif control_id == 3203:
            self.toggle_playback()
        elif control_id == 3204:
            self.roon.next_track()
        elif control_id == 3206 and self.shuffle_state:
            self.roon.shuffle(False)
        elif control_id == 3206 and not self.shuffle_state:
            self.roon.shuffle(True)
        elif control_id == 3208:
            self.roon.toggle_repeat()

    def toggle_playback(self):
        '''toggle play/pause'''
        if self.is_playing:
            self.is_playing = False
            self.getControl(3202).setEnabled(False)
            self.roon.pause_playback()
        else:
            self.is_playing = True
            self.getControl(3202).setEnabled(True)
            self.roon.start_playback()
    
class RoonOSDUpdateThread(threading.Thread):
    '''Background thread to complement our OSD dialog,
    fills the listing while UI keeps responsive'''
    active = True
    dialog = None
    search_string = ""
    

    def __init__(self, *args):
        log_msg("RoonOSDUpdateThread Init")
        threading.Thread.__init__(self, *args)

    def stop_running(self):
        '''stop thread end exit'''
        self.active = False

    def set_dialog(self, dialog):
        '''set the active dialog to perform actions'''
        self.dialog = dialog

    def run(self):
        '''Main run loop for the background thread'''
        last_title = ""
        last_changed = ""
        monitor = xbmc.Monitor()
        while not monitor.abortRequested() and self.active:
            cur_playback = self.dialog.roon.zone_details()
            if cur_playback and cur_playback["last_changed"] != last_changed:
                # player was updated
                last_changed = cur_playback["last_changed"]

                if cur_playback["settings"]["shuffle"] != self.dialog.shuffle_state:
                    self.toggle_shuffle(cur_playback["settings"]["shuffle"])
                
                if cur_playback["settings"]["loop"] != self.dialog.repeat_state:
                    self.set_repeat(cur_playback["settings"]["loop"])
                
                if cur_playback["state"] != self.dialog.is_playing:
                    self.toggle_playstate(cur_playback["state"])

                trackdetails = cur_playback.get("now_playing")
                if not trackdetails:
                    self.clear_info()
                else:
                    cur_title = trackdetails["one_line"]["line1"]
                    if cur_title != last_title:
                        last_title = cur_title
                        self.update_info(trackdetails)
            monitor.waitForAbort(1)

        del monitor


    def toggle_playstate(self, value):
        '''toggle pause/play'''
        is_playing = value == "playing"
        self.dialog.is_playing = is_playing
        self.dialog.getControl(3202).setEnabled(is_playing)

    def toggle_shuffle(self, value):
        '''toggle shuffle'''
        self.dialog.shuffle_state = value
        self.dialog.getControl(3205).setEnabled(value)

    def set_repeat(self, value):
        '''set repeat state'''
        self.dialog.repeat_state = value
        self.dialog.getControl(3207).setLabel(value)

    def clear_info(self):
        '''clear osd info labels'''
        self.dialog.getControl(3110).setImage("")
        # set track title
        self.dialog.getControl(3111).setLabel("")
        # set artist label
        self.dialog.getControl(3112).setLabel("")
        # set album label
        self.dialog.getControl(3113).setLabel("")
        # set genre label
        self.dialog.getControl(3114).setLabel("")
        # set rating label
        self.dialog.getControl(3115).setLabel("")
        # clear art
        self.dialog.getControl(3300).setImage("special://home/addons/plugin.audio.roon/fanart.jpg")
        self.dialog.getControl(3301).setLabel("")
        self.dialog.getControl(3303).setImage("")
        self.dialog.getControl(3304).setImage("")
        self.dialog.getControl(3305).setImage("")
        self.dialog.getControl(3306).setImage("")
        self.dialog.getControl(3307).setImage("")


    def update_info(self, track=None):
        '''scrape results for search query'''

        # set cover image
        thumb = self.dialog.roon.get_thumb(track["image_key"])
        self.dialog.getControl(3110).setImage(thumb)

        # set track title
        lbl_control = self.dialog.getControl(3111)
        title = track["three_line"]["line1"]
        lbl_control.setLabel(title)

        # set artist label
        lbl_control = self.dialog.getControl(3112)
        artist = " / ".join(track["three_line"]["line2"].split(", "))
        lbl_control.setLabel(artist)

        # set album label
        lbl_control = self.dialog.getControl(3113)
        album = track["three_line"]["line3"]
        lbl_control.setLabel(album)

        # get additional artwork and metadata
        artwork = self.dialog.metadatautils.get_music_artwork(artist, album, title)
        fanart = artwork["art"].get("fanart", "special://home/addons/plugin.audio.roon/fanart.jpg")
        self.dialog.getControl(3300).setImage(fanart)
        efa = artwork["art"].get("extrafanart", "")
        self.dialog.getControl(3301).setLabel(efa)
        clearlogo = artwork["art"].get("clearlogo", "")
        self.dialog.getControl(3303).setImage(clearlogo)
        banner = artwork["art"].get("banner", "")
        self.dialog.getControl(3304).setImage(banner)
        albumthumb = artwork["art"].get("albumthumb", "")
        self.dialog.getControl(3305).setImage(albumthumb)
        artistthumb = artwork["art"].get("artistthumb", "")
        self.dialog.getControl(3306).setImage(artistthumb)
        discart = artwork["art"].get("discart", "disc.png")
        self.dialog.getControl(3307).setImage(discart)
        # set genre label
        lbl_control = self.dialog.getControl(3114)
        genre = " / ".join(artwork.get("genre", []))
        lbl_control.setLabel(genre)

        # set rating label
        lbl_control = self.dialog.getControl(3115)
        rating = artwork.get("rating")
        lbl_control.setLabel(rating)


