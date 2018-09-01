import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from typing import List

import click
from tabulate import tabulate
from termcolor import colored

import audiocorpfr
from audiocorpfr import utils, ffmpeg, sox, exceptions

CURRENT_DIR = os.path.dirname(__file__)
DEFAULT_SILENCE_MIN_DURATION = 0.07
DEFAULT_SILENCE_NOISE_LEVEL = -45


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


def build_alignment(source_name):
    source = utils.get_source(source_name)
    mp3 = os.path.join(CURRENT_DIR, 'data/mp3/', source['audio'])

    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')

    with open(path_to_transcript) as f:
        transcript = [l.strip() for l in f.readlines()]
    transcript = [l for l in transcript if l]

    silences = ffmpeg.list_silences(
        input_path=mp3,
        min_duration=DEFAULT_SILENCE_MIN_DURATION,
        noise_level=DEFAULT_SILENCE_NOISE_LEVEL,
    )

    original_alignment = utils.get_alignment(path_to_audio_file=mp3, transcript=transcript)

    alignment = utils.fix_alignment(original_alignment, silences)

    if any(f['end'] - f['begin'] == 0 for f in alignment):
        lines = ', '.join([str(i + 1) for i, f in enumerate(alignment) if f['end'] - f['begin'] == 0])
        raise Exception(f'lines {lines} led to empty alignment')

    if os.path.exists(path_to_alignment):
        with open(path_to_alignment) as curr_f:
            current_alignment = json.load(curr_f)
    else:
        current_alignment = []

    merged_alignment = utils.merge_alignments(current_alignment, alignment)
    with open(path_to_alignment, 'w') as dest:
        json.dump(
            obj=merged_alignment,
            fp=dest,
            sort_keys=True,
            indent=2,
        )

    with open(path_to_transcript, 'w') as f:
        f.writelines('\n'.join(f['text'] for f in alignment) + '\n')

    # Generate Audacity labels for DEBUG purpose
    path_to_silences_labels = f'/tmp/{source_name}_silences_labels.txt'
    with open(path_to_silences_labels, 'w') as f:
        f.writelines('\n'.join([f'{s}\t{e}\tsilence{i+1:03d}' for i, (s, e) in enumerate(silences)]) + '\n')

    path_to_alignment_labels = f'/tmp/{source_name}_alignments_labels.txt'
    with open(path_to_alignment_labels, 'w') as labels_f:
        labels_f.writelines(
            '\n'.join([f'{f["begin"]}\t{f["end"]}\t#{i+1:03d}:{f["text"]}' for i, f in enumerate(merged_alignment)]) + '\n')

    path_to_original_alignment_labels = f'/tmp/{source_name}_original_alignments_labels.txt'
    with open(path_to_original_alignment_labels, 'w') as labels_f:
        labels_f.writelines('\n'.join([f'{f["begin"]}\t{f["end"]}\t#{i+1:03d}:{f["text"]}' for i, f in enumerate(original_alignment)]) + '\n')


audio_player = None


def cut_fragment_audio(fragment: dict, input_file: str, output_dir: str):
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)

    fragment_hash = utils.get_fragment_hash(fragment)
    path_to_fragment_audio = os.path.join(output_dir, f'{fragment_hash}.wav')
    if not os.path.isfile(path_to_fragment_audio):
        ffmpeg.cut(input_file, path_to_fragment_audio, from_=fragment['begin'], to=fragment['end'])


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
def check_alignment(source_name, restart):
    import inquirer
    source = utils.get_source(source_name)
    path_to_alignment = os.path.join(CURRENT_DIR, f'data/alignments/{source_name}.json')
    path_to_transcript = os.path.join(CURRENT_DIR, f'data/transcripts/{source_name}.txt')
    path_to_mp3 = os.path.join(CURRENT_DIR, 'data/mp3', source['audio'])

    build_alignment(source_name)

    with open(path_to_alignment, 'r') as f:
        fragments = json.load(f)

    # generate wav
    with open(path_to_mp3, 'rb') as f:
        file_hash = utils.hash_file(f)
    path_to_wav = f'/tmp/{file_hash}.wav'
    # create wav from mp3 if do not exists yet
    if not os.path.exists(path_to_wav):
        ffmpeg.convert(from_=path_to_mp3, to=f'/tmp/{file_hash}.wav', rate=16000, channels=1)

    # delete existing fragments if any
    path_to_recordings = os.path.join(CURRENT_DIR,  f'/tmp/{source_name}/')

    silences = ffmpeg.list_silences(
        input_path=path_to_mp3,
        min_duration=DEFAULT_SILENCE_MIN_DURATION,
        noise_level=DEFAULT_SILENCE_NOISE_LEVEL,
    )

    def _check_alignment(index: int, fragments):
        fragment = fragments[index]
        prev_fragment = fragments[index - 1] if i > 0 else None
        next_fragment = None if index == len(fragments) - 1 else fragments[index + 1]

        print(colored(
            f'\nplaying #{i + 1:03d}: @@ {timedelta(seconds=fragment["begin"])}  {timedelta(seconds=fragment["end"])} @@',
            'yellow',
            attrs=['bold']
        ))
        if prev_fragment:
            print('   ' + colored(prev_fragment['text'], 'grey'))
        print('-> ' + colored(fragment['text'], 'green', attrs=['bold']))
        if next_fragment:
            print('   ' + colored(next_fragment['text'], 'grey'))

        todo = set()
        pool = ThreadPoolExecutor()

        def play_audio():
            fragment_hash = utils.get_fragment_hash(fragment)
            path_to_audio = os.path.join(path_to_recordings, f'{fragment_hash}.wav')
            if not os.path.isfile(path_to_audio):
                cut_fragment_audio(fragment, path_to_wav, path_to_recordings)
            global audio_player

            with sox.play(path_to_audio, speed=1.3) as player:
                audio_player = player

        todo.add(pool.submit(play_audio))

        def ask_right_text():
            new_text = click.edit(text=fragment['text'], require_save=False)
            new_text = new_text or fragment['text']
            new_text = new_text.strip()
            new_text = '\n'.join(l.strip() for l in new_text.split('\n') if l.strip())
            return new_text

        def ask_what_next():
            try:
                next_: str = inquirer.prompt([
                    inquirer.List(
                        'next',
                        message="\nWhat should I do ?",
                        choices=(
                                ['continue', 'repeat'] +
                                (['go_back'] if prev_fragment else []) +
                                (['wrong_end__cut_on_previous_silence'] if prev_fragment else []) +
                                (['wrong_end__cut_on_next_silence'] if next_fragment else []) +
                                (['merge_previous'] if index > 0 else []) +
                                ['wrong_text'] +
                                (['enable'] if fragment.get('disabled') else ['disable']) +
                                ['quit']),
                    ),
                ])['next']
            except TypeError:
                raise exceptions.QuitException
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
                prev_fragment.pop('disabled', None)
                prev_fragment.pop('approved', None)
                raise exceptions.GoBackException
            elif next_ == 'wrong_text':
                new_text = ask_right_text()
                fragment['text'] = new_text
                if len(new_text.split('\n')) > 1:
                    raise exceptions.SplitException
            elif next_ == 'wrong_end__cut_on_previous_silence':
                current_silence = next((s for s in silences if s[0] <= fragment['end'] <= s[1]), None)
                if current_silence:
                    prev_silence_start, prev_silence_end = silences[silences.index(current_silence) - 1]
                else:
                    prev_silence_start, prev_silence_end = next((s for s in reversed(silences) if s[1] <= fragment['end']))
                fragment['end'] = round(min(prev_silence_start + 0.5, prev_silence_end), 3)
                fragment['end_forced'] = True
                cut_fragment_audio(fragment, input_file=path_to_wav, output_dir=path_to_recordings)
                if next_fragment:
                    next_fragment['begin'] = round(max(prev_silence_end - 0.5, prev_silence_start), 3)
                    next_fragment['begin_forced'] = True
                    cut_fragment_audio(next_fragment, input_file=path_to_wav, output_dir=path_to_recordings)
                todo.add(pool.submit(play_audio))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'wrong_end__cut_on_next_silence':
                current_silence = next((s for s in silences if s[0] <= fragment['end'] <= s[1]), None)
                if current_silence:
                    next_silence_start, next_silence_end = silences[silences.index(current_silence) + 1]
                else:
                    next_silence_start, next_silence_end = next((s for s in silences if s[0] >= fragment['end']))
                fragment['end'] = round(min(next_silence_start + 0.5, next_silence_end), 3)
                fragment['end_forced'] = True
                cut_fragment_audio(fragment, input_file=path_to_wav, output_dir=path_to_recordings)
                if next_fragment:
                    next_fragment['begin'] = round(max(next_silence_end - 0.5, next_silence_start), 3)
                    next_fragment['begin_forced'] = True
                    cut_fragment_audio(next_fragment, input_file=path_to_wav, output_dir=path_to_recordings)
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
                raise exceptions.QuitException
            elif next_ == 'merge_previous':
                raise exceptions.MergeException
            else:
                raise NotImplementedError

        todo.add(pool.submit(ask_what_next))

        while todo:
            for future in as_completed(t for t in todo):
                todo.remove(future)
                future.result()

        pool.shutdown(wait=True)

    cut_fragments_audio(fragments, input_file=path_to_wav, output_dir=path_to_recordings)

    # iterate over successive fragments
    i = 0
    done = False
    while i < len(fragments) and not done:
        fragment = fragments[i]

        if not restart and (fragment.get('approved') or fragment.get('disabled')):
            click.echo(f'skip fragment#{i} {fragment["text"]}')
            i += 1
            continue

        fragment_hash = utils.get_fragment_hash(fragment)
        path_to_audio = os.path.join(path_to_recordings, f'{fragment_hash}.wav')

        try:
            _check_alignment(index=i, fragments=fragments)
        except exceptions.GoBackException:
            i -= 1
            continue
        except exceptions.QuitException:
            audio_player.kill()
            break
        except exceptions.MergeException:
            prev_fragment = fragments[i - 1]
            fragment['begin'] = prev_fragment['begin']
            fragment['text'] = f'{prev_fragment["text"]} {fragment["text"]}'
            fragment['duration'] = fragment['end'] - fragment['begin']
            cut_fragment_audio(fragment, input_file=path_to_wav, output_dir=path_to_recordings)
            fragments = fragments[:i-1] + fragments[i:]
            i -= 2
        except exceptions.SplitException:
            new_fragments = utils.get_alignment(
                path_to_audio,
                transcript=fragment['text'].split('\n'),
            )
            for nf in new_fragments:
                nf["begin"] += fragment["begin"]
                nf["end"] += fragment["begin"]
            fragments = (
                fragments[:i] +
                new_fragments +
                fragments[i+1:]
            )
            cut_fragments_audio(
                fragments[i:],
                input_file=path_to_wav,
                output_dir=path_to_recordings
            )

        # save progress
        with open(path_to_alignment, 'w') as dest:
            json.dump(
                obj=fragments,
                fp=dest,
                sort_keys=True,
                indent=2,
            )
        with open(path_to_transcript, 'w') as f:
            f.writelines('\n'.join(f['text'] for f in fragments) + '\n')

        i += 1


MAPPINGS = [
    (os.path.join(CURRENT_DIR, 's3://audiocorpfr/epubs/'), os.path.join(CURRENT_DIR, 'data/epubs/'), 'ebook'),  # epubs
    (os.path.join(CURRENT_DIR, 's3://audiocorpfr/mp3/'), os.path.join(CURRENT_DIR, 'data/mp3/'), 'audio'),  # mp3
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
            options += f'--exclude \'*\' --include \'{source[key]}\' '

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


if __name__ == '__main__':
    cli()
