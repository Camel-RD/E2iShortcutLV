# -*- coding: utf-8 -*-
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, RetHost
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser 
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist

from datetime import datetime, tzinfo, timedelta, date
import time
import random
try:    import json
except Exception: import simplejson as json
from Components.config import config, ConfigText, ConfigSelection, ConfigYesNo, getConfigListEntry

config.plugins.iptvplayer.shortcut_login = ConfigText(default='', fixed_size=False)
config.plugins.iptvplayer.shortcut_password = ConfigText(default='', fixed_size=False)
config.plugins.iptvplayer.shortcut_quality = ConfigSelection(default = "hd", choices = [ ("hd", "hd"), ("hq", "hq"), ("mq", "mq"), ("lq", "lq") ])

config.plugins.iptvplayer.shortcut_token = ConfigText(default='', fixed_size=False)
config.plugins.iptvplayer.shortcut_uid = ConfigText(default='', fixed_size=False)
config.plugins.iptvplayer.shortcut_last_loggin = ConfigText(default='', fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("login:", config.plugins.iptvplayer.shortcut_login))
    optionList.append(getConfigListEntry("password:", config.plugins.iptvplayer.shortcut_password))
    optionList.append(getConfigListEntry("quality:", config.plugins.iptvplayer.shortcut_quality))
    return optionList


def isEmpty(param):
    if param is None or param == "":
        return True

def dateToDateTime(dt):
    return datetime.combine(dt, datetime.min.time())

def dateTounixTS(date):
    return int((date - datetime(1970,1,1)).total_seconds())
    
    
def dateFromUnix(string):
    return datetime.utcfromtimestamp(string)


def dateFromLocalToUtc(local_datetime):
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
    return local_datetime - offset


def dateFromUtcToLocal(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset

def dateFromString(string, fmt):
    try:
        res = datetime.strptime(string, fmt)
    except Exception:
        res = datetime(*(time.strptime(string, fmt)[0:6]))
    return res

def setToken(token):
    config.plugins.iptvplayer.shortcut_token.value = token
    config.plugins.iptvplayer.shortcut_token.save()


def setUID(uid):
    config.plugins.iptvplayer.shortcut_uid.value = uid
    config.plugins.iptvplayer.shortcut_uid.save()

def getLastLoggedIn():
    lastlogin = config.plugins.iptvplayer.shortcut_last_loggin.value
    if isEmpty(lastlogin): lastlogin = '2000-01-01 00:00:00'
    return dateFromString(lastlogin, '%Y-%m-%d %H:%M:%S')

def setLastLoggedIn(date):
    date_str = date.strftime("%Y-%m-%d %H:%M:%S")
    config.plugins.iptvplayer.shortcut_last_loggin.value = date_str
    config.plugins.iptvplayer.shortcut_last_loggin.save()


def toQualityX(quality): 
    if isEmpty(quality): quality = 'hd'
    if quality == 'hd': quality = "0-hd"
    elif quality == 'hq': quality = "1-hq"
    elif quality == 'mq': quality = "2-mq"
    elif quality == 'lq': quality = "3-lq"
    return quality


def get_unique_id():
    uid = config.plugins.iptvplayer.shortcut_uid.value
    if not isEmpty(uid):
        return uid

    digits = '0123456789'
    letters = 'abcdef'
    all_chars = digits + letters
    length = 16
    val = None
    while True:
        val = ''.join(random.choice(all_chars) for i in range(length))
        if not val.isdigit():
            break
    setUID(val)
    return val


def gettytul():
    return 'https://shortcut.lv/'


class Cache():
    cached_channels = []
    cached_epg = {}
    def __init__(self):
        pass


class Shortcut(CBaseHostClass):
    
    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = "https://shortcut.lv/"
        self.DEFAULT_ICON_URL = ""
        self.MENU_ITEMS={}
        self.API_BASEURL = "https://manstv.lattelecom.tv"
        self.API_ENDPOINT = self.API_BASEURL + "/api/v1.7"
        self.USER_AGENT = 'Shortcut.lv for Android TV v1.11.9 / Dalvik/2.1.0 (Linux; U; Android 7.1.1; sdk_google_atv_x86 Build/NYC)'

        self.defaultParams = {'header': {'User-Agent' : self.USER_AGENT, 'Connection': 'keep-alive'}}
        

    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        addParams['header'] = MergeDicts(addParams['header'], self.defaultParams['header'])
        return self.cm.getPage(url, addParams, post_data)


    def get_channels(self):
        if len(Cache.cached_channels) > 0:
            return Cache.cached_channels

        url = self.API_ENDPOINT + '/get/content/packages?include=channels'

        response_status, response_text = self.getPage(url)

        if not response_status:
            printDBG("[Shortcut.lv] Got incorrect response code while requesting channel list. Text: " + response_text)
            return []

        json_object = None
        try:
            json_object = json.loads(response_text)
        except ValueError, e:
            printDBG("[Shortcut.lv] Did not receive json, something wrong: " + response_text)
            return []

        if "included" not in json_object:
            printDBG("[Shortcut.lv] Invalid response: " + response_text)
            return []

        channels = []
        for item in json_object["included"]:
            if "type" not in item or "id" not in item:
                continue

            if item["type"] != "channels":
                continue

            if item["attributes"] is None or item["attributes"]["title"] is None:
                continue

            channels.append({
                'id': item["id"],
                'name': item["attributes"]["title"],
                'logo': item["attributes"]["logo-url"],
                'thumb': item["attributes"]["epg-default-poster-url"]
            })
    
        Cache.cached_channels = channels
        return channels


    def get_epg(self, dateUtc1, dateUtc2, chid=''):
        printDBG("[Shortcut.lv] Getting EPG for: " + str(dateUtc1) + " - " +  str(dateUtc2) + "; chid: " + chid)

        timestamp_from = dateTounixTS(dateUtc1)
        timestamp_to = dateTounixTS(dateUtc2)
    
        #chids = chid
        #if isEmpty(chids): chids = '*'
        #key_str = 'GETEPG|' + str(timestamp_from) + '|' + str(timestamp_to) + '|' + chids
        #if Cache.cached_epg.has_key(key_str):
        #    printDBG("[Shortcut.lv] Getting EPG  from cache")
        #    return Cache.cached_epg[key_str]

        url = self.API_ENDPOINT + "/get/content/epgs/?include=channel&page[size]=100000&filter[utTo]="+str(timestamp_to)+"&filter[utFrom]="+str(timestamp_from)
        if not isEmpty(chid):
            url = url + "&filter[channel]=" + str(chid)
    
        response_status, response_text = self.getPage(url)

        if not response_status:
            printDBG("[Shortcut.lv] Got bad response from EPG service. Response code: ")
            return None

        json_object = None
        try:
            json_object = json.loads(response_text)
        except ValueError, e:
            printDBG("[Shortcut.lv] Did not receive json, something wrong: " + response_text)
            return None

        #Cache.cached_epg[key_str] = json_object

        return json_object


    def get_epg_now(self):
        dateutc = datetime.utcfromtimestamp(time.time())
        return self.get_epg(dateutc, dateutc)


    def get_epg_for_channel(self, date, chid):
        timestampFrom = dateFromLocalToUtc(date)
        timestampTo = timestampFrom + timedelta(seconds=86400)
        return self.get_epg(timestampFrom, timestampTo, chid)

    
    def prepare_epg(self, epg_data, bychannel=True, filterchannel = '', 
                    filtertimefrom = None, filtertimeto = None):
        printDBG("[Shortcut.lv] Preparing EPG")
        events = {}
        for item in epg_data["data"]:
            if item["type"] != "epgs":
                continue
            id = item["id"]

            chid = item["relationships"]["channel"]["data"]["id"]
            time_start = dateFromUnix(float(item["attributes"]["unix-start"]))
            time_stop = dateFromUnix(float(item["attributes"]["unix-stop"]))
            time_start = dateFromUtcToLocal(time_start)
            time_stop = dateFromUtcToLocal(time_stop)
            title = item["attributes"]["title"]
            desc = item["attributes"]["description"]

            if not isEmpty(filterchannel) and chid != filterchannel:
                continue

            if not filtertimefrom is None and not filtertimeto is None:
                if time_start > filtertimeto or time_stop < filtertimefrom:
                    continue
        
            event = {}
            event["id"] = id
            event["chid"] = chid
            event["start"] = time_start
            event["stop"] = time_stop
            event["title"] = title.encode('utf8')
            event["desc"] = desc.encode('utf8')
            event["poster"] = self.API_BASEURL + '/' + item["attributes"]["poster-url"]

            if bychannel:
                events[chid] = event
            else:
                events[id] = event
        return events
    

    def filter_pepg(self, pepg = {}, bychid = False, filterchannel = '', 
                    filtertimefrom = None, filtertimeto = None):
        events = {}
        for key, val in pepg.items():
            chid = val['chid']
            time_start = val['start']
            time_stop = val['stop']
            if not isEmpty(filterchannel) and chid != filterchannel: 
                continue
            if not filtertimefrom is None and not filtertimeto is None:
                if time_start > filtertimeto or time_stop < filtertimefrom:
                    continue
            if bychid:
                events[chid] = val
            else:
                events[key] = val
        return events


    def prepare_epg_now(self):
        #epg_data = get_epg_now()
        date_now = datetime.fromtimestamp(time.time())
        date_today = dateToDateTime(date.today())

        sdate = date_today.strftime('%Y-%m-%d')
        key_str = 'PREPEPGNOW|' + sdate
        if Cache.cached_epg.has_key(key_str):
            printDBG("[Shortcut.lv] prepare_epg_now hit cache")
            pepg = Cache.cached_epg[key_str]
            return self.filter_pepg(pepg, True, '', date_now, date_now)

        epg_data = self.get_epg_for_channel(date_today, '')
        if epg_data is None: return {}
        pepg = self.prepare_epg(epg_data, False)
        Cache.cached_epg[key_str] = pepg
        pepg = self.filter_pepg(pepg, True, '', date_now, date_now)
        return pepg


    def prepare_epg_for_channel(self, date, chid):
        sdateutc = dateFromLocalToUtc(date).strftime('%Y-%m-%d')
        schid = chid
        if isEmpty(schid): schids = '*'
        key_str = 'PREPEPGFORCH|' + sdateutc + '|' + schid
        if Cache.cached_epg.has_key(key_str):
            printDBG("[Shortcut.lv] prepare_epg_for_channel hit cache")
            return Cache.cached_epg[key_str]

        epg_data = self.get_epg_for_channel(date, chid)
        if epg_data is None: return {}
        pepg = self.prepare_epg(epg_data, False)
        Cache.cached_epg[key_str] = pepg
        return pepg


    def login(self, force=False):
        username = config.plugins.iptvplayer.shortcut_login.value
        password = config.plugins.iptvplayer.shortcut_password.value
        token = config.plugins.iptvplayer.shortcut_token.value
        lastlogin = config.plugins.iptvplayer.shortcut_last_loggin.value
        uid = get_unique_id()
        printDBG("[Shortcut.lv] [Login] User: " + username + ";UID: " + uid + "; Token: " + token + "; LastLogin: " + lastlogin)
        lastlogin_date = getLastLoggedIn()


        if isEmpty(username) or isEmpty(password):
            return False
    
        update = force or isEmpty(token)
        update = update or (abs(lastlogin_date - datetime.now()) > timedelta(days=1))
    
        if not update:
            return True

        values = {'id': username,
                  'uid': uid,
                  'password': password}
    
        url = self.API_ENDPOINT + '/post/user/users'
        response_status, response_text = self.getPage(url, {}, values)

        setToken('')

        if not response_status:
            printDBG("[Shortcut.lv] Login failed")
            return False
        
        json_object = None
        try:
            json_object = json.loads(response_text)
        except ValueError, e:
            printDBG("[Shortcut.lv] Did not receive json, something wrong: " + response_text)
            printDBG("[Shortcut.lv] Failed to log in, API error")

        token = json_object["data"]["attributes"]["token"]

        setToken(token)
        setLastLoggedIn(datetime.now())
    
        printDBG("[Shortcut.lv] Login success! Token: " + token)
        return True


    def get_stream_url(self, chid):
        quality = config.plugins.iptvplayer.shortcut_quality.value
        printDBG("[Shortcut.lv] Getting URL for channel: " + chid + " quality: " + quality)

        if not self.login():
            return ''

        streamurl = None
        token = config.plugins.iptvplayer.shortcut_token.value
        url = self.API_ENDPOINT + "/get/content/live-streams/" + chid + "?include=quality"

        addParams = {'header': {'Authorization' : "Bearer " + token}}
        response_status, response_text = self.getPage(url, addParams)

        if not response_status:
            setToken('')
            printDBG("[Shortcut.lv] Got incorrect response code while requesting stream info. Text: " + response_text)
            return ''
        
        json_object = None
        try:
            json_object = json.loads(response_text)
        except ValueError, e:
            setToken('')
            printDBG("[Shortcut.lv] Did not receive json, something wrong: " + response_text)
            return ''

        stream_links = {}

        for stream in json_object["data"]:
            if stream["type"] != "live-streams":
                continue
            url = stream["attributes"]["stream-url"]
            if "_lq.stream" in stream["id"]: stream_links["3-lq"] = url
            elif "_mq.stream" in stream["id"]: stream_links["2-mq"] = url
            elif "_hq.stream" in stream["id"]: stream_links["1-hq"] = url
            elif "_hd.stream" in stream["id"]: stream_links["0-hd"] = url
    
        qualityx = toQualityX(quality)

        for key in sorted(stream_links.keys()):
            if key >= qualityx:
                streamurl = stream_links[key]
                break
            streamurl = stream_links[key]

        return streamurl


    def get_archive_url(self, eventid):
        quality = config.plugins.iptvplayer.shortcut_quality.value
        printDBG("[Shortcut.lv] Getting URL for archive event: " + eventid + " quality: " + quality)

        if not self.login():
            return ''

        streamurl = None
        token = config.plugins.iptvplayer.shortcut_token.value
        url = self.API_ENDPOINT + "/get/content/record-streams/" + eventid + "?include=quality"
        addParams = {'header': {'Authorization' : "Bearer " + token}}
        response_status, response_text = self.getPage(url, addParams)

        if not response_status:
            setToken('')
            printDBG("[Shortcut.lv] Got incorrect response code while requesting stream info. Text: " + response_text)
            return ''
        
        json_object = None
        try:
            json_object = json.loads(response_text)
        except ValueError, e:
            setToken('')
            printDBG("[Shortcut.lv] Did not receive json, something wrong: " + response_text)
            return ''

        stream_links = {}

        for stream in json_object["data"]:
            if stream["type"] != "record-streams":
                continue
            url = stream["attributes"]["stream-url"]
            if "_lq." in stream["id"]: stream_links["3-lq"] = url
            elif "_mq." in stream["id"]: stream_links["2-mq"] = url
            elif "_hq." in stream["id"]: stream_links["1-hq"] = url
            elif "_hd." in stream["id"]: stream_links["0-hd"] = url
    
        qualityx = toQualityX(quality)

        for key in sorted(stream_links.keys()):
            if key >= qualityx:
                streamurl = stream_links[key]
                break
            streamurl = stream_links[key]

        return streamurl

  
    def getLinksForVideo(self, cItem):
        printDBG("[Shortcut.lv] getLinksForVideo [%s]" % cItem)
        
        xurl = cItem['url']
        mode, id = xurl.split('|')
        if mode == 'playlive': url = self.get_stream_url(id)
        elif mode == 'playarchive': url = self.get_archive_url(id)
        
        retlist = []
        if isEmpty(url): return []

        urlMeta = {'User-Agent':self.USER_AGENT, 
                   'Connection': 'keep-alive'}
        url = urlparser.decorateUrl(url, urlMeta)  
        
        #tmpList = getDirectM3U8Playlist(url, checkExt=False)
        #url = tmpList[0]['url']
        #url = urlparser.decorateUrl(url, urlMeta)  

        retlist.append({'name':xurl, 'url': url})
        return retlist

   
    def listMainMenu(self):
        printDBG("Shortcut.listMainMenu")
        self.addDir({'category': 'live', 'title': 'Tiesraide' , 'url': '', 'text_color': 'yellow'})              
        self.addDir({'category': 'archive', 'title': 'Arhivs' , 'url': '', 'text_color': 'yellow'})              

    
    def listLiveItems(self,cItem):
        printDBG("Shortcut.listLiveItems")
        category = self.currItem.get("category", '')
        title    = self.currItem.get("title", '')
        xurl     = self.currItem.get("url", '')
        
        channels = self.get_channels()
        epgnow = self.prepare_epg_now()

        for c in channels:
            chid = c['id']
            name = c['name'].encode('utf8')
            if epgnow.has_key(chid):
                event = epgnow[chid]
                start = event['start'].strftime('%H:%M')
                stop = event['stop'].strftime('%H:%M')
                stime = start + '-' + stop
                label = '{} - {} - {}'.format(name, stime, event['title'])
                desc = label + '\n' + event['desc']        
            else:
                label = name
                desc = ''
            url = 'playlive|' + c['id']
            self.addVideo({'title': label , 'url': url, 'desc': desc })

  
    def listArchiveItems(self,cItem):
        printDBG("Shortcut.listArchiveItems")
        category = self.currItem.get("category", '')
        title    = self.currItem.get("title", '')
        xurl     = self.currItem.get("url", '')
        
        channels = self.get_channels()
        for c in channels:
            name = (c['name'] + ' (arhivs)').encode('utf8')
            url = c['name'] + '|' + c['id']
            self.addDir({'category': 'archivedates', 'title': name , 'url': url})


    def listArchiveDatesItems(self,cItem):
        printDBG("Shortcut.listArchiveItems")
        category = self.currItem.get("category", '')
        title    = self.currItem.get("title", '')
        xurl     = self.currItem.get("url", '')
        
        dt = date.today()
        name, chid = xurl.split('|')
        for i in range(7):
            dt2 = dt + timedelta(days=-i)
            sdt = dt2.strftime('%A %d. %B').encode('utf8')
            urldt = dt2.strftime('%Y%m%d')
            url = name + '|' + chid + '|' + urldt
            title = str(name) + ' - ' + sdt
            self.addDir({'category': 'archivedate', 'title': title , 'url': url})


    def listArchiveDateItems(self,cItem):
        printDBG("Shortcut.listArchiveItems")
        category = self.currItem.get("category", '')
        title    = self.currItem.get("title", '')
        xurl     = self.currItem.get("url", '')
       
        name, chid, urldt = xurl.split('|')
        date = dateFromString(urldt, '%Y%m%d')
        epg = self.prepare_epg_for_channel(date, chid)
        
        for event in sorted(epg.values(), key = lambda x: x['start']):
            start = event['start'].strftime('%H:%M')
            stop = event['stop'].strftime('%H:%M')
            time = start
            time2 = start + '-' + stop
            label = '{} - {}'.format(time, event['title'])
            desc = '{} - {} - {}\n{}'.format(name, time2, event['title'], event['desc'])
            start2 = event['start'].strftime('%d %b')
            title = start2 + ' ' + event['title']
            url = 'playarchive|' + event['id']
            self.addVideo({'title': label , 'url': url, 'desc': desc })
       
       
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('Shortcut.handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        subtype  = self.currItem.get("sub-type",'')
        
        printDBG( "handleService: >> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
        if name == None:
            self.listMainMenu()
        elif category == 'live':
            self.listLiveItems(self.currItem)
        elif category == 'archive':
            self.listArchiveItems(self.currItem)
        elif category == 'archivedates':
            self.listArchiveDatesItems(self.currItem)
        elif category == 'archivedate':
            self.listArchiveDateItems(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Shortcut(), True, [])

