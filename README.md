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


## Last releases

| Name                                                                                               |   # speeches |   # speakers | Total Duration   | Language   |
|:---------------------------------------------------------------------------------------------------|-------------:|-------------:|:-----------------|:-----------|
| [2018-09-05_fr_FR.zip](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-09-05_fr_FR.zip) |        10292 |            3 | 15:55:12         | fr_FR      |



## Current Stats (2018-09-03)

| Source                        | Status   | Progress   |   # speeches | Speeches Duration   | Language   |
|:------------------------------|:---------|:-----------|-------------:|:--------------------|:-----------|
| LeComteDeMonteCristoT1Chap1   | DONE     | 100 %      |          235 | 0:19:57.613000      | fr_FR      |
| LeComteDeMonteCristoT1Chap2   | DONE     | 100 %      |          205 | 0:15:52.458000      | fr_FR      |
| LeComteDeMonteCristoT1Chap3   | DONE     | 100 %      |          289 | 0:26:08.636000      | fr_FR      |
| LeComteDeMonteCristoT1Chap4   | DONE     | 100 %      |          192 | 0:14:53.025000      | fr_FR      |
| LeComteDeMonteCristoT1Chap5   | DONE     | 100 %      |          345 | 0:28:44.031000      | fr_FR      |
| LeComteDeMonteCristoT1Chap6   | DONE     | 100 %      |          234 | 0:22:33.132000      | fr_FR      |
| LeComteDeMonteCristoT1Chap7   | DONE     | 100 %      |          267 | 0:26:39.812000      | fr_FR      |
| LeComteDeMonteCristoT1Chap8   | DONE     | 100 %      |          286 | 0:27:46.410000      | fr_FR      |
| LeComteDeMonteCristoT1Chap9   | DONE     | 100 %      |          141 | 0:13:41.718000      | fr_FR      |
| LeComteDeMonteCristoT1Chap10  | DONE     | 100 %      |          209 | 0:17:53.854000      | fr_FR      |
| LeComteDeMonteCristoT1Chap11  | DONE     | 100 %      |          217 | 0:17:36.642000      | fr_FR      |
| LeComteDeMonteCristoT1Chap12  | DONE     | 100 %      |          196 | 0:17:06.130000      | fr_FR      |
| LeComteDeMonteCristoT1Chap13  | DONE     | 100 %      |          201 | 0:21:32.854000      | fr_FR      |
| LeComteDeMonteCristoT1Chap14  | DONE     | 100 %      |          280 | 0:25:42.052000      | fr_FR      |
| LeComteDeMonteCristoT1Chap15  | DONE     | 100 %      |          409 | 0:41:08.252000      | fr_FR      |
| LeComteDeMonteCristoT1Chap16  | DONE     | 100 %      |          242 | 0:23:50.096000      | fr_FR      |
| LeComteDeMonteCristoT1Chap17  | DONE     | 100 %      |          505 | 0:41:37.428000      | fr_FR      |
| LeComteDeMonteCristoT1Chap18  | DONE     | 100 %      |          279 | 0:28:02.862000      | fr_FR      |
| LeComteDeMonteCristoT1Chap19  | DONE     | 100 %      |          228 | 0:23:08.514000      | fr_FR      |
| LeComteDeMonteCristoT1Chap20  | DONE     | 100 %      |          113 | 0:11:26.030000      | fr_FR      |
| LeComteDeMonteCristoT1Chap21  | DONE     | 100 %      |          289 | 0:28:33.130000      | fr_FR      |
| LeComteDeMonteCristoT1Chap22  | DONE     | 100 %      |          151 | 0:18:02.404000      | fr_FR      |
| LeComteDeMonteCristoT1Chap23  | DONE     | 100 %      |          182 | 0:19:56.798000      | fr_FR      |
| LeComteDeMonteCristoT1Chap24  | DONE     | 100 %      |          192 | 0:24:05.832000      | fr_FR      |
| LeComteDeMonteCristoT1Chap25  | DONE     | 100 %      |          117 | 0:15:21.020000      | fr_FR      |
| LeComteDeMonteCristoT1Chap26  | DONE     | 100 %      |          255 | 0:28:59.626000      | fr_FR      |
| LeComteDeMonteCristoT1Chap27  | DONE     | 100 %      |          346 | 0:33:07.140000      | fr_FR      |
| LeComteDeMonteCristoT1Chap28  | DONE     | 100 %      |          153 | 0:14:41.766000      | fr_FR      |
| LeComteDeMonteCristoT1Chap29  | DONE     | 100 %      |          303 | 0:30:32.862000      | fr_FR      |
| LeComteDeMonteCristoT1Chap30  | DONE     | 100 %      |          379 | 0:35:52.810000      | fr_FR      |
| LeComteDeMonteCristoT1Chap31  | DONE     | 100 %      |          489 | 0:59:46.002000      | fr_FR      |
| LaGloireDuComacchio           | DONE     | 100 %      |         1313 | 1:40:08.420000      | fr_FR      |
| LeDernierJourDunCondamne      | WIP      | 56 %       |         1050 | 1:20:42.666000      | fr_FR      |
|                               |          |            |              |                     |            |
| TOTAL                         |          |            |        10292 | 15:55:12.025000     |            |
| TOTAL fr_FR                   |          |            |        10292 | 15:55:12.025000     | fr_FR      |
