# aurora
Music transcription and song analysis with LSTM neural networks.
Based on data from hooktheory theorypad.

## Setup instructions
1. Create a Python 3 virtual environment and activate the environment.
`python3 -m venv /path/to/aurora-env`
`source aurora-env/bin/activate`

2. [Install TensorFlow](https://www.tensorflow.org/versions/r0.11/get_started/os_setup.html) for Python 3.

3. Install deps using
`pip3 install -r requirements.txt`

4. Install ffmpeg with libvorbis and libvpx. On MacOS Homebrew, use
`brew install ffmpeg --with-libvorbis --with-libvpx`

5. Get a [YouTube API key](https://developers.google.com/youtube/v3/getting-started).

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
`python3 src/data/generate.py generate_dataset dataset/specs dataset/audio dataset/dataset.tfrecords`

## Training instructions
TBI

## Inference instructions
TBI
