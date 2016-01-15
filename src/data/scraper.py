"""Downloads community-generated music analysis data from hooktheory theorytab and YouTube audio.

Usage: scraper.py [--cache=<path>] [--fresh] [--loglevel=<level>] [--youtube_api_key=<key>]

Options:
  --cache=<path>           Set cache directory to <path>.
  --fresh                  Redownload items that have been cached.
  --loglevel=<level>       Set log level [default: INFO].
  --youtube_api_key=<key>  Set YouTube data API v3 key.
"""

from __future__ import print_function

import glob
import logging
import os.path
import re
import string
import sys

import bs4
import docopt
import pafy
import requests

class HooktheoryScraper:
  ARTISTS_URL_TEMPLATE = "http://www.hooktheory.com/theorytab/artists/{}?page={}"
  ARTISTS_KEY_TEMPLATE = "character/{}-{}.html"
  ARTISTS_URL_REGEX = re.compile(r'/theorytab/artists/[a-z0-9\-]/(.+)')
  SONGS_URL_TEMPLATE = "http://www.hooktheory.com/theorytab/artists/a/{}?page={}"
  SONGS_KEY_TEMPLATE = "artist/{}-{}.html"
  SONGS_URL_REGEX = re.compile(r'/theorytab/view/[a-z0-9\-]+/(.+)')
  SECTIONS_URL_TEMPLATE = "http://www.hooktheory.com/theorytab/view/{}/{}"
  SECTIONS_KEY_TEMPLATE = "song/{}-{}.html"
  SECTIONS_URL_REGEX = re.compile(r'/theorytab/fork/id/([0-9]+)')
  SECTION_URL_TEMPLATE = "http://www.hooktheory.com/songs/getXmlByPk?pk={}"
  SECTION_KEY_TEMPLATE = "section/{}.xml"
  YOUTUBE_KEY_TEMPLATE = "youtube/{}"

  def __init__(self, *, cache=None, fresh=False, user_agent=None, loglevel='WARNING', **options):
    self.cache = cache
    self.fresh = fresh
    self.user_agent = user_agent
    self.logger = logging.getLogger(__name__)
    self.logger.setLevel(loglevel)
    ch = logging.StreamHandler()
    ch.setLevel(loglevel)
    self.logger.addHandler(ch)
    ch.setLevel(loglevel)

    self.options = options

  def fetch_many(self, fetcher, processor, requests):
    return [fetcher(processor, request) for request in requests]

  def fetch_html(self, processor, request):
    """Fetches an html page.
    Request:
      key: filename in the cache.
      url: filename to fetch with a GET request.
    Response:
      string containing html.
    """
    cache_path = os.path.join(self.cache, request['key']) if self.cache is not None else None
    if not self.fresh and cache_path is not None and os.path.exists(cache_path):
      with open(cache_path) as f:
        response = f.read()
      self.logger.info("Got %s from cache", request['key'])
    else:
      headers = {'user-agent': self.user_agent}
      response = requests.get(request['url'], headers=headers).text
      if self.cache is not None:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w') as f:
          f.write(response)
      self.logger.info("Got %s", request['key'])

    return processor(request, response)

  def fetch_youtube(self, processor, request):
    """Fetches YouTube audio.
    Request:
      key: filename in the cache, without extension.
      id: YouTube id.
    Response:
      string path of the downloaded file.
    """
    if self.cache is None:
      return processor(request, None)

    cache_path = os.path.join(self.cache, request['key'])
    cache_files = glob.glob(cache_path + '.*')
    if not self.fresh and len(cache_files) > 0:
      cache_full_path = cache_files[0]
      self.logger.info("Got %s from cache", request['key'])
      return processor(request, cache_full_path)

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    try:
      audio_stream = pafy.new(request['id']).getbestaudio()
      cache_full_path = '{}.{}'.format(cache_path, audio_stream.extension)
      audio_stream.download(filepath=cache_full_path)
      self.logger.info("Got %s", request['key'])
      return processor(request, cache_full_path)
    except OSError as e:
      self.logger.error("Couldn't get %s", request['key'])
      return processor(request, None)

  def make_artist_list_request(self, character, page):
    return {
      'key': self.ARTISTS_KEY_TEMPLATE.format(character, page),
      'url': self.ARTISTS_URL_TEMPLATE.format(character, page),
      'character': character,
      'page': page,
    }

  def make_song_list_request(self, artist_id, page):
    return {
      'key': self.SONGS_KEY_TEMPLATE.format(artist_id, page),
      'url': self.SONGS_URL_TEMPLATE.format(artist_id, page),
      'artist_id': artist_id,
      'page': page,
    }

  def make_section_list_request(self, artist_id, song_id):
    return {
      'key': self.SECTIONS_KEY_TEMPLATE.format(artist_id, song_id),
      'url': self.SECTIONS_URL_TEMPLATE.format(artist_id, song_id),
      'artist_id': artist_id,
      'song_id': song_id,
    }

  def make_section_request(self, section_id):
    return {
      'key': self.SECTION_KEY_TEMPLATE.format(section_id),
      'url': self.SECTION_URL_TEMPLATE.format(section_id),
      'section_id': section_id,
    }

  def make_youtube_request(self, youtube_id):
    return {
      'key': self.YOUTUBE_KEY_TEMPLATE.format(youtube_id),
      'id': youtube_id,
    }

  def run(self, characters):
    """Start by exploring artists by first letter/number. This should cover most if not all songs.
    Estimated number of requests: ~100
    """
    requests = (self.make_artist_list_request(character, 1) for character in list(characters))
    artistss = self.fetch_many(self.fetch_html, self.process_artist_list, requests)
    result = {}
    for artists in artistss:
      result.update(artists)
    return result

  def process_artist_list(self, request, response):
    """Scrape artist ids from artist lists. Fetch artist pages listing songs.
    If the list of artists is more than 100 long, increment the page number and fetch more artists.
    Estimated number of requests: ~5000
    """
    soup = bs4.BeautifulSoup(response, 'lxml')
    links = soup.find_all(href=lambda href: href and self.ARTISTS_URL_REGEX.match(href))
    result = {}
    for link in links:
      artist_id = self.ARTISTS_URL_REGEX.match(link.get('href')).group(1)
      result[artist_id] = self.fetch_html(self.process_song_list, self.make_song_list_request(artist_id, 1))

    if len(links) >= 100:
      request_ = self.make_artist_list_request(request['character'], request['page'] + 1)
      result.update(self.fetch_html(self.process_artist_list, request_))

    return result

  def process_song_list(self, request, response):
    """Scrape song ids from song lists. Fetch song page listing sections.
    Estimated number of requests: ~7000
    """
    soup = bs4.BeautifulSoup(response, 'lxml')
    links = soup.find_all(href=lambda href: href and self.SONGS_URL_REGEX.match(href))
    artist_id = request['artist_id']
    result = {}
    for link in links:
      song_id = self.SONGS_URL_REGEX.match(link.get('href')).group(1)
      result[song_id] = self.fetch_html(self.process_section_list, self.make_section_list_request(artist_id, song_id))

    if len(links) >= 100:
      request_ = self.make_song_list_request(request['artist_id'], request['page'] + 1)
      result.update(self.fetch_html(self.process_song_list, request_))

    return result

  def process_section_list(self, request, response):
    """Scrape section ids from song pages. Fetch theory data.
    Estimated number of requests: ~11000
    """
    soup = bs4.BeautifulSoup(response, 'lxml')
    links = soup.find_all(href=lambda href: href and self.SECTIONS_URL_REGEX.match(href))
    result = {}
    for link in links:
      section_id = self.SECTIONS_URL_REGEX.match(link.get('href')).group(1)
      result[section_id] = self.fetch_html(self.process_section, self.make_section_request(section_id))

    return result

  def process_section(self, request, response):
    """Scrape YouTube ids from theory data.
    Estimated number of requests: ~11000
    """
    soup = bs4.BeautifulSoup(response, 'xml')
    youtube_element = soup.find("YouTubeID")
    if youtube_element is None:
      return None
    
    youtube_id = youtube_element.string
    if youtube_id == 'null':
      return None

    self.fetch_youtube(self.process_youtube, self.make_youtube_request(youtube_id))
    return youtube_id

  def process_youtube(self, request, response):
    """Process downloaded YouTube clips."""
    pass


def main(args):
  """User-Agent will be set to 'github.com/jczhang/aurora' for transparency.
  Responses are cached to disk before parsing for troubleshooting and to prevent repeated requests.
  """
  cache = args['--cache']
  fresh = args['--fresh']
  loglevel = args['--loglevel']
  youtube_api_key = args['--youtube_api_key']

  if youtube_api_key is not None:
    pafy.set_api_key(youtube_api_key)
  scraper = HooktheoryScraper(cache=cache, fresh=fresh, user_agent='github.com/jczhang/aurora', loglevel=loglevel)
  result = scraper.run(string.ascii_lowercase + string.digits)
  print(result)

if __name__ == '__main__':
  args = docopt.docopt(__doc__, sys.argv[1:])
  if args is not None:
    main(args)