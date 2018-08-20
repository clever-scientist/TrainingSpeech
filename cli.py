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
@click.argument('path_to_transcript')
def build_transcript(source_name, epub, path_to_transcript):
    sources = utils.read_sources()
    if source_name not in sources:
        click.echo(f'source "{source_name}" not found', err=True)
        return

    source = sources[source_name]

    res = click.edit(utils.read_epub(epub, path_to_xhtmls=source['ebook_parts']))
    if not res:
        return
    with open(path_to_transcript, 'w') as f:
        f.writelines(res)



play_audio_p = None


def check_alignment(fragment: dict, path_to_audio: str):

    todo = set()
    pool = ThreadPoolExecutor()

    def play_audio():
        global play_audio_p
        try:
            print(f'playing {" ".join(fragment["lines"])}')
            play_audio_p = subprocess.call(f'play -q {path_to_audio} tempo 1.5'.split(' '))
        except Exception as e:
            print(e)
            raise e

    todo.add(pool.submit(play_audio))

    def ask_what_next():
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

        global play_audio_p
        try:
            play_audio_p.kill()
        except:
            pass

        if answers['next'] == 'repeat':

            todo.add(pool.submit(play_audio))
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
@click.argument('transcript', type=click.Path(exists=True))
@click.argument('mp3', type=click.Path(exists=True))
@click.argument('path_to_alignment', type=click.Path(exists=False))
def build_alignment(source_name, transcript, mp3, path_to_alignment):
    assert utils.file_extension(mp3) == '.mp3', 'expect file to have `.mp3` extension'
    mp3 = os.path.abspath(mp3)
    sources = utils.read_sources()
    if source_name not in sources:
        click.echo(f'source "{source_name}" not found', err=True)
        return

    # build alignment
    task = Task('task_language=fra|os_task_file_format=json|is_text_type=plain')
    task.audio_file_path_absolute = os.path.abspath(mp3)
    task.text_file_path_absolute = os.path.abspath(transcript)
    task.sync_map_file_path_absolute = path_to_alignment
    executor = ExecuteTask(task=task)
    executor.execute()
    task.output_sync_map_file()


@cli.command()
@click.argument('source_name')
@click.argument('path_to_alignment', type=click.Path(exists=True))
@click.argument('mp3', type=click.Path(exists=True))
def check_alignments(source_name, path_to_alignment, mp3):
    with open(path_to_alignment, 'r') as f:
        alignment = json.load(f)

    sources = utils.read_sources()
    if source_name not in sources:
        click.echo(f'source "{source_name}" not found', err=True)
        return

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
            if i > 0:
                bar.update(1)
            bar.label = f'playing {" ".join(fragment["lines"])}'
            path_to_audio = f'/tmp/{source_name}.{fragment["id"]}.wav'
            check_alignment(fragment, path_to_audio)


if __name__ == '__main__':
    cli()
