# aurora
Music transcription and song analysis with LSTM neural networks.
Based on data from hooktheory theorypad.

## Setup instructions
1. Create a python virtual environment and install deps using
`pip3 install -r requirements.txt`

2. Install ffmpeg with libvorbis and libvpx. On MacOS Homebrew, use
`brew install ffmpeg --with-libvorbis --with-libvpx`

3. Get a [YouTube API key](https://developers.google.com/youtube/v3/getting-started).

4. Install tensorflow (exact setup TBI).

## Data collection instructions
1. Scrape data by running
`python3 src/data/scraper.py --cache=cache --youtube_api_key=<key>`

2. Generate truncated audio clips and spec files.

`python3 src/data/generate.py generate_specs cache/section cache/youtube dataset/specs`

`python3 src/data/generate.py clip_audio dataset/specs cache/youtube dataset/audio`

At this point the cache may be deleted (although you may want to keep `cache/section`
for future spec changes).

To update the spec with the clipped audio, run
`python3 src/data/generate.py generate_specs cache/section dataset/audio dataset/specs`

3. Generate a TensorFlow dataset.
TBI

## Training instructions
TBI

## Inference instructions
TBI
