import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, wait, ProcessPoolExecutor, FIRST_COMPLETED
from time import sleep
import inquirer

import click
import vlc
from aeneas.executetask import ExecuteTask
from aeneas.task import Task

from audiocorpfr import utils


@click.group()
def cli():
    pass


@cli.command()
@click.argument('source_name')
@click.argument('epub')
@click.argument('mp3')
def process_source(source_name, epub, mp3):
    pass



@cli.command()
@click.argument('source_name')
@click.argument('epub', type=click.Path(exists=True))
def build_transcript_from_epub(source_name, epub):
    sources = utils.read_sources()
    if source_name not in sources:
        click.echo(f'source "{source_name}" not found', err=True)
        return

    source = sources[source_name]
    if source.get('transcript') and os.path.isfile(source['transcript']):
        click.echo(f'transcript already exists for source "{source_name}", see {source["transcript"]}', err=True)
        return
    path_to_transcript = f'./.tmp/{source_name}.txt'
    res = click.edit(utils.read_epub(epub, path_to_xhtmls=source['ebook_parts']))
    if not res:
        return
    with open(path_to_transcript, 'w') as f:
        f.writelines(res)
    source['transcript'] = path_to_transcript
    utils.update_sources(sources)


play_audio_f = None


def check_alignment(fragment: dict, path_to_audio: str):
    global play_audio_f
    todo = set()
    pool = ThreadPoolExecutor()

    def play_audio():
        try:
            print(f'playing {" ".join(fragment["lines"])}')
            subprocess.call(f'play -q {path_to_audio} tempo 1.5'.split(' '))
        except Exception as e:
            print(e)
            raise e

    play_audio_f = pool.submit(play_audio)
    todo.add(play_audio_f)

    def ask_what_next():
        global play_audio_f
        try:
            answers = inquirer.prompt([
                inquirer.List(
                    'next',
                    message="What should I do ?",
                    choices=['continue', 'repeat', 'quit'],
                ),
            ])
        except Exception:
            answers = {'next': 'quit'}

        if answers['next'] == 'repeat':
            play_audio_f.cancel()
            play_audio_f = pool.submit(play_audio)
            todo.add(play_audio_f)
            todo.add(pool.submit(ask_what_next))
        elif answers['next'] == 'continue':
            pass
        elif answers['next'] == 'quit':
            pass
        else:
            raise NotImplementedError

    todo.add(pool.submit(ask_what_next))

    while todo:
        done, _ = wait(todo, return_when=FIRST_COMPLETED)
        for future in done:
            todo.remove(future)
            try:
                future.result()
            except Exception:
                pool.shutdown(wait=True)
                raise
    pool.shutdown(wait=True)


@cli.command()
@click.argument('source_name')
@click.argument('mp3', type=click.Path(exists=True))
def align(source_name, mp3):
    assert utils.file_extension(mp3) == '.mp3', 'expect file to have `.mp3` extension'
    mp3 = os.path.abspath(mp3)

    sources = utils.read_sources()
    if source_name not in sources:
        click.echo(f'source "{source_name}" not found', err=True)
        return

    source = sources[source_name]
    if not source.get('transcript'):
        click.echo(f'transcript not found', err=True)
        return
    path_to_alignment = f'/tmp/{source_name}.json'
    if not os.path.isfile(path_to_alignment):
        # build alignment
        task = Task('task_language=fra|os_task_file_format=json|is_text_type=plain')
        task.audio_file_path_absolute = os.path.abspath(mp3)
        task.text_file_path_absolute = source["transcript"]
        task.sync_map_file_path_absolute = path_to_alignment
        executor = ExecuteTask(task=task)
        executor.execute()
        task.output_sync_map_file()

    with open(path_to_alignment, 'r') as f:
        alignment = json.load(f)

    fragments = alignment['fragments']

    # generate wav
    wav = re.sub(r'\.mp3$', '.wav', mp3)
    retcode = subprocess.call(f'ffmpeg -loglevel quiet -y -i {mp3} -ac 1 -ar 16000 {wav}'.split(' '))
    assert retcode == 0

    # delete existing fragments if any
    subprocess.call(f'rm -f /tmp/{source_name}.*.wav'.split(' '))

    # generate fragments
    with click.progressbar(length=len(fragments), show_eta=True, label='cut audio into fragments') as bar:
        def cut_fragment_audio(fragment):
            audio_begin = max(float(fragment['begin']) - 0.2, 0)
            audio_end = float(fragment['end']) - 0.2
            audio_dur = audio_end - audio_begin
            path_to_audio = f'/tmp/{source_name}.{fragment["id"]}.wav'
            assert audio_dur > 0
            utils.cut_audio(wav, audio_begin, audio_end, path_to_audio)
            bar.update(1)
        with ThreadPoolExecutor() as executor:
            executor.map(cut_fragment_audio, fragments)

    with click.progressbar(length=len(fragments), show_eta=True) as bar:
        for i, fragment in enumerate(fragments):
            bar.update(1 if i > 0 else 0)
            bar.label = f'playing {" ".join(fragment["lines"])}'
            path_to_audio = f'/tmp/{source_name}.{fragment["id"]}.wav'
            check_alignment(fragment, path_to_audio)


if __name__ == '__main__':
    cli()
