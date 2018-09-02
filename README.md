> Provide open and freely reusable dataset of voices for text-to-speech and speech-to-text models training.
>
> Comes with a CLI that automate and simplify text forced-alignment from audio-books

**Contributions are always welcome !** 


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

## Current Stats (2018-09-02)
| Source                    | Status   | Progress   |   # speeches | Speeches Duration   | Language   |
|:--------------------------|:---------|:-----------|-------------:|:--------------------|:-----------|
| LeComteDeMonteCristoChap1 | DONE     | 100 %      |          235 | 0:19:57.613000      | fr_FR      |
| LeComteDeMonteCristoChap2 | DONE     | 100 %      |          205 | 0:15:52.458000      | fr_FR      |
| LeComteDeMonteCristoChap3 | DONE     | 100 %      |          289 | 0:26:08.636000      | fr_FR      |
| LeComteDeMonteCristoChap4 | DONE     | 100 %      |          192 | 0:14:53.025000      | fr_FR      |
| LeComteDeMonteCristoChap5 | DONE     | 100 %      |          345 | 0:28:44.031000      | fr_FR      |
| LaGloireDuComacchio       | DONE     | 100 %      |         1313 | 1:40:08.420000      | fr_FR      |
|                           |          |            |              |                     |            |
| TOTAL                     |          |            |         2579 | 3:25:44.183000      |            |
| TOTAL fr_FR               |          |            |         2579 | 3:25:44.183000      |            |


## Releases

| Name                                                                                               |   # speeches | Total Duration   | Language   |
|:---------------------------------------------------------------------------------------------------|-------------:|:-----------------|:-----------|
| [2018-09-02_fr_FR.zip](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-09-02_fr_FR.zip) |         2579 | 3:25:44          | fr_FR      |