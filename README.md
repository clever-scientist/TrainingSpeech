`AudioCorp` is an initiative to provide **open and freely reusable dataset** of voices… 

…for speech-to-text models training… 

…on non-english languages… 

…using already available data such as audio-books.
 


Right now, data are extracted exclusively… 

…from audio-books…

…in French language. 



## Tooling

`AudioCorp`  comes with a CLI that automate and simplify:
 - transcript extraction
 - [forced-alignment](https://github.com/pettarin/forced-alignment-tools#definition-of-forced-alignment)
 - validation and correction



## Common workflow

### 1. Generate and validate alignment on existing source

1. pick a source that have NOT been validated yet: see `python manage.py stats` and `./sources.json` for more info
2. download assets (ie epub and mp3 files): `python manage.py download -s <SOURCE_NAME>`
3. check alignment: `python manage.py check_alignment <SOURCE_NAME>` (may require multiple iterations)
4. send a pull request with generated transcript and alignment

### 2. Add New source (team members only)

1. retrieve epub and corresponding mp3 file and store them into `./data/epubs` and `./data/mp3` (respectively)
2. create new source into `./sources.json` (NB: all fields are mandatory)
3. generate initial transcript using `python manage.py build_transcript <SOURCE_NAME>`
4. upload epub and mp3 files on S3 `python manage.py upload -s <SOURCE_NAME>` 


## Dev setup 

```sh
$ sudo apt-get install -y ffmpeg espeak libespeak-dev python3-numpy python-numpy libncurses-dev libncursesw5-dev sox libsqlite3-dev
$ git clone git@gitlab.com:nicolaspanel/AudioCorp.git
$ pip3 install --user pipenv
$ cd AudioCorp
$ pipenv install --python=3.6.6
$ pipenv sync
$ pipenv shell
$ pytest
```


## Last releases

| Name                                                                                               |   # speeches |   # speakers | Total Duration   | Language   |
|:---------------------------------------------------------------------------------------------------|-------------:|-------------:|:-----------------|:-----------|
| [2018-09-09_fr_FR](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-09-09_fr_FR.zip)     |        32245 |            3 | 49:44:22  | fr_FR      |
| [2018-09-05_fr_FR](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-09-05_fr_FR.zip)     |        10292 |            3 | 15:55:12         | fr_FR      |
