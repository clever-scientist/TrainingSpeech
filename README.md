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

## Current Stats (2018-09-03)

| Source                        | Status   | Progress   |   # approved speeches | Approved Speeches Duration   | Language   |
|:------------------------------|:---------|:-----------|-------------:|:--------------------|:-----------|
| LeComteDeMonteCristoT1Chap1   | DONE     | 100 %      |          235 | 0:19:57.613000      | fr_FR      |
| LeComteDeMonteCristoT1Chap2   | DONE     | 100 %      |          205 | 0:15:52.458000      | fr_FR      |
| LeComteDeMonteCristoT1Chap3   | DONE     | 100 %      |          289 | 0:26:08.636000      | fr_FR      |
| LeComteDeMonteCristoT1Chap4   | DONE     | 100 %      |          192 | 0:14:53.025000      | fr_FR      |
| LeComteDeMonteCristoT1Chap5   | DONE     | 100 %      |          345 | 0:28:44.031000      | fr_FR      |
| LeComteDeMonteCristoT1Chap6   | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap7   | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap8   | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap9   | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap10  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap11  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap12  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap13  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap14  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap15  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap16  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap17  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap18  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap19  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap20  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap21  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap22  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap23  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap24  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap25  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap26  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap27  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap28  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap29  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap30  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT1Chap31  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap32  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap33  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap34  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap35  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap36  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap37  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap38  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap39  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap40  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap41  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap42  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap43  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap44  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap45  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap46  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap47  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap48  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap49  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap50  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap51  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap52  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap53  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap54  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT2Chap55  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap56  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap57  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap58  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap59  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap60  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap61  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap62  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap63  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap64  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap65  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap66  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap67  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap68  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap69  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap70  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap71  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap72  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap73  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap74  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap75  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap76  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap77  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap78  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap79  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap80  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap81  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap82  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap83  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT3Chap84  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap85  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap86  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap87  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap88  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap89  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap90  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap91  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap92  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap93  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap94  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap95  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap96  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap97  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap98  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap99  | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap100 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap101 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap102 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap103 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap104 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap105 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap106 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap107 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap108 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap109 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap110 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap111 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap112 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap113 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap114 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap115 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap116 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LeComteDeMonteCristoT4Chap117 | PENDING  | 0 %        |            0 | 0:00:00             | fr_FR      |
| LaGloireDuComacchio           | DONE     | 100 %      |         1313 | 1:40:08.420000      | fr_FR      |
| LeDernierJourDunCondamne      | WIP      | 35 %       |          604 | 0:51:41.564000      | fr_FR      |
|                               |          |            |              |                     |            |
| TOTAL                         |          |            |         3183 | 4:17:25.747000      |            |
| TOTAL fr_FR                   |          |            |         3183 | 4:17:25.747000      | fr_FR      |

## Releases

| Name                                                                                               |   # speeches | Total Duration   | Language   |
|:---------------------------------------------------------------------------------------------------|-------------:|:-----------------|:-----------|
| [2018-09-02_fr_FR.zip](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/2018-09-02_fr_FR.zip) |         2579 | 3:25:44          | fr_FR      |

