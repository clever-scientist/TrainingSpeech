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
    source = audiocorpfr.get_source(source_name)
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
    source = audiocorpfr.get_source(source_name)
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

    def _check_alignment(index: int, alignment):
        click.clear()
        fragment = alignment[index]
        prev_fragment = alignment[index - 1] if i > 0 else None
        next_fragment = None if index == len(alignment) - 1 else alignment[index + 1]

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

        def ask_right_text():
            new_text = click.edit(text=fragment['text'], require_save=False)
            new_text = new_text or fragment['text']
            new_text = new_text.strip()
            new_text = '\n'.join(l.strip() for l in new_text.split('\n') if l.strip())
            return new_text

        def ask_what_next():
            current_silence = next((s for s in silences if s[0] <= fragment['end'] <= s[1]), None)
            if current_silence:
                prev_silence_start, prev_silence_end = silences[silences.index(current_silence) - 1]
                next_silence_start, next_silence_end = silences[silences.index(current_silence) + 1]
            else:
                prev_silence_start, prev_silence_end = next((s for s in reversed(silences) if s[1] <= fragment['end']))
                next_silence_start, next_silence_end = next((s for s in silences if s[0] >= fragment['end']))

            can_cut_on_prev_silence = prev_silence_start > fragment['begin']

            try:
                next_: str = inquirer.prompt([
                    inquirer.List(
                        'next',
                        message="\nWhat should I do ?",
                        choices=(
                                ['continue', 'repeat'] +
                                (['go_back'] if prev_fragment else []) +
                                (['wrong_end__cut_on_previous_silence'] if can_cut_on_prev_silence else []) +
                                (['wrong_end__cut_on_next_silence'] if next_fragment else []) +
                                (['merge_with_previous'] if prev_fragment else []) +
                                (['merge_with_next'] if next_fragment else []) +
                                ['edit_text'] +
                                (['enable'] if fragment.get('disabled') else ['disable']) +
                                ['quit']),
                    ),
                ])['next']
            except TypeError:
                raise exceptions.QuitException
            except Exception:
                next_ = 'merge_with_next'

            global audio_player
            try:
                audio_player.kill()
            except:
                pass

            if next_ == 'repeat':
                todo.add(pool.submit(play_audio_slow))
                todo.add(pool.submit(ask_what_next))
            elif next_ == 'go_back':
                prev_fragment.pop('disabled', None)
                prev_fragment.pop('approved', None)
                raise exceptions.GoBackException
            elif next_ == 'edit_text':
                new_text = ask_right_text()
                fragment['text'] = new_text
                if len(new_text.split('\n')) > 1:
                    raise exceptions.SplitException
                else:
                    print(colored(
                        f'playing #{i + 1:03d}: @@ {timedelta(seconds=fragment["begin"])} {timedelta(seconds=fragment["end"])} @@',
                        'yellow',
                        attrs=['bold']
                    ))
                    if prev_fragment:
                        print('   ' + colored(prev_fragment['text'], 'grey'))
                    print('-> ' + colored(fragment['text'], 'green', attrs=['bold']))
                    if next_fragment:
                        print('   ' + colored(next_fragment['text'], 'grey'))
                    todo.add(pool.submit(play_audio))
                    todo.add(pool.submit(ask_what_next))
            elif next_ == 'wrong_end__cut_on_previous_silence':
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
            elif next_ == 'merge_with_previous':
                raise exceptions.MergeException(left=prev_fragment, right=fragment)
            elif next_ == 'merge_with_next':
                raise exceptions.MergeException(left=fragment, right=next_fragment)
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

        if not restart and (fragment.get('approved') or fragment.get('disabled')):
            click.echo(f'skip fragment#{i} {fragment["text"]}')
            i += 1
            continue

        fragment_hash = utils.get_fragment_hash(fragment)
        path_to_audio = os.path.join(path_to_recordings, f'{fragment_hash}.wav')

        try:
            _check_alignment(index=i, alignment=alignment)
        except exceptions.GoBackException:
            i -= 1
            continue
        except exceptions.QuitException:
            audio_player.kill()
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

        except exceptions.SplitException:
            new_alignment = utils.get_alignment(
                path_to_audio,
                transcript=fragment['text'].split('\n'),
            )
            for nf in new_alignment:
                nf["begin"] += fragment["begin"]
                nf["end"] += fragment["begin"]
            alignment = (
                alignment[:i] +
                new_alignment +
                alignment[i+1:]
            )
            cut_fragments_audio(
                alignment[i:],
                input_file=path_to_wav,
                output_dir=path_to_recordings
            )
            i -= len(new_alignment) + 1

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
            source = audiocorpfr.get_source(source_name)
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
            info['approved_count'],
            info['approved_duration'],
        ])
        total_dur += info['approved_duration']
        total_count += info['approved_count']

    print(tabulate(
        sources_data,
        headers=['Source', 'Status', 'Progress', '# speeches', 'Speeches Duration'],
        tablefmt='pipe',
    ))
    print(f'\nTotal: {total_dur} with {total_count} speeches')


if __name__ == '__main__':
    cli()
