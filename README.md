# AudioCorpFR


# New source workflow

1. add source to `./sources.json` for both epub and mp3 files
2. build transcript
   `$ python cli.py build_transcript_from_epub <source-name> <path-to-epub>`
   NB: this generate a new txt file with all
3. 

## Dev setup 

```sh
$ git clone git@gitlab.com:<your-fork>/AudioCorpFR.git
$ cd AudioCorpFR
$ pyenv virtualenv 3.6.6 audiocorpfr # OPTIONNAL 
$ pip install -r requirements.txt
$ pytest
```