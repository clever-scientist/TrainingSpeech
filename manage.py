import csv
import io
import json
import os
import subprocess
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, datetime
from typing import List
from zipfile import ZipFile

import click
from tabulate import tabulate
from termcolor import colored

import audiocorp
from audiocorp import utils, ffmpeg, sox, exceptions

CURRENT_DIR = os.path.dirname(__file__)
DEFAULT_SILENCE_MIN_DURATION = 0.07
DEFAULT_SILENCE_NOISE_LEVEL = -45


@click.group()
def cli():
    pass


@cli.command()
@click.argument('source_name')
def build_transcript(source_name):
    source = audiocorp.get_source(source_name)
    path_to_epub = os.path.join(CURRENT_DIR, 'data/epubs/', source['ebook'])

    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    if os.path.isfile(path_to_transcript):
        click.confirm(text=f'{path_to_transcript} already exists. Override ?', default=False, abort=True)

    with open(path_to_transcript, 'w') as f:
        f.writelines(utils.read_epub(path_to_epub, path_to_xhtmls=source.get('ebook_parts', ['part1.xhtml'])))

    subprocess.call(f'git add {path_to_transcript}'.split(' '))
    click.echo(f'transcript {path_to_transcript} added to git')


audio_player = None


def cut_fragment_audio(fragment: dict, input_file: str, output_dir: str):
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)

    fragment_hash = utils.get_fragment_hash(fragment)
    path_to_fragment_audio = os.path.join(output_dir, f'{fragment_hash}.wav')
    if not os.path.isfile(path_to_fragment_audio):
        ffmpeg.cut(input_file, path_to_fragment_audio, from_=fragment['begin'], to=fragment['end'])
    return path_to_fragment_audio


def cut_fragments_audio(fragments: List[dict], input_file: str, output_dir: str):
    # generate fragments
    with click.progressbar(length=len(fragments), show_eta=True, label='cut audio into fragments') as bar:
        def _cut(f: dict):
            cut_fragment_audio(f, input_file, output_dir)
            bar.update(1)

        with ThreadPoolExecutor() as executor:
            executor.map(_cut, fragments)


@cli.command()
@click.argument('source_name')
@click.option('-r', '--restart', is_flag=True, default=False, help='restart validation from scratch')
@click.option('-s', '--speed', default=1.3, help='set audio speed')
def check_alignment(source_name, restart, speed):
    import inquirer
    source = audiocorp.get_source(source_name)
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    path_to_mp3 = os.path.join(CURRENT_DIR, 'data/mp3', source['audio'])

    # generate wav if do not exists yet
    with open(path_to_mp3, 'rb') as f:
        file_hash = utils.hash_file(f)
    path_to_wav = f'/tmp/{file_hash}.wav'
    if not os.path.exists(path_to_wav):
        ffmpeg.convert(from_=path_to_mp3, to=f'/tmp/{file_hash}.wav', rate=16000, channels=1)

    # retrieve transcript
    with open(path_to_transcript) as f:
        transcript = [l.strip() for l in f.readlines()]
    transcript = [l for l in transcript if l]  # rm empty lines

    # detect silences
    silences = ffmpeg.list_silences(
        input_path=path_to_wav,
        min_duration=DEFAULT_SILENCE_MIN_DURATION,
        noise_level=DEFAULT_SILENCE_NOISE_LEVEL,
    )

    if not restart and os.path.isfile(path_to_alignment):
        with open(path_to_alignment) as f:
            existing_alignment = json.load(f)
    else:
        existing_alignment = []

    alignment = utils.build_alignment(
        transcript=transcript,
        path_to_audio=path_to_wav,
        existing_alignment=existing_alignment,
        silences=silences,
        generate_labels=True,
    )

    # delete existing fragments if any
    path_to_recordings = os.path.join(CURRENT_DIR,  f'/tmp/{source_name}/')

    def _check_alignment(index: int, alignment: List[dict]):
        click.clear()
        fragment = alignment[index]
        prev_fragments = alignment[max(i - 1, 0):i]
        next_fragments = alignment[i + 1:i + 3]

        print(colored(
            f'\nplaying #{i + 1:03d}: @@ {timedelta(seconds=fragment["begin"])}  {timedelta(seconds=fragment["end"])} @@',
            'yellow',
            attrs=['bold']
        ))
        if prev_fragments:
            for prev_ in prev_fragments:
                print(colored(prev_['text'], 'grey'))
        print(colored(fragment['text'], 'green', attrs=['bold']))
        if next_fragments:
            for next_ in next_fragments:
                print(colored(next_['text'], 'grey'))

        todo = set()
        pool = ThreadPoolExecutor()

        def play_audio():
            fragment_hash = utils.get_fragment_hash(fragment)
            path_to_audio = os.path.join(path_to_recordings, f'{fragment_hash}.wav')
            if not os.path.isfile(path_to_audio):
                cut_fragment_audio(fragment, path_to_wav, path_to_recordings)
            global audio_player

            with sox.play(path_to_audio, speed=speed) as player:
                audio_player = player

        def play_audio_slow():
            fragment_hash = utils.get_fragment_hash(fragment)
            path_to_audio = os.path.join(path_to_recordings, f'{fragment_hash}.wav')
            if not os.path.isfile(path_to_audio):
                cut_fragment_audio(fragment, path_to_wav, path_to_recordings)
            global audio_player

            with sox.play(path_to_audio) as player:
                audio_player = player

        todo.add(pool.submit(play_audio))

        def ask_right_transcript(current: List[str]):
            new_text = click.edit(text='\n'.join(current), require_save=False)
            return [
                l.strip()
                for l in new_text.strip().split('\n')
                if l.strip()
            ]

        def ask_what_next():
            current_silence = next((s for s in silences if s[0] <= fragment['end'] <= s[1]), None)
            if current_silence:
                prev_silence_start, prev_silence_end = silences[silences.index(current_silence) - 1]
                try:
                    next_silence_start, next_silence_end = silences[silences.index(current_silence) + 1]
                except IndexError:
                    next_silence_start = next_silence_end = fragment['end']
            else:
                prev_silence_start, prev_silence_end = next((s for s in reversed(silences) if s[1] <= fragment['end']))
                next_silence_start, next_silence_end = next((s for s in silences if s[0] >= fragment['end']))

            can_cut_on_prev_silence = prev_silence_start > fragment['begin']
            can_cut_on_next_silence = next_fragments and (next_fragments[0]['end'] > next_silence_start)
            try:
                next_: str = inquirer.prompt([
                    inquirer.List(
                        'next',
                        message="\nWhat should I do ?",
                        choices=(
                                ['approve', 'repeat'] +
                                (['go_back'] if prev_fragments else []) +
                                ['edit'] +
                                (['wrong_end__cut_on_previous_silence'] if can_cut_on_prev_silence else []) +
                                (['wrong_end__cut_on_next_silence'] if can_cut_on_next_silence else []) +
                                (['enable'] if fragment.get('disabled') else ['disable']) +
                                ['quit']),
                    ),
                ])['next']
            except TypeError:
                raise exceptions.QuitException
            except Exception:
                next_ = 'quit'

            global audio_player
            try:
                audio_player.kill()
            except:
                pass

            if next_ == 'repeat':
                todo.add(pool.submit(play_audio_slow))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'go_back':
                prev_fragments[-1].pop('disabled', None)
                prev_fragments[-1].pop('approved', None)
                raise exceptions.GoBackException
            elif next_ == 'edit':
                new_transcript = ask_right_transcript([t['text'] for t in prev_fragments + [fragment] + next_fragments])
                raise exceptions.SplitException(
                    start=i-len(prev_fragments),
                    end=i+len(next_fragments),
                    new_transcript=new_transcript,
                )
            elif next_ == 'wrong_end__cut_on_previous_silence':
                fragment['end'] = round(min(prev_silence_start + 0.5, prev_silence_end), 3)
                fragment['end_forced'] = True
                cut_fragment_audio(fragment, input_file=path_to_wav, output_dir=path_to_recordings)
                if next_fragments:
                    next_fragments[0]['begin'] = round(max(prev_silence_end - 0.5, prev_silence_start), 3)
                    next_fragments[0]['begin_forced'] = True
                    cut_fragment_audio(next_fragments[0], input_file=path_to_wav, output_dir=path_to_recordings)
                todo.add(pool.submit(play_audio))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'wrong_end__cut_on_next_silence':
                fragment['end'] = round(min(next_silence_start + 0.5, next_silence_end), 3)
                fragment['end_forced'] = True
                cut_fragment_audio(fragment, input_file=path_to_wav, output_dir=path_to_recordings)
                if next_fragments:
                    next_fragments[0]['begin'] = round(max(next_silence_end - 0.5, next_silence_start), 3)
                    next_fragments[0]['begin_forced'] = True
                    cut_fragment_audio(next_fragments[0], input_file=path_to_wav, output_dir=path_to_recordings)
                todo.add(pool.submit(play_audio))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'approve':
                fragment['approved'] = True
            elif next_ == 'pass':
                fragment.pop('approved', None)
            elif next_ == 'disable':
                fragment['disabled'] = True
                fragment.pop('approved', None)
            elif next_ == 'enabled':
                fragment['approved'] = True
                fragment.pop('disabled', None)
            elif next_ == 'quit':
                raise exceptions.QuitException
            else:
                raise NotImplementedError

        todo.add(pool.submit(ask_what_next))

        while todo:
            for future in as_completed(t for t in todo):
                todo.remove(future)
                future.result()

        pool.shutdown(wait=True)

    cut_fragments_audio(alignment, input_file=path_to_wav, output_dir=path_to_recordings)

    # iterate over successive fragments
    i = 0
    done = False
    while i < len(alignment) and not done:
        fragment = alignment[i]

        if fragment.get('approved') or fragment.get('disabled'):
            click.echo(f'skip fragment#{i} {fragment["text"]}')
            i += 1
            continue

        try:
            _check_alignment(index=i, alignment=alignment)
        except exceptions.GoBackException:
            i -= 1
            continue
        except exceptions.QuitException:
            try:
                audio_player.kill()
            except:
                pass
            exit(1)
        except exceptions.MergeException as e:
            left = e.left
            right = e.right
            right['begin'] = left['begin']
            left['end'] = right['end']
            left['text'] = right['text'] = f'{left["text"]} {right["text"]}'
            cut_fragment_audio(right, input_file=path_to_wav, output_dir=path_to_recordings)
            if fragment is right:
                alignment = alignment[:i - 1] + alignment[i:]
                i -= 2
            else:
                alignment = alignment[:i] + alignment[i + 1:]
                i -= 1

        except exceptions.SplitException as e:
            fragment.pop('approved', None)
            fragment.pop('disabled', None)
            audio_start: float = alignment[e.start]['begin']
            audio_end: float = alignment[e.end]['end']
            with tempfile.NamedTemporaryFile(suffix='.wav') as file_:
                sox.trim(path_to_wav, file_.name, from_=audio_start, to=audio_end)
                sub_alignment = utils.build_alignment(
                    transcript=e.new_transcript,
                    path_to_audio=file_.name,
                    existing_alignment=[
                        dict(
                            text=f['text'],
                            begin=f['begin'] - audio_start,
                            end=f['end'] - audio_start,
                            approved=f.get('approved', False),
                            disabled=f.get('disabled', False),
                        )
                        for f in alignment[e.start:e.end+1]
                    ],
                    silences=[
                        [max(s_start - audio_start, 0.), s_end - audio_start]
                        for s_start, s_end in silences
                        if s_end > audio_start and s_start < audio_end
                    ],
                    generate_labels=False,
                    language=source['language'],
                )

            for nf in sub_alignment:
                nf["begin"] += audio_start
                nf["end"] += audio_start

            alignment = (
                alignment[:e.start] +
                sub_alignment +
                alignment[e.end+1:]
            )
            i -= e.start

        # save progress
        with open(path_to_alignment, 'w') as dest:
            json.dump(
                obj=alignment,
                fp=dest,
                sort_keys=True,
                indent=2,
            )
        with open(path_to_transcript, 'w') as f:
            f.writelines('\n'.join(f['text'] for f in alignment) + '\n')

        i += 1
    click.confirm(
        text=colored(
            text=f'Done with {source_name}. Add changes to git ?',
            color='yellow',
            attrs=['bold'],
        ),
        default=True,
        abort=True
    )
    subprocess.call(f'git add {path_to_alignment} {path_to_transcript}'.split(' '))


MAPPINGS = [
    ('s3://audiocorp/epubs/', os.path.join(CURRENT_DIR, 'data/epubs/'), 'ebook'),  # epubs
    ('s3://audiocorp/mp3/', os.path.join(CURRENT_DIR, 'data/mp3/'), 'audio'),  # mp3
    ('s3://audiocorp/releases/', os.path.join(CURRENT_DIR, 'data/releases/'), 'releases'),
]


@cli.command()
@click.option('-s', '--source_name', default=None)
def download(source_name):
    for s3, local, key in MAPPINGS:
        if key == 'releases':
            continue
        local = os.path.abspath(local)
        options = ''
        if source_name:

            source = audiocorp.get_source(source_name)
            options += f'--exclude \'*\' --include \'{source[key]}\' '

        sync_cmd = f'aws s3 sync {options}{s3} {local}'
        print(sync_cmd)
        subprocess.call(sync_cmd.split(' '))


@cli.command()
@click.option('-s', '--source_name', default=None)
def upload(source_name):
    for s3, local, key in MAPPINGS:
        local = os.path.abspath(local)
        options = '--exclude .gitkeep --exclude \'*.zip\' '
        if source_name:
            if key == 'releases':
                continue
            source = audiocorp.get_source(source_name)
            options += f'--exclude \'*\' --include \'{source[key]}\' '

        sync_cmd = f'aws s3 sync {options}{local} {s3}'
        print(sync_cmd)
        subprocess.call(sync_cmd.split(' '))


@cli.command()
def stats():
    sources = audiocorp.sources()
    sources_data = []
    total_dur = timedelta(seconds=0)
    total_count = 0
    per_language_count = defaultdict(float)
    per_language_dur = defaultdict(timedelta)
    for name, metadata in sources.items():
        info = audiocorp.source_info(name)
        sources_data.append([
            name,
            info['status'],
            f'{int(info["progress"] * 100)} %',
            info['approved_count'],
            info['approved_duration'],
            metadata['language'],
        ])
        total_dur += info['approved_duration']
        total_count += info['approved_count']
        per_language_count[metadata['language']] += info['approved_count']
        per_language_dur[metadata['language']] += info['approved_duration']

    sources_data.append([])
    sources_data.append([
        'TOTAL',
        ''
        '',
        '',
        total_count,
        total_dur,
    ])
    for language, count in per_language_count.items():
        sources_data.append([
            f'TOTAL {language}',
            ''
            '',
            '',
            count,
            per_language_dur[language],
            language,
        ])
    print('\n' + tabulate(
        sources_data,
        headers=['Source', 'Status', 'Progress', '# speeches', 'Speeches Duration', 'Language'],
        tablefmt='pipe',
    ))


@cli.command()
def release():
    per_language_sources = defaultdict(list)
    for name, metadata in audiocorp.sources().items():
        info = audiocorp.source_info(name)
        if info['status'] == 'DONE':
            per_language_sources[metadata['language']].append(name)
    today_str = datetime.now().isoformat()[:10]
    releases_data = []
    for language, sources in per_language_sources.items():
        release_name = f'{today_str}_{language}.zip'
        path_to_release = os.path.join(CURRENT_DIR, 'data/releases', release_name)
        with ZipFile(path_to_release, 'w') as zip_file:
            # generate fragments
            fragments = []
            with click.progressbar(length=len(sources), show_eta=True, label='find sources') as bar:
                for source_name in sources:
                    metadata = audiocorp.get_source(source_name)
                    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
                    path_to_mp3 = os.path.join(CURRENT_DIR, 'data/mp3', metadata['audio'])
                    # generate wav if do not exists yet
                    with open(path_to_mp3, 'rb') as f:
                        file_hash = utils.hash_file(f)
                    path_to_wav = f'/tmp/{file_hash}.wav'
                    if not os.path.exists(path_to_wav):
                        ffmpeg.convert(from_=path_to_mp3, to=f'/tmp/{file_hash}.wav', rate=16000, channels=1)

                    with open(path_to_alignment) as file_:
                        fragments += [
                            dict(name=f'{source_name}_{i + 1:04d}', source_file=path_to_wav, **f)
                            for i, f in enumerate(json.load(file_))
                            if f.get('approved')
                        ]
                bar.update(1)

            with click.progressbar(length=len(fragments), show_eta=True, label='cut audio into fragments') as bar:
                for fragment in fragments:
                    fragment_audio_path = cut_fragment_audio(fragment, fragment['source_file'], '/tmp/')
                    archive_audio_path = f'{fragment["name"]}.wav'
                    fragment.update(
                        path=archive_audio_path,
                    )
                    zip_file.write(fragment_audio_path, arcname=archive_audio_path)
                    os.unlink(fragment_audio_path)
                    bar.update(1)

            # create CSV
            string_buffer = io.StringIO()
            writer = csv.DictWriter(string_buffer, delimiter=';', fieldnames=['path', 'duration', 'text'])
            writer.writeheader()
            writer.writerows([
                dict(path=f['path'], duration=round(f['end'] - f['begin'], 3), text=f['text'])
                for f in fragments
            ])
            zip_file.writestr('data.csv', string_buffer.getvalue())
            releases_data.append([
                f'[{release_name}](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/{release_name})',
                len(fragments),
                timedelta(seconds=round(sum(round(f['end'] - f['begin'], 3) for f in fragments))),
                language,
            ])
    print('\n' + tabulate(
        releases_data,
        headers=['Name', '# speeches', 'Total Duration', 'Language'],
        tablefmt='pipe',
    ))


if __name__ == '__main__':
    cli()
