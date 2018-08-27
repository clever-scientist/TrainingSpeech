# AudioCorpFR



## Common workflows

### 1. Add New source workflow (contributors only)

1. retrieve epub and corresponding mp3 file from [atramenta](atramenta.net/audiobooks) and store them into `./data/epubs` and `./data/mp3` (respectively)
2. create new source into `./sources.json`


### 2. Generate transcript for an existing source

```sh
python cli.py build_transcript <source-name>`
```


## Dev setup 

```sh
$ git clone git@gitlab.com:<your-fork>/AudioCorpFR.git
$ cd AudioCorpFR
$ pyenv virtualenv 3.6.6 audiocorpfr # OPTIONNAL 
$ pip install -r requirements.txt
$ pytest
```