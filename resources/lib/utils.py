#!/usr/bin/python
# -*- coding: utf-8 -*-

'''
    plugin.audio.roon
    Roon remote for Kodi
    utils.py
    Various helper methods
'''

import xbmc
import xbmcvfs
import xbmcaddon
import os
import stat
import sys
from traceback import format_exc


ADDON_ID = "plugin.audio.roon"
PLUGIN_BASE = "plugin://%s/" % ADDON_ID
KODI_VERSION = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
KODILANGUAGE = xbmc.getLanguage(xbmc.ISO_639_1)
DEBUG = False


def log_msg(msg, loglevel=xbmc.LOGNOTICE):
    '''log message to kodi log'''
    if DEBUG and loglevel == xbmc.LOGDEBUG:
        loglevel = xbmc.LOGNOTICE
    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    xbmc.log("%s --> %s" % (ADDON_ID, msg), level=loglevel)


def log_exception(modulename, exceptiondetails):
    '''helper to properly log an exception'''
    log_msg(format_exc(sys.exc_info()), xbmc.LOGDEBUG)
    log_msg("Exception in %s ! --> %s" % (modulename, exceptiondetails), xbmc.LOGWARNING)


def addon_setting(setting, value=None):
    '''get/set addon setting '''
    addon = xbmcaddon.Addon(ADDON_ID)
    if value != None:
        addon.setSetting(setting, value)
    else:
        value = addon.getSetting(setting)
    del addon
    return value
