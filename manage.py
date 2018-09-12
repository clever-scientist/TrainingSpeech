import csv
import io
import json
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import timedelta, datetime
from typing import List, Tuple

import click
import numpy as np
from tabulate import tabulate
from termcolor import colored

import audiocorp
from audiocorp import utils, ffmpeg, sox, exceptions

CURRENT_DIR = os.path.dirname(__file__)


logger = logging.getLogger()


@click.group()
def cli():
    pass


@cli.command()
@click.argument('source_name')
@click.option('-y', '--yes', is_flag=True, default=False, help='override existing transcript if any')
@click.option('--add-to-git/--no-add-to-git', is_flag=True, default=True)
def build_transcript(source_name, yes, add_to_git):
    source = audiocorp.get_source(source_name)
    path_to_epub = os.path.join(CURRENT_DIR, 'data/epubs/', source['ebook'])

    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    if yes is False and os.path.isfile(path_to_transcript):
        click.confirm(text=f'{path_to_transcript} already exists. Override ?', default=False, abort=True)

    with open(path_to_transcript, 'w') as f:
        f.writelines(utils.read_epub(path_to_epub, path_to_xhtmls=source.get('ebook_parts', ['part1.xhtml'])))

    if add_to_git:
        subprocess.call(f'git add {path_to_transcript}'.split(' '))
    click.echo(f'transcript {path_to_transcript} added to git')


audio_player = None


def cut_fragment_audio(fragment: dict, input_file: str, output_dir: str=utils.CACHE_DIR):
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)

    fragment_hash = utils.get_fragment_hash(fragment)
    path_to_fragment_audio = os.path.join(output_dir, f'{fragment_hash}.wav')
    if not os.path.isfile(path_to_fragment_audio):
        ffmpeg.cut(input_file, path_to_fragment_audio, from_=fragment['begin'], to=fragment['end'])
    return path_to_fragment_audio


def cut_fragments_audio(fragments: List[dict], input_file: str, output_dir: str=utils.CACHE_DIR):
    # generate fragments
    with click.progressbar(length=len(fragments), show_eta=True, label='cut audio into fragments') as bar:
        def _cut(f: dict):
            p = cut_fragment_audio(f, input_file, output_dir)
            bar.update(1)
            return p

        with ThreadPoolExecutor() as executor:
            return executor.map(_cut, fragments)


@cli.command()
@click.argument('source_name')
@click.option('-r', '--restart', is_flag=True, default=False, help='restart validation from scratch')
@click.option('-s', '--speed', default=1.3, help='set audio speed')
@click.option('-ar', '--audio-rate', default=16000)
@click.option('-nc', '--no-cache', is_flag=True, default=None)
@click.option('-f', '--fast', is_flag=True, default=False)
def check_alignment(source_name, restart, speed, audio_rate, no_cache, fast):
    import inquirer
    source = audiocorp.get_source(source_name)
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    path_to_mp3 = os.path.join(CURRENT_DIR, 'data/mp3', source['audio'])

    if no_cache and os.path.isdir(utils.CACHE_DIR):
        shutil.rmtree(utils.CACHE_DIR)
        os.mkdir(utils.CACHE_DIR)

    # generate wav if do not exists yet
    with open(path_to_mp3, 'rb') as f:
        file_hash = utils.hash_file(f)
    path_to_wav = os.path.join(utils.CACHE_DIR, f'{file_hash}.wav')
    if not os.path.exists(path_to_wav):
        ffmpeg.convert(
            from_=path_to_mp3,
            to=os.path.join(utils.CACHE_DIR, f'{file_hash}.wav'),
            rate=audio_rate,
            channels=1
        )

    # retrieve transcript
    with open(path_to_transcript) as f:
        transcript = [l.strip() for l in f.readlines()]
    transcript = [l for l in transcript if l]  # rm empty lines

    # detect silences
    silences = ffmpeg.list_silences(
        input_path=path_to_wav,
        min_duration=utils.DEFAULT_SILENCE_MIN_DURATION,
        noise_level=utils.DEFAULT_SILENCE_NOISE_LEVEL,
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

    def _check_alignment(index: int, alignment: List[dict]):
        click.clear()
        fragment = alignment[index]
        prev_fragments = alignment[max(i - 1, 0):i]
        next_fragments = alignment[i + 1:i + 3]

        print(colored(
            f'\nplaying #{i + 1:03d}: @@ {timedelta(seconds=fragment["begin"])}  {timedelta(seconds=fragment["end"])} ({fragment["end"] - fragment["begin"]:0.3f}) @@',  # noqa
            'yellow',
            attrs=['bold']
        ))
        if prev_fragments:
            for prev_ in prev_fragments:
                print(colored(prev_['text'], 'grey'))
        print(colored(fragment['text'], 'magenta' if fragment.get('warn') else 'green', attrs=['bold']))
        if next_fragments:
            for next_ in next_fragments:
                print(colored(next_['text'], 'grey'))

        todo = set()
        pool = ThreadPoolExecutor()

        def play_audio():
            path_to_audio = cut_fragment_audio(fragment, path_to_wav)
            global audio_player

            with sox.play(path_to_audio, speed=speed) as player:
                audio_player = player

        def play_audio_slow():
            path_to_audio = cut_fragment_audio(fragment, path_to_wav)
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
            if prev_fragments:
                silence_before, silence_between, silence_after = utils.transition_silences(
                    prev_fragments[-1],
                    fragment,
                    silences
                )
                can_cut_start_on_prev_silence = silence_before is not None
                can_cut_start_on_next_silence = silence_after is not None
            else:
                can_cut_start_on_prev_silence = can_cut_start_on_next_silence = False
            if next_fragments:
                silence_before, silence_between, silence_after = utils.transition_silences(
                    fragment,
                    next_fragments[0],
                    silences
                )
                can_cut_end_on_prev_silence = silence_before is not None
                can_cut_end_on_next_silence = silence_after is not None
            else:
                can_cut_end_on_prev_silence = can_cut_end_on_next_silence = False


            try:
                next_: str = inquirer.prompt([
                    inquirer.List(
                        'next',
                        message="\nWhat should I do ?",
                        choices=(
                                ['approve', 'repeat'] +
                                (['go_back'] if prev_fragments else []) +
                                ['edit'] +
                                (['wrong_start__cut_on_previous_silence'] if can_cut_start_on_prev_silence else []) +
                                (['wrong_start__cut_on_next_silence'] if can_cut_start_on_next_silence else []) +
                                (['wrong_end__cut_on_previous_silence'] if can_cut_end_on_prev_silence else []) +
                                (['wrong_end__cut_on_next_silence'] if can_cut_end_on_next_silence else []) +
                                (['enable'] if fragment.get('disabled') else ['disable']) +
                                ['toggle_fast_mode','quit']),
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
            elif next_ == 'toggle_fast_mode':
                raise exceptions.ToggleFastModeException
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

            elif next_ == 'wrong_start__cut_on_previous_silence':
                prev_fragment = prev_fragments[-1]
                silence_before, _, _ = utils.transition_silences(prev_fragment, fragment, silences)
                fragment['begin'] = round(max(silence_before[1] - 0.35, silence_before[1]), 3)
                prev_fragment['end'] = round(min(silence_before[0] + 0.35, silence_before[1]), 3)
                cut_fragment_audio(fragment, input_file=path_to_wav)
                cut_fragment_audio(fragment, input_file=path_to_wav)
                todo.add(pool.submit(play_audio))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'wrong_start__cut_on_next_silence':
                prev_fragment = prev_fragments[-1]
                _, _, silence_after = utils.transition_silences(prev_fragment, fragment, silences)
                prev_fragment['end'] = round(min(silence_after[0] + 0.35, silence_after[1]), 3)
                fragment['begin'] = round(max(silence_after[1] - 0.35, silence_after[0]), 3)
                cut_fragment_audio(prev_fragment, input_file=path_to_wav)
                cut_fragment_audio(fragment, input_file=path_to_wav)
                todo.add(pool.submit(play_audio))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'wrong_end__cut_on_previous_silence':
                next_fragment = next_fragments[0]
                silence_before, _, _ = utils.transition_silences(fragment, next_fragment, silences)
                fragment['end'] = round(min(silence_before[0] + 0.35, silence_before[1]), 3)
                next_fragment['begin'] = round(max(silence_before[1] - 0.35, silence_before[1]), 3)
                cut_fragment_audio(fragment, input_file=path_to_wav)
                cut_fragment_audio(next_fragment, input_file=path_to_wav)
                todo.add(pool.submit(play_audio))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'wrong_end__cut_on_next_silence':
                next_fragment = next_fragments[0]
                _, _, silence_after = utils.transition_silences(fragment, next_fragment, silences)
                fragment['end'] = round(min(silence_after[0] + 0.35, silence_after[1]), 3)
                next_fragment['begin'] = round(max(silence_after[1] - 0.35, silence_after[0]), 3)
                cut_fragment_audio(fragment, input_file=path_to_wav)
                cut_fragment_audio(next_fragment, input_file=path_to_wav)
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

    cut_fragments_audio(alignment, input_file=path_to_wav)

    # iterate over successive fragments
    i = 0
    done = False
    while i < len(alignment) and not done:
        fragment = alignment[i]

        if fragment.get('approved') or fragment.get('disabled'):
            click.echo(f'skip fragment#{i} {fragment["text"]}')
            i += 1
            continue

        if fast and i != 0 and i < len(alignment) - 1 and not fragment.get('warn'):
            fragment.update(
                approved=True,
                approved_auto=True,
            )
            click.echo(f'approve fragment#{i} {fragment["text"]}')
            i += 1
            continue

        try:
            _check_alignment(index=i, alignment=alignment)
        except exceptions.ToggleFastModeException:
            fast = not fast
            continue
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
            cut_fragment_audio(right, input_file=path_to_wav)
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
            cut_fragments_audio(alignment, input_file=path_to_wav)
            i -= e.start

        # save progress
        with open(path_to_alignment, 'w') as dest:
            to_save = deepcopy(alignment)
            for f in to_save:
                f.pop('warn', None)
            json.dump(
                obj=to_save,
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
    total_available = timedelta(seconds=0)
    total_count = 0
    per_language_count = defaultdict(float)
    per_language_dur = defaultdict(timedelta)
    per_language_available = defaultdict(timedelta)
    for name, metadata in sources.items():
        info = audiocorp.source_info(name)
        path_to_mp3 = os.path.join(CURRENT_DIR, 'data/mp3', metadata['audio'])
        if os.path.isfile(path_to_mp3):
            mp3_duration = timedelta(seconds=ffmpeg.audio_duration(path_to_mp3))
        else:
            mp3_duration = None
        sources_data.append([
            name,
            info['status'],
            f'{int(info["progress"] * 100)} %',
            info['approved_count'],
            utils.format_timedelta(info['approved_duration']),
            utils.format_timedelta(mp3_duration) if mp3_duration else '?',
            metadata['language'],
        ])
        total_dur += info['approved_duration']
        total_count += info['approved_count']
        per_language_count[metadata['language']] += info['approved_count']
        per_language_dur[metadata['language']] += info['approved_duration']
        if mp3_duration:
            per_language_available[metadata['language']] += mp3_duration
            total_available += mp3_duration

    sources_data.append([])
    sources_data.append([
        'TOTAL',
        ''
        '',
        '',
        total_count,
        utils.format_timedelta(total_dur),
        utils.format_timedelta(total_available),
    ])
    for language, count in per_language_count.items():
        sources_data.append([
            f'TOTAL {language}',
            ''
            '',
            '',
            count,
            utils.format_timedelta(per_language_dur[language]),
            utils.format_timedelta(per_language_available[language]),
            language,
        ])
    print('\n' + tabulate(
        sources_data,
        headers=['Source', 'Status', 'Progress', '# speeches', 'Speeches duration', 'mp3 duration', 'Language'],
        tablefmt='pipe',
    ))


@cli.command()
@click.option('-r', '--audio-rate', default=16000)
@click.option('-l', '--language', type=click.Choice(['fr_FR']), default=None)
def release(audio_rate, language):
    per_language_sources = defaultdict(list)
    per_language_speakers = defaultdict(set)
    for name, metadata in audiocorp.sources().items():
        info = audiocorp.source_info(name)
        if info['status'] in {'DONE', 'WIP'}:
            per_language_sources[metadata['language']].append((name, metadata, info))
            per_language_speakers[metadata['language']].add(metadata['speaker'])
    today_str = datetime.now().isoformat()[:10]
    releases_data = []

    for source_language, sources in per_language_sources.items():
        if language and source_language != language:
            continue

        release_name = f'{today_str}_{source_language}'
        path_to_release = os.path.join(CURRENT_DIR, 'data/releases', f'{release_name}.zip')
        print(f'start building {release_name}')
        # generate fragments
        p_label = f'convert mp3 files to mono {audio_rate}Hz wav'
        with click.progressbar(length=len(sources), show_eta=True, label=p_label) as bar:
            with ThreadPoolExecutor() as executor:
                def _process_source(source_data: Tuple[str, dict, dict]):
                    source_name, metadata, _ = source_data
                    try:
                        path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
                        path_to_mp3 = os.path.join(CURRENT_DIR, 'data/mp3', metadata['audio'])
                        # generate wav if do not exists yet
                        with open(path_to_mp3, 'rb') as f:
                            file_hash = utils.hash_file(f)
                        path_to_wav = os.path.join(utils.CACHE_DIR, f'{file_hash}.wav')
                        if not os.path.exists(path_to_wav):
                            ffmpeg.convert(from_=path_to_mp3, to=path_to_wav, rate=audio_rate, channels=1)

                        with open(path_to_alignment) as file_:
                            source_fragments = [
                                dict(name=f'{source_name}_{i + 1:04d}', source_file=path_to_wav, **f)
                                for i, f in enumerate(json.load(file_))
                                if f.get('approved')
                            ]
                        bar.update(1)
                        return source_fragments
                    except Exception as e:
                        print(f'cannot process source {source_name}. {e}')
                        raise e

                fragments = []
                for source_fragments in executor.map(_process_source, sources):
                    fragments += source_fragments

        # generate fragments
        p_label = f'cut audio fragments'
        with click.progressbar(length=len(fragments), show_eta=True, label=p_label) as bar, ThreadPoolExecutor() as executor:

            def _cut(f: dict):
                try:
                    p = cut_fragment_audio(f, f['source_file'])
                    bar.update(1)
                    return p
                except Exception as e:
                    print(f'cannot extract fragment {fragment["name"]}. {e}')

            audio_fragments_pathes = executor.map(_cut, fragments)

        p_label = f'generate {release_name}.zip file'
        with click.progressbar(length=len(fragments) + 1, show_eta=True, label=p_label) as bar, zipfile.ZipFile(path_to_release, 'w') as zip_file:
            # create CSV
            string_buffer = io.StringIO()
            writer = csv.DictWriter(string_buffer, delimiter=';', fieldnames=['path', 'duration', 'text'])
            writer.writeheader()

            for fragment, tmp_audio in zip(fragments, audio_fragments_pathes):
                archive_audio_path = f'{fragment["name"]}.wav'
                zip_file.write(tmp_audio, arcname=archive_audio_path, compress_type=zipfile.ZIP_DEFLATED)
                writer.writerow(dict(
                    path=archive_audio_path,
                    duration=round(fragment['end'] - fragment['begin'], 3),
                    text=fragment['text']
                ))
                bar.update(1)
                os.unlink(tmp_audio)

            zip_file.writestr('data.csv', string_buffer.getvalue())
            bar.update(1)

        releases_data.append([
            f'[{release_name}](https://s3.eu-west-3.amazonaws.com/audiocorp/releases/{release_name}.zip)',
            len(fragments),
            len(per_language_speakers[source_language]),
            utils.format_timedelta(timedelta(seconds=round(sum(round(f['end'] - f['begin'], 3) for f in fragments)))),
            source_language,
        ])

    print('\n' + tabulate(
        releases_data,
        headers=['Name', '# speeches', '# speakers', 'Total Duration', 'Language'],
        tablefmt='pipe',
    ))


@cli.command()
@click.argument('source_name')
@click.argument('from_id', type=int)
@click.argument('to_id', type=int)
@click.option('-ar', '--audio-rate', default=16000)
def make_test(source_name, from_id, to_id, audio_rate):
    source = audiocorp.get_source(source_name)
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    path_to_mp3 = os.path.join(CURRENT_DIR, 'data/mp3', source['audio'])

    # generate wav if do not exists yet
    with open(path_to_mp3, 'rb') as f:
        file_hash = utils.hash_file(f)
    path_to_wav = os.path.join(utils.CACHE_DIR, f'{file_hash}.wav')
    if not os.path.exists(path_to_wav):
        ffmpeg.convert(
            from_=path_to_mp3,
            to=os.path.join(utils.CACHE_DIR, f'{file_hash}.wav'),
            rate=audio_rate,
            channels=1
        )

    # retrieve transcript
    with open(path_to_transcript) as f:
        transcript = [l.strip() for l in f.readlines()]
    transcript = [l for l in transcript if l]  # rm empty lines

    if os.path.isfile(path_to_alignment):
        with open(path_to_alignment) as f:
            existing_alignment = json.load(f)
    else:
        existing_alignment = []

    # detect silences
    silences = ffmpeg.list_silences(
        input_path=path_to_wav,
        min_duration=utils.DEFAULT_SILENCE_MIN_DURATION,
        noise_level=utils.DEFAULT_SILENCE_NOISE_LEVEL,
    )

    alignment = utils.build_alignment(
        transcript=transcript,
        path_to_audio=path_to_wav,
        existing_alignment=existing_alignment,
        silences=silences,
        generate_labels=True,
    )
    remaining = alignment[from_id - 1:to_id]

    with tempfile.NamedTemporaryFile(suffix='.wav') as file_:
        ffmpeg.cut(path_to_wav, file_.name, from_=remaining[0]['begin'], to=remaining[-1]['end'])
        with open(file_.name, 'rb') as f:
            file_hash = utils.hash_file(f)[:8]
        path_to_sub_audio = f'tests/assets/{file_hash}.wav'
        shutil.copy(file_.name, os.path.join(CURRENT_DIR, path_to_sub_audio))

    new_alignment = utils.build_alignment(
        transcript=[f['text'] for f in remaining],
        path_to_audio=path_to_sub_audio,
        existing_alignment=[],
        silences=ffmpeg.list_silences(
            input_path=path_to_sub_audio,
            min_duration=utils.DEFAULT_SILENCE_MIN_DURATION,
            noise_level=utils.DEFAULT_SILENCE_NOISE_LEVEL,
        ),
        generate_labels=True,
    )

    print(BUILD_ALIGNMENT_TEST_TEMPLATE.format(
        file_hash=file_hash,
        source_name=source_name,
        from_=timedelta(seconds=remaining[0]['begin']),
        to=timedelta(seconds=remaining[-1]['end']),
        transcript='\n        '.join(f"'{f['text']}'," for f in new_alignment),
        alignment='\n        '.join("dict(begin={begin}, end={end}, text='{text}'),".format(**f) for f in new_alignment),
        min_duration=utils.DEFAULT_SILENCE_MIN_DURATION,
        noise_level=utils.DEFAULT_SILENCE_NOISE_LEVEL,
    ))


BUILD_ALIGNMENT_TEST_TEMPLATE = """
    # {source_name} @@ {from_} {to} @@
    ('{file_hash}.wav', {noise_level}, {min_duration}, [
        {transcript}
    ], [], [
        {alignment}
    ]),
"""


@cli.command()
@click.argument('source_name')
def source_stats(source_name):
    source = audiocorp.get_source(source_name)
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    path_to_mp3 = os.path.join(CURRENT_DIR, 'data/mp3', source['audio'])

    # generate wav if do not exists yet
    with open(path_to_mp3, 'rb') as f:
        file_hash = utils.hash_file(f)
    path_to_wav = os.path.join(utils.CACHE_DIR, f'{file_hash}.wav')
    if not os.path.exists(path_to_wav):
        ffmpeg.convert(
            from_=path_to_mp3,
            to=os.path.join(utils.CACHE_DIR, f'{file_hash}.wav'),
            rate=16000,
            channels=1
        )

    # retrieve transcript
    with open(path_to_transcript) as f:
        transcript = [l.strip() for l in f.readlines()]
    transcript = [l for l in transcript if l]  # rm empty lines

    if os.path.isfile(path_to_alignment):
        with open(path_to_alignment) as f:
            existing_alignment = json.load(f)
    else:
        existing_alignment = []

    # detect silences
    silences = ffmpeg.list_silences(
        input_path=path_to_wav,
        min_duration=utils.DEFAULT_SILENCE_MIN_DURATION,
        noise_level=utils.DEFAULT_SILENCE_NOISE_LEVEL,
    )

    alignment = utils.build_alignment(
        transcript=transcript,
        path_to_audio=path_to_wav,
        existing_alignment=existing_alignment,
        silences=silences,
        generate_labels=True,
    )

    transitions_durations = []
    fragments_durations = []
    for prev_fragment, next_fragment in zip(alignment[:-1], alignment[1:]):
        silence_before, silence_between, silence_after = \
            utils.transition_silences(prev_fragment, next_fragment, silences)
        if silence_between:
            transitions_durations.append(silence_between[1] - silence_between[0])
        fragments_durations.append(next_fragment['end'] - next_fragment['begin'])
    t_mean = np.array(transitions_durations).mean()
    t_std = np.array(transitions_durations).std()
    f_mean = np.array(fragments_durations).mean()
    f_std = np.array(fragments_durations).std()
    print('\n' + tabulate(
        [
            [
                'transition dur (s)',
                len(transitions_durations),
                round(t_mean, 3),
                round(t_std, 3),
                f'{round(t_mean - t_std, 3)} - {round(t_mean + t_std, 3)}',
                f'{round(t_mean - 2 * t_std, 3)} - {round(t_mean + 2 * t_std, 3)}',
                f'{max(0, round(t_mean - 3 * t_std, 3))} - {round(t_mean + 3 * t_std, 3)}',
                min(transitions_durations),
                max(transitions_durations),
            ],
            [
                'fragment dur (s)',
                len(fragments_durations),
                round(f_mean, 3),
                round(f_std, 3),
                f'{round(f_mean - f_std, 3)} - {round(f_mean + f_std, 3)}',
                f'{round(f_mean - 2 * f_std, 3)} - {round(f_mean + 2 * f_std, 3)}',
                f'{max(0, round(f_mean - 3 * f_std, 3))} - {round(f_mean + 3 * f_std, 3)}',
                min(fragments_durations),
                max(fragments_durations),
            ],
        ],
        headers=['Metric', 'count', 'avg', 'std', '70%', '95%', '95%', 'min', 'max'],
        tablefmt='pipe',
    ))


if __name__ == '__main__':
    cli()
