from bs4 import BeautifulSoup
from couchpotato.core.helpers.variable import getTitle, tryInt
from couchpotato.core.logger import CPLog
from couchpotato.core.helpers.encoding import simplifyString, tryUrlencode
from couchpotato.core.helpers.variable import getTitle, mergeDicts
from couchpotato.core.providers.torrent.base import TorrentProvider
from dateutil.parser import parse
import cookielib
import htmlentitydefs
import json
import re
import time
import traceback
import urllib
import urllib2
import unicodedata
from libs.werkzeug.urls import url_encode
from couchpotato.core.event import fireEvent

log = CPLog(__name__)


class Base(TorrentProvider):

    urls = {
        'test': 'http://www.cpasbien.pw/',
        'search': 'http://www.cpasbien.pw/recherche/',
    }

    http_time_between_calls = 1 #seconds
    cat_backup_id = None

    class NotLoggedInHTTPError(urllib2.HTTPError):
        def __init__(self, url, code, msg, headers, fp):
            urllib2.HTTPError.__init__(self, url, code, msg, headers, fp)

    class PTPHTTPRedirectHandler(urllib2.HTTPRedirectHandler):
        def http_error_302(self, req, fp, code, msg, headers):
            log.debug("302 detected; redirected to %s" % headers['Location'])
            if (headers['Location'] != 'login.php'):
                return urllib2.HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)
            else:
                raise cPASbien.NotLoggedInHTTPError(req.get_full_url(), code, msg, headers, fp)

    def _search(self, movie, quality, results):

                # Cookie login
        if not self.login_opener and not self.login():
            return


        TitleStringReal = (getTitle(movie['library']) + ' ' + simplifyString(quality['identifier'] )).replace('-',' ').replace(' ',' ').replace(' ',' ').replace(' ',' ').encode("utf8")
        
        URL = (self.urls['search']).encode('UTF8')
        URL=unicodedata.normalize('NFD',unicode(URL,"utf8","replace"))
        URL=URL.encode('ascii','ignore')
        URL = urllib2.quote(URL.encode('utf8'), ":/?=")
        
        values = {
          'champ_recherche' : TitleStringReal
        }

        data_tmp = urllib.urlencode(values)
        req = urllib2.Request(URL, data_tmp )
        
        data = urllib2.urlopen(req )

        log.error(URL)
        log.error(TitleStringReal)

        id = 1000

        if data:

            cat_ids = self.getCatId(quality['identifier'])
            table_order = ['name', 'size', None, 'age', 'seeds', 'leechers']
            
            try:
                html = BeautifulSoup(data)

                resultdiv = html.find('div', attrs = {'id':'recherche'}).find('table').find('tbody')

                for result in resultdiv.find_all('tr', recursive = False):

                    try:
                        
                        new = {}

                        #id = result.find_all('td')[2].find_all('a')[0]['href'][1:].replace('torrents/nfo/?id=','')
                        name = result.find_all('td')[0].find_all('a')[0].text
                        
                        detail_url = result.find_all('td')[0].find_all('a')[0]['href']

                        #on scrapp la page detail

                        urldetail = detail_url.encode('UTF8')
                        urldetail=unicodedata.normalize('NFD',unicode(urldetail,"utf8","replace"))
                        urldetail=urldetail.encode('ascii','ignore')
                        urldetail = urllib2.quote(urldetail.encode('utf8'), ":/?=")

                        req = urllib2.Request(urldetail )  # POST request doesn't not work
                        data_detail = urllib2.urlopen(req)

                        url_download = ""

                        if data_detail:
                            
                            html_detail = BeautifulSoup(data_detail)                                
                            url_download = html_detail.find_all('div', attrs = {'class':'download-torrent'})[0].find_all('a')[0]['href']    
                        else:
                            tmp = result.find_all('td')[0].find_all('a')[0]['href']
                            tmp = tmp.split('/')[6].replace('.html','.torrent')
                            url_download = ('http://www.cpasbien.me/_torrents/%s' % tmp)



                        size = result.find_all('td')[1].text
                        seeder = result.find_all('td')[2].find_all('span')[0].text
                        leecher = result.find_all('td')[3].text
                        age = '0'

                        verify = getTitle(movie['library']).split(' ')
                        
                        add = 1
                        
                        for verify_unit in verify:
                            if (name.find(verify_unit) == -1) :
                                add = 0

                        def extra_check(item):
                            return True

                        if add == 1:

                            new['id'] = id
                            new['name'] = name.strip()
                            new['url'] = url_download
                            new['detail_url'] = detail_url
                           
                            new['size'] = self.parseSize(size)
                            new['age'] = self.ageToDays(age)
                            new['seeders'] = tryInt(seeder)
                            new['leechers'] = tryInt(leecher)
                            new['extra_check'] = extra_check
                            new['download'] = self.loginDownload             
    
                            #new['score'] = fireEvent('score.calculate', new, movie, single = True)
    
                            #log.error('score')
                            #log.error(new['score'])
    
                            results.append(new)
    
                            id = id+1
                        
                    except:
                        log.error('Failed parsing cPASbien: %s', traceback.format_exc())

            except AttributeError:
                log.debug('No search results found.')
        else:
            log.debug('No search results found.')

    def ageToDays(self, age_str):
        age = 0
        age_str = age_str.replace('&nbsp;', ' ')

        regex = '(\d*.?\d+).(sec|heure|jour|semaine|mois|ans)+'
        matches = re.findall(regex, age_str)
        for match in matches:
            nr, size = match
            mult = 1
            if size == 'semaine':
                mult = 7
            elif size == 'mois':
                mult = 30.5
            elif size == 'ans':
                mult = 365

            age += tryInt(nr) * mult

        return tryInt(age)

    def login(self):

        cookieprocessor = urllib2.HTTPCookieProcessor(cookielib.CookieJar())
        opener = urllib2.build_opener(cookieprocessor, cPASbien.PTPHTTPRedirectHandler())
        opener.addheaders = [
            ('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.1 (KHTML, like Gecko)'),
            ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
            ('Accept-Language', 'fr-fr,fr;q=0.5'),
            ('Accept-Charset', 'ISO-8859-1,utf-8;q=0.7,*;q=0.7'),
            ('Keep-Alive', '115'),
            ('Connection', 'keep-alive'),
            ('Cache-Control', 'max-age=0'),
        ]

        try:
            response = opener.open('http://www.cpasbien.me', tryUrlencode({'url': '/'}))
        except urllib2.URLError as e:
            log.error('Login to cPASbien failed: %s' % e)
            return False

        if response.getcode() == 200:
            log.debug('Login HTTP cPASbien status 200; seems successful')
            self.login_opener = opener
            return True
        else:
            log.error('Login to cPASbien failed: returned code %d' % response.getcode())
            return False
        
        
    def loginDownload(self, url = '', nzb_id = ''):
        values = {
          'url' : '/'
        }
        data_tmp = urllib.urlencode(values)
        req = urllib2.Request(url, data_tmp )
        
        try:
            if not self.login_opener and not self.login():
                log.error('Failed downloading from %s', self.getName())
            return urllib2.urlopen(req).read()
        except:
            log.error('Failed downloading from %s: %s', (self.getName(), traceback.format_exc()))
            
    def download(self, url = '', nzb_id = ''):
        
        if not self.login_opener and not self.login():
            return
        
        values = {
          'url' : '/'
        }
        data_tmp = urllib.urlencode(values)
        req = urllib2.Request(url, data_tmp )
        
        try:
            return urllib2.urlopen(req).read()
        except:
            log.error('Failed downloading from %s: %s', (self.getName(), traceback.format_exc()))
      
config = [{
    'name': 'cPASbien',
    'groups': [
        {
            'tab': 'searcher',
            'subtab': 'providers',
            'list': 'torrent_providers',
            'name': 'cPASbien',
            'description': 'See <a href="http://www.cpasbien.pw/">cPASbien</a>',
            'wizard': True,
            'options': [
                {
                    'name': 'enabled',
                    'type': 'enabler',
                    'default': True,
                },
            ],
        },
    ],
}]
