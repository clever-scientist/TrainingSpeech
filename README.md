# AudioCorpFR
> automate and simplify text forced-alignment from audio-books

## Common workflow

### 1. Add New source (contributors only)

1. retrieve epub and corresponding mp3 file from [atramenta](atramenta.net/audiobooks) and store them into `./data/epubs` and `./data/mp3` (respectively)
2. create new source into `./sources.json` (NB: all fields are mandatory)
3. generate initial transcript build_transcript


### 2. Generate and validate alignment on existing source

1. pick a source that have NOT been validated yet: see `python manage.py stats` and `./sources.json` for more info
2. download assets (ie epub and mp3 files): `python manage.py download -s <SOURCE_NAME>`
3. build initial transcript: `python manage.py build_transcript <SOURCE_NAME>`
4. check alignment: `python manage.py check_alignment <SOURCE_NAME>` (may require multiple iterations)
5. send a pull request with generated transcript and alignment

## Dev setup 

```sh
$ git clone git@gitlab.com:nicolaspanel/AudioCorpFR.git
$ pip3 install --user pipenv
$ cd AudioCorpFR
$ pipenv install --python=3.6.6
$ pipenv sync
$ pipenv shell
$ pytest
```