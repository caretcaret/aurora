"""Helper library for handling hooktheory theorytab data files."""

from __future__ import print_function

import logging
import re

import bs4

loglevel = 'ERROR'
logger = logging.getLogger(__name__)
logger.setLevel(loglevel)
ch = logging.StreamHandler()
ch.setLevel(loglevel)
logger.addHandler(ch)
ch.setLevel(loglevel)


class Theorytab:
  """Parses a theorytab xml file and produces a normalized representation."""

  YOUTUBE_ID_REGEX = re.compile(r'[0-9A-Za-z-_]{11}')

  NOTE_TO_PITCH_CLASS = {
      'Cb': 11,
      'C': 0,
      'C#': 1,
      'Db': 1,
      'D': 2,
      'D#': 3,
      'Eb': 3,
      'E': 4,
      'E#': 5,
      'Fb': 4,
      'F': 5,
      'F#': 6,
      'Gb': 6,
      'G': 7,
      'G#': 8,
      'Ab': 8,
      'A': 9,
      'A#': 10,
      'Bb': 10,
      'B': 11,
      'B#': 0,
  }

  MODE_TO_NAME = {
      1: 'Major/Ionian',
      2: 'Dorian',
      3: 'Phrygian',
      4: 'Lydian',
      5: 'Mixolydian',
      6: 'Minor/Aeolian',
      7: 'Locrian',
  }

  def __init__(self, filename):
    with open(filename) as f:
      source = f.read()
    self.soup = bs4.BeautifulSoup(source, 'xml')
    version_element = self.soup.find('version')
    if not version_element or not version_element.string:
      self.version = "1.0"
    else:
      self.version = str(version_element.string)
    self.filename = filename
    # example versions:
    # version 1.1: theorytab >= 173661
    # version 1.2: theorytab >= 191620
    # version 1.3: theorytab >= 280191

  def _extract_beats_per_measure(self, meta_element):
    """Extracts the number of beats per measure."""
    beats_element = meta_element.find(['beats_in_measure', 'Beats_In_Measure'])
    if not beats_element or not beats_element.string:
      logger.error("%s has no beats_in_measure element", self.filename)
      return None

    beats_per_measure = int(round(float(beats_element.string)))
    if beats_per_measure <= 0:
      logger.error("%s beats_per_measure is %d", self.filename,
                   beats_per_measure)
      return None

    return beats_per_measure

  def _extract_tonic(self, meta_element):
    """Extract the tonic pitch class of the key."""
    key_element = meta_element.find(['key', 'Key'])
    if not key_element or not key_element.string:
      logger.error("%s has no key element", self.filename)
      return None
    if key_element.string not in self.NOTE_TO_PITCH_CLASS:
      logger.error("%s has unrecognized key %s",
                   self.filename, key_element.string)
      return None

    return self.NOTE_TO_PITCH_CLASS[key_element.string]

  def _extract_mode(self, meta_element):
    """Extract the mode of the key."""
    mode_element = meta_element.find('mode')
    if not mode_element or not mode_element.string:
      logger.warning("%s has no mode element, assuming major", self.filename)
      return 1

    mode = int(round(float(mode_element.string)))
    if mode not in self.MODE_TO_NAME:
      logger.error("%s has unrecognized mode %d", self.filename, mode)
      return None

    return mode

  def _extract_youtube_id(self, meta_element):
    youtube_element = meta_element.find('YouTubeID')
    if (not youtube_element or
            not youtube_element.string or
            youtube_element.string == 'null'):
      logger.error("%s has no YouTube element", self.filename)
      return None
    if not self.YOUTUBE_ID_REGEX.match(youtube_element.string):
      logger.error("%s has an invalid YouTube id %s",
                   self.filename, youtube_element.string)
      return None

    return str(youtube_element.string)

  def _extract_timing(self, meta_section):
    """Extracts the begin and end time in the YouTube video for the section."""
    global_start = meta_section.find('global_start')
    active_start = meta_section.find('active_start')
    active_stop = meta_section.find('active_stop')
    if (None in (global_start, active_start, active_stop) or
        None in (global_start.string, active_start.string,
                 active_stop.string)):
      logger.error("%s is missing global_start, active_start, or active_stop",
                   self.filename)
      return None

    return (float(global_start.string) + float(active_start.string),
            float(global_start.string) + float(active_stop.string))

  def _extract_num_beats(self, data_section, beats_per_measure):
    """Extracts the number of beats for audio alignment."""
    num_measures = 0
    for measure_element in data_section.find_all('numMeasures'):
      if not measure_element.string:
        num_measures = 0
        break
      num_measures += int(round(float(measure_element.string)))
    if num_measures:
      return num_measures * beats_per_measure

    # Theorytabs 3882 to 4192 don't have number of measures.
    # Audio may be synced to a non-integral number of measures.
    num_beats = 0
    for beat_element in data_section.find_all('numBeats'):
      if not beat_element.string:
        num_beats = 0
        break
      num_beats += int(round(float(beat_element.string)))
    if num_beats:
      return num_beats

    # TODO(caretcaret): Use the last beat of the melody or harmony.

    logger.error("%s is missing number of beats", self.filename)
    return None

  def clips(self):
    """Separates the theorytab file into sections with backing YouTube audio.
    In version <= 1.1, there may be more than one section per file.
    In version >= 1.2, there is at most one section.
    """
    # A <meta> element may be nested within a <super> or a <theorytab>, but
    # there should be only one.
    root_element = self.soup.find(['theorytab', 'super'])
    if not root_element:
      logger.error("%s has no root element", self.filename)
      return []
    meta_element = root_element.meta
    if not meta_element:
      logger.error("%s has no meta element", self.filename)
      return []

    beats_per_measure = self._extract_beats_per_measure(meta_element)
    tonic = self._extract_tonic(meta_element)
    mode = self._extract_mode(meta_element)
    youtube_id = self._extract_youtube_id(meta_element)

    if None in (beats_per_measure, tonic, mode, youtube_id):
      return []

    # Find the sections.
    if meta_element.find('sections', recursive=False):
      meta_sections = [
          elem for elem
          in meta_element.find('sections', recursive=False).contents
          if type(elem) != bs4.element.NavigableString]
      data_sections = [
          elem for elem
          in root_element.find('sections', recursive=False).contents
          if type(elem) != bs4.element.NavigableString]
    else:
      meta_sections = [meta_element]
      data_sections = [root_element.data]

    clips = []
    for meta_section, data_section in zip(meta_sections, data_sections):
      if not meta_section or not data_section:
        logger.error("%s couldn't find meta or data section", self.filename)
        continue
      if (meta_section.name != 'meta' and
              data_section.name != 'data' and
              meta_section.name != data_section.name):
        logger.warning("%s section name mismatch: %s and %s",
                       self.filename, meta_section.name, data_section.name)

      interval = self._extract_timing(meta_section)
      if not interval:
        continue
      start_time, end_time = interval

      num_beats = self._extract_num_beats(data_section, beats_per_measure)
      if not num_beats:
        continue

      clips.append({
          'data_source': self.filename,
          'audio_source': {
              'youtube_id': youtube_id,
              'start_time': start_time,
              'end_time': end_time,
          },
          'meter': {
              'beats': num_beats,
              'beats_per_measure': beats_per_measure,
          },
          'key': {
              'tonic': tonic,
              'mode': mode,
          },
          # TODO(caretcaret): Extract melody and harmony.
      })

    if not clips:
      logger.error("%s has no clips", self.filename)

    return clips
