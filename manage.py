import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import click
from tabulate import tabulate

import audiocorpfr
from audiocorpfr import utils, ffmpeg, sox
from audiocorpfr.exceptions import GoBackException, QuitException, MergeException

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
    silences = ffmpeg.list_silences(input_path=mp3)
    alignment = utils.fix_alignment(alignment, silences)

    if any(f['end'] - f['begin'] == 0 for f in alignment):
        lines = ', '.join([str(i + 1) for i, f in enumerate(alignment) if f['end'] - f['begin'] == 0])
        raise Exception(f'lines {lines} led to empty alignment')

    with open(path_to_alignment, 'w') as dest:
        json.dump(
            obj=alignment,
            fp=dest,
            sort_keys=True,
            indent=2,
        )


audio_player = None


@cli.command()
@click.argument('source_name')
@click.option('--restart', default=False, help='use --restart to ignore already checked fragments')
def check_alignment(source_name, restart):
    import inquirer
    source = utils.get_source(source_name)
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
    path_to_mp3 = os.path.join(CURRENT_DIR, 'data/mp3', source['audio'])
    if not os.path.isfile(path_to_alignment):
        raise FileNotFoundError(f'alignment file missing for {source_name}. see `python cli.py build_alignment --help`')

    with open(path_to_alignment, 'r') as f:
        fragments = json.load(f)

    # generate wav
    with open(path_to_mp3, 'rb') as f:
        f_hash = utils.sha1_file(f)
    path_to_wav = f'/tmp/{f_hash}.wav'
    # create wav from mp3 if do not exists yet
    if not os.path.exists(path_to_wav):
        ffmpeg.convert(from_=path_to_mp3, to=f'/tmp/{f_hash}.wav', rate=16000, channels=1)

    # delete existing fragments if any
    path_to_recordings = os.path.join(CURRENT_DIR,  f'data/recordings/{source_name}/')
    subprocess.call(f'rm -f {path_to_recordings}*.wav'.split(' '))

    def cut_fragment_audio(fragment: dict):
        path_to_fragment_audio = os.path.join(path_to_recordings, f'{fragment["id"]}.wav')
        ffmpeg.cut(path_to_wav, path_to_fragment_audio, from_=fragment['begin'], to=fragment['end'])

    # generate fragments
    with click.progressbar(length=len(fragments), show_eta=True, label='cut audio into fragments') as bar:
        if not os.path.isdir(path_to_recordings):
            os.mkdir(path_to_recordings)

        def _cut(f: dict):
            cut_fragment_audio(f)
            bar.update(1)

        with ThreadPoolExecutor() as executor:
            executor.map(_cut, fragments)

    def _check_alignment(index: int, path_to_audio: str, fragments):
        fragment = fragments[index]
        is_last_fragment = index == len(fragments) - 1
        todo = set()
        pool = ThreadPoolExecutor()

        def play_audio():
            global audio_player
            with sox.play(path_to_audio, speed=1.25) as player:
                audio_player = player

        todo.add(pool.submit(play_audio))

        def ask_right_end():
            try:
                right_end: str = inquirer.prompt([
                    inquirer.Text(
                        'end',
                        message="\nWhat is the right end ?",
                        default=str(fragment['end']),
                        validate=lambda _, x: utils.is_float(x),
                    ),
                ])['end']
            except TypeError:
                return fragment['end']
            return float(right_end)

        def ask_right_text():
            try:
                right_text: str = inquirer.prompt([
                    inquirer.Text(
                        'text',
                        message="\nWhat is the right text ?",
                        default=str(fragment['text']),
                        validate=lambda _,x: bool(x),
                    ),
                ])['text']
            except TypeError:
                return fragment['text']
            return right_text

        def ask_what_next():
            try:
                next_: str = inquirer.prompt([
                    inquirer.List(
                        'next',
                        message="\nWhat should I do ?",
                        choices=(
                                ['continue', 'repeat'] +
                                (['go_back'] if index > 0 else []) +
                                ['wrong_end'] +
                                (['merge_previous'] if index > 0 else []) +
                                ['wrong_text'] +
                                (['enable'] if fragment.get('disabled') else ['disable']) +
                                ['quit']),
                    ),
                ])['next']
            except TypeError:
                raise QuitException
            except Exception:
                next_ = 'continue'

            global audio_player
            try:
                audio_player.kill()
            except:
                pass

            if next_ == 'repeat':
                todo.add(pool.submit(play_audio))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'go_back':
                prev_fragment = fragments[index - 1]
                prev_fragment.pop('disabled', None)
                prev_fragment.pop('approved', None)
                raise GoBackException
            elif next_ == 'wrong_text':
                fragment['text'] = ask_right_text()
            elif next_ == 'wrong_end':
                new_end = ask_right_end()
                fragment['end'] = new_end
                fragment['duration'] = fragment['end'] - fragment['begin']
                cut_fragment_audio(fragment)
                if not is_last_fragment:
                    next_fragment = fragments[index + 1]
                    next_fragment['begin'] = new_end - 0.1
                    next_fragment['duration'] = next_fragment['end'] - next_fragment['begin']
                    cut_fragment_audio(next_fragment)
                todo.add(pool.submit(play_audio))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'continue':
                fragment['approved'] = True
            elif next_ == 'disable':
                fragment['disabled'] = True
                fragment.pop('approved', None)
            elif next_ == 'enabled':
                fragment['approved'] = True
                fragment.pop('disabled', None)
            elif next_ == 'quit':
                raise QuitException
            elif next_ == 'merge_previous':
                raise MergeException
            else:
                raise NotImplementedError

        todo.add(pool.submit(ask_what_next))

        while todo:
            for future in as_completed(t for t in todo):
                todo.remove(future)
                future.result()

        pool.shutdown(wait=True)

    with click.progressbar(length=len(fragments), show_eta=True, label=f'playing #{0}: {fragments[0]["text"]}') as bar:
        i = 0
        done = False
        while i < len(fragments) and not done:
            fragment = fragments[i]
            bar.label = f'\nplaying #{i}: {fragment["text"]}'
            if i > 0:
                bar.update(1)

            if not restart and (fragment.get('approved') or fragment.get('disabled')):
                click.echo(f'skip fragment#{i} {fragment["text"]}')
                i += 1
                continue

            path_to_audio = os.path.join(path_to_recordings, f'{fragment["id"]}.wav')
            try:
                _check_alignment(index=i, path_to_audio=path_to_audio, fragments=fragments)
            except GoBackException:
                i -= 1
                continue
            except QuitException:
                break
            except MergeException:
                prev_fragment = fragments[i - 1]
                fragment['begin'] = prev_fragment['begin']
                fragment['text'] = f'{prev_fragment["text"]} {fragment["text"]}'
                fragment['duration'] = fragment['end'] - fragment['begin']
                cut_fragment_audio(fragment)
                fragments = fragments[:i-1] + fragments[i:]
                i -= 2

            # save progress
            with open(path_to_alignment, 'w') as dest:
                json.dump(
                    obj=fragments,
                    fp=dest,
                    sort_keys=True,
                    indent=2,
                )
            i += 1


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


@cli.command()
def stats():
    sources = utils.read_sources()
    sources_data = []
    total_dur = timedelta(seconds=0)
    total_count = 0
    for name, _ in sources.items():
        info = audiocorpfr.source_info(name)
        sources_data.append([
            name,
            info['status'],
            f'{int(info["progress"] * 100)} %',
            info['approved_duration'],
            info['approved_count'],
        ])
        total_dur += info['approved_duration']
        total_count += info['approved_count']

    print(tabulate(
        sources_data,
        headers=['Source', 'Status', 'Progress', 'Approved Duration', 'Approved Count'],
        tablefmt='pipe',
    ))
    print(f'\nTotal: {total_dur} with {total_count} fragments')


@cli.command()
@click.argument('source_name')
def generate_labels(source_name: str):
    source = utils.get_source(source_name)
    path_to_audio = os.path.join(CURRENT_DIR, 'data/mp3/', source['audio'])
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
    if not os.path.isfile(path_to_alignment):
        raise FileNotFoundError(f'alignment file missing for {source_name}. see `python cli.py build_alignment --help`')
    print(f'detecting silences from {path_to_audio}')
    silences = ffmpeg.list_silences(input_path=path_to_audio)
    print('done')
    path_to_silences_labels = f'/tmp/{source_name}_silences_labels.txt'
    with open(path_to_silences_labels, 'w') as f:
        f.writelines('\n'.join([f'{s}\t{e}\tsilence{i+1}' for i, (s, e) in enumerate(silences)]) + '\n')

    path_to_alignment_labels = f'/tmp/{source_name}_alignments_labels.txt'
    with open(path_to_alignment) as alignments_f, open(path_to_alignment_labels, 'w') as labels_f:
        alignments = json.load(alignments_f)
        labels_f.writelines('\n'.join([f'{f["begin"]}\t{f["end"]}\t#{i+1}:{f["text"]}' for i, f in enumerate(alignments)]) + '\n')
    print(f'labels availables at\n{path_to_alignment_labels}\n{path_to_silences_labels}')


if __name__ == '__main__':
    cli()
