"""Helper library for handling hooktheory theorytab data files."""

from __future__ import print_function

import logging
import re

import bs4

loglevel = 'WARNING'
logger = logging.getLogger(__name__)
logger.setLevel(loglevel)
ch = logging.StreamHandler()
ch.setLevel(loglevel)
logger.addHandler(ch)
ch.setLevel(loglevel)
YOUTUBE_ID_REGEX = re.compile(r'[0-9A-Za-z-_]{11}')

class Theorytab:
  def __init__(self, filename):
    with open(filename) as f:
      source = f.read()
    self.soup = bs4.BeautifulSoup(source, 'xml')
    version_element = self.soup.find('version')
    if version_element is None or version_element.string is None:
      self.version = "1.0"
    else:
      self.version = version_element.string
    self.filename = filename
    # example versions:
    # version 1.1: section >= 173661
    # version 1.2: section >= 191620

  def clips(self):
    """Separates the theorytab file into sections with backing YouTube video.
    In version <= 1.0, there may be more than one section per file (example: section=3899)
    In version >= 1.1, there is at most one section.
    """
    # A <meta> element may be nested within a <super> or a <theorytab>, but there
    # should be only one.
    meta_element = self.soup.find('meta')
    if meta_element is None:
      return []

    # A <YouTubeID> is a child of <meta>, and there should be only one, if it exists.
    youtube_element = meta_element.find('YouTubeID')
    if youtube_element is None or youtube_element.string is None:
      logger.warning("%s has no YouTube element", self.filename)
      return []
    if not YOUTUBE_ID_REGEX.match(youtube_element.string):
      logger.warning("%s has an invalid YouTube id", self.filename)
      return []
    youtube_id = youtube_element.string

    # The section timing data is in <sections> for <= 1.1 or <meta> for >= 1.2.
    if self.version in ["1.0", "1.1"]:
      timing_parent = meta_element.find('sections')
      if timing_parent is None:
        logger.warning("%s couldn't find timing data", self.filename)
        return []
    else:
      timing_parent = meta_element
    # When the clip starts playing
    global_starts = timing_parent.find_all('global_start')
    # When the theorytab notes start
    active_starts = timing_parent.find_all('active_start')
    # When the theorytab notes stop
    active_stops = timing_parent.find_all('active_stop')
    clips = []
    for global_start, active_start, active_stop in zip(global_starts, active_starts, active_stops):
      if None in [global_start.string, active_start.string, active_stop.string]:
        continue
      clips.append({
          'youtube_id': youtube_id,
          'start_time': float(global_start.string) + float(active_start.string),
          'end_time': float(global_start.string) + float(active_stop.string),
          'source': self.filename,
        })

    if len(clips) == 0:
      logger.warning("%s has no clips", self.filename)

    return clips
