`TrainingSpeech` is an initiative to provide **open and freely reusable dataset** of voices 

 - for speech-to-text models training

 - on non-english languages 

 - using already available data (such as audio-books).
 

Right now, data are extracted exclusively from audio-books and in French language. Let me know if you are intersted to contribute.



## Tooling

`TrainingSpeech`  comes with a CLI that automate and simplify:
 - transcript extraction
 - [forced-alignment](https://github.com/pettarin/forced-alignment-tools#definition-of-forced-alignment) (using [aeneas](https://github.com/readbeyond/aeneas))
 - validation and correction



## Common workflow

### 1. Generate and validate alignment on existing source

1. pick a source that have NOT been validated yet: see `python manage.py stats` and `./sources.json` for more info
2. download assets (ie epub and mp3 files): `python manage.py download -s <SOURCE_NAME>`
3. check alignment: `python manage.py check-alignment <SOURCE_NAME>` (may require multiple iterations)
4. send a pull request with generated transcript and alignment

### 2. Add New source (team members only)

1. retrieve epub and corresponding mp3 file and store them into `./data/epubs` and `./data/mp3` (respectively)
2. create new source into `./sources.json` (NB: all fields are mandatory)
3. generate initial transcript using `python manage.py build-transcript <SOURCE_NAME>`
4. upload epub and mp3 files on S3 `python manage.py upload -s <SOURCE_NAME>` 


## Dev setup 

```sh
$ sudo apt-get install -y ffmpeg espeak libespeak-dev python3-numpy python-numpy libncurses-dev libncursesw5-dev sox libsqlite3-dev
$ git clone git@gitlab.com:nicolaspanel/TrainingSpeech.git
$ pip3 install --user pipenv
$ cd TrainingSpeech
$ pipenv install --python=3.6.6
$ pipenv sync
$ pipenv shell
$ pytest
```


## Last releases & download
Releases are ready-to-use `zip` archives containing :
 - short 16kHz 16bit wav audio speeches (0-15s)
 - a single `data.csv` file with following columns:
   - `path`: path to the audio file inside the archive
   - `duration`: audio duration in second
   - `text`: transcript


| Name                                                                                                    |   # speeches |   # speakers | Total Duration | Language   |
|:--------------------------------------------------------------------------------------------------------|-------------:|-------------:|:---------------|:-----------|
| [2018-10-03_fr_FR](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-10-03_fr_FR.zip) (latest) |        67670 |            4 | 95:28:42       | fr_FR      |
| [2018-10-02_fr_FR](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-10-02_fr_FR.zip)          |        62657 |            4 | 87:23:34       | fr_FR      |
| [2018-09-28_fr_FR](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-09-28_fr_FR.zip)          |        61664 |            4 | 86:23:05       | fr_FR      |
| [2018-09-27_fr_FR](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-09-27_fr_FR.zip)          |        61658 |            4 | 86:22:43       | fr_FR      |
| [2018-09-18_fr_FR](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-09-18_fr_FR.zip)          |        44439 |            4 | 69:20:14       | fr_FR      |
| [2018-09-05_fr_FR](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-09-05_fr_FR.zip)          |        10292 |            3 | 15:55:12       | fr_FR      |
