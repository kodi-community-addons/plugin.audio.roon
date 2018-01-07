#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
    plugin.audio.roon
    Roon remote for Kodi
    roonserver.py
    Helper to communicate with Roon server using the json interface
'''

from utils import log_msg, log_exception, addon_setting
import requests

try:
    import simplejson as json
except Exception:
    import json


class RoonServer:
    ''' Class containing our helper methods'''
    _host = None
    _port = None

    def __init__(self, host, port, output_id):
        self._host = host
        self._port = port
        self.zone_id = output_id


    def zones(self):
        '''get all zones'''
        return self.send_request("zones")


    def browse_main(self):
        ''' get the browse main menu'''
        result = self.send_request("browseload", 
            {
                "hierarchy": "browse", 
                "pop_all": True
            })
        return result["items"] if result else []


    def browse(self, item_key, item_path, offset=0):
        ''' try to browse a Roon folder with item_key or the path '''
        result = self.browse_by_key(item_key, offset)
        if not result:
            # retry with the path workaround
            result = self.browse_by_path(item_path)
        if not result:
            result = []
        return result


    def browse_by_key(self, item_key, offset=0):
        ''' browse Roon content by item_key '''
        browse_params = {
                "hierarchy": "browse",
                "item_key": item_key,
                "offset": offset
            }
        return self.send_request("browseload", browse_params)

    
    def browse_by_path(self, item_path):
        ''' 
            browse Roon content by parsing the path
            workaround for the always changing item_keys
        '''
        result = None
        item_path = item_path.split("//")
        item_path = filter(None, item_path)
        for main_item in self.browse_main():
            if main_item["title"] == item_path[0]:
                # match found now we move further down the tree
                item_key = main_item["item_key"]
                for path_part in item_path[1:] + [""]:
                    result = self.browse_by_key(item_key)
                    if result:
                        for item in result["items"]:
                            if item["title"] == path_part:
                                item_key = item["item_key"]
                                break
                    else:
                        break
                break
        return result


    def next_track(self):
        """ Send next track command to zone. """
        return self.send_request("control", {"control":"next", "zone": self.zone_id} )

    def previous_track(self):
        """ Send next track command to zone. """
        return self.send_request("control", {"control":"previous", "zone": self.zone_id} )

    def pause_playback(self):
        """ Send next track command to zone. """
        return self.send_request("control", {"control":"pause", "zone": self.zone_id} )

    def start_playback(self):
        """ Send next track command to zone. """
        return self.send_request("control", {"control":"play", "zone": self.zone_id} )

    def stop_playback(self):
        """ Send next track command to zone. """
        return self.send_request("control", {"control":"stop", "zone": self.zone_id} )

    def shuffle(self, shuffle):
        """ Set shuffle state on zone """
        return self.change_settings("shuffle", shuffle)

    def toggle_repeat(self):
        """ Toggle repeat on zone """
        return self.change_settings("loop", "next")

    def repeat(self, repeat):
        """ 
            Set repeat on zone 
            Possible values: 'loop' | 'loop_one' | 'disabled' | 'next'
        """
        return self.change_settings("loop", repeat)


    def change_settings(self, setting, value):
        """ Set setting to device or zone """
        return self.send_request("change_settings", {"zone": self.zone_id, "setting": setting, "value": value} )


    def zone_details(self):
        ''' return zone details'''
        return self.send_request("zone", {"zone": self.zone_id})

    def set_volume_level(self, volume, method="absolute"):
        """ Send new volume_level to all outputs of zone """
        for output in self.zone_details()["outputs"]:
            output_id = output["output_id"]
            cur_vol = output["volume"]["value"]
            if method == "up":
                volume = cur_vol + volume
            elif method == "down":
                volume = cur_vol - volume
            self.send_request("change_volume", {"volume":volume, "output": output_id} )

    def volume_up(self):
        """ Send new volume_level to device. """
        return self.set_volume_level(5, "up")

    def volume_down(self):
        """ Send new volume_level to device. """
        return self.set_volume_level(5, "down")


    def send_request(self, endpoint, params=None):
        '''get info from json api'''
        result = {}
        url = "http://{}:{}/{}".format(self._host, self._port, endpoint)
        params = params if params else {}
        params["zone_or_output_id"] = self.zone_id
        try:
            response = requests.get(url, params=params, timeout=20)
            if response and response.content and response.status_code == 200:
                result = json.loads(response.content.decode('utf-8', 'replace'))
            else:
                log_msg("Invalid or empty reponse from server - endpoint: %s - server response: %s - %s" %
                        (endpoint, response.status_code, response.content))
                if "ZoneNotFound" in response.content:
                    addon_setting("zone_id", "")
        except Exception as exc:
            log_exception(__name__, exc)
            result = None
        return result

    def get_thumb(self, image_key):
        '''get thumb url from image_key'''
        if not image_key:
            return None
        try:
            url = 'http://{}:{}/image?image_key={}&width=500&height=500&scale=fit'.format(
                self._host, self._port, image_key)
            return url
        except KeyError:
            return None