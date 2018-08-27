import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED, as_completed

import click

from audiocorpfr import utils


CURRENT_DIR = os.path.dirname(__file__)


@click.group()
def cli():
    pass


@cli.command()
@click.argument('source_name')
def build_transcript(source_name):
    source = utils.get_source(source_name)
    path_to_epub = os.path.join(CURRENT_DIR, 'data/epubs/', source['ebook'])

    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    if os.path.isfile(path_to_transcript):
        click.confirm(text=f'{path_to_transcript} already exists. Override ?', default=False, abort=True)

    with open(path_to_transcript, 'w') as f:
        f.writelines(utils.read_epub(path_to_epub, path_to_xhtmls=source.get('ebook_parts', ['part1.xhtml'])))
    click.echo(f'transcript has been saved into {path_to_transcript}')


@cli.command()
@click.argument('source_name')
def build_alignment(source_name):
    from aeneas.executetask import ExecuteTask
    from aeneas.task import Task
    source = utils.get_source(source_name)
    mp3 = os.path.join(CURRENT_DIR, 'data/mp3/', source['audio'])

    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    path_to_alignment_tmp = os.path.join(CURRENT_DIR, f'/tmp/{source_name}.json')
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')

    # build alignment
    task = Task('task_language=fra|os_task_file_format=json|is_text_type=plain')
    task.audio_file_path_absolute = mp3
    task.text_file_path_absolute = os.path.abspath(path_to_transcript)
    task.sync_map_file_path_absolute = path_to_alignment_tmp
    executor = ExecuteTask(task=task)
    executor.execute()
    task.output_sync_map_file()
    with open(path_to_alignment_tmp) as source:
        original_alignment = json.load(source)
    alignment = [utils.cleanup_fragment(f) for f in original_alignment['fragments']]

    if any(f['duration'] == 0 for f in alignment):
        lines = ', '.join([str(i + 1) for i, f in enumerate(alignment) if f['duration'] == 0])
        raise Exception(f'lines {lines} led to empty alignment')

    with open(path_to_alignment, 'w') as dest:
        json.dump(
            obj=alignment,
            fp=dest,
            sort_keys=True,
            indent=2,
        )


play_audio_p = None


@cli.command()
@click.argument('source_name')
@click.option('--restart', default=False, help='use --restart to ignore already checked fragments')
def check_alignment(source_name, restart):
    import inquirer
    source = utils.get_source(source_name)
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
    path_to_mp3 = source['audio']
    if not os.path.isfile(path_to_alignment):
        raise Exception(f'alignment file missing for source {source_name}. see `python cli.py build_alignment --help`')

    with open(path_to_alignment, 'r') as f:
        fragments = json.load(f)

    # generate wav
    with open(path_to_mp3, 'rb') as f:
        f_hash = utils.sha1_file(f)
    path_to_wav = f'/tmp/{f_hash}.wav'
    # create wav from mp3 if do not exists yet
    if not os.path.exists(path_to_wav):
        retcode = subprocess.call(f'ffmpeg -loglevel quiet -y -i {path_to_mp3} -ac 1 -ar 16000 /tmp/{f_hash}.wav'.split(' '))
        assert retcode == 0

    # delete existing fragments if any
    path_to_recordings = os.path.join(CURRENT_DIR,  f'data/recordings/{source_name}/')
    subprocess.call(f'rm -f {path_to_recordings}*.wav'.split(' '))

    # generate fragments
    with click.progressbar(length=len(fragments), show_eta=True, label='cut audio into fragments') as bar:
        if not os.path.isdir(path_to_recordings):
            os.mkdir(path_to_recordings)

        def cut_fragment_audio(fragment):
            path_to_fragment_audio = os.path.join(path_to_recordings, f'{fragment["id"]}.wav')
            utils.cut_audio(path_to_wav, fragment['begin'], fragment['end'], path_to_fragment_audio)
            bar.update(1)

        with ThreadPoolExecutor() as executor:
            executor.map(cut_fragment_audio, fragments)

    def check_alignment(fragment: dict, path_to_audio: str):
        todo = set()
        pool = ThreadPoolExecutor()

        def play_audio():
            global play_audio_p
            try:
                play_audio_p = subprocess.Popen(f'play -q {path_to_audio} tempo 1.5'.split(' '))
                play_audio_p.wait()
            except Exception as e:
                print(e)
                raise e

        todo.add(pool.submit(play_audio))

        def ask_what_next():
            try:
                answers = inquirer.prompt([
                    inquirer.List(
                        'next',
                        message="\nWhat should I do ?",
                        choices=['continue', 'repeat'] + (['enable'] if fragment.get('disabled') else ['disable']) + ['quit'],
                    ),
                ])
            except Exception:
                answers = {'next': 'continue'}

            global play_audio_p
            try:
                play_audio_p.kill()
            except:
                pass

            if answers['next'] == 'repeat':
                todo.add(pool.submit(play_audio))
                todo.add(pool.submit(ask_what_next))
            elif answers['next'] == 'continue':
                fragment['approved'] = True
            elif answers['next'] == 'disable':
                fragment['disabled'] = True
                fragment.pop('approved', None)
            elif answers['next'] == 'enabled':
                fragment['approved'] = True
                fragment.pop('disabled', None)
            elif answers['next'] == 'quit':
                raise Exception('interrupted')
            else:
                raise NotImplementedError

        todo.add(pool.submit(ask_what_next))

        while todo:
            for future in as_completed(t for t in todo):
                todo.remove(future)
                future.result()

        pool.shutdown(wait=True)

    with click.progressbar(length=len(fragments), show_eta=True, label=f'playing #{0}: {fragments[0]["text"]}') as bar:
        for i, fragment in enumerate(fragments):
            bar.label = f'\nplaying #{i}: {fragment["text"]}'
            if i > 0:
                bar.update(1)
            if not restart and (fragment.get('approved') or fragment.get('disabled')):
                click.echo(f'skip fragment#{i}')
                continue
            path_to_audio = os.path.join(path_to_recordings, f'{fragment["id"]}.wav')
            check_alignment(fragment, path_to_audio)

            # save progress
            with open(path_to_alignment, 'w') as dest:
                json.dump(
                    obj=fragments,
                    fp=dest,
                    sort_keys=True,
                    indent=2,
                )


MAPPINGS = [
    (os.path.join(CURRENT_DIR, 's3://audiocorpfr/epubs/'), os.path.join(CURRENT_DIR, 'data/epubs/'), 'ebook'),  # epubs
    (os.path.join(CURRENT_DIR, 's3://audiocorpfr/mp3/'), os.path.join(CURRENT_DIR, 'data/mp3/'), 'audio'),  # mp3
    (os.path.join(CURRENT_DIR, 's3://audiocorpfr/recordings/'), os.path.join(CURRENT_DIR, 'data/recordings/'), 'recordings'),
]


@cli.command()
@click.option('-s', '--source_name', default=None)
def download(source_name):
    for s3, local, key in MAPPINGS:
        local = os.path.abspath(local)
        options = ''
        if source_name:
            source = utils.get_source(source_name)
            options += f'--exclude \'*\' --include \'{source[key]}\' '

        sync_cmd = f'aws s3 sync {options}{s3} {local}'
        print(sync_cmd)
        subprocess.call(sync_cmd.split(' '))


@cli.command()
@click.option('-s', '--source_name', default=None)
def upload(source_name):
    for s3, local, key in MAPPINGS:
        local = os.path.abspath(local)
        options = ''
        if source_name:
            source = utils.get_source(source_name)
            if key != 'recordings':
                options += f'--exclude \'*\' --include \'{source[key]}\' '
            else:
                s3 += f'{source_name}/'
                local += f'{source_name}/'
        sync_cmd = f'aws s3 sync {options}{local} {s3}'
        print(sync_cmd)
        subprocess.call(sync_cmd.split(' '))


if __name__ == '__main__':
    cli()
