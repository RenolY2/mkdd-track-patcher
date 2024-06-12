"""
A wrapper for the WSYSTool.
"""
import contextlib
import os
import pathlib
import shlex
import subprocess
import tempfile
import logging

log = logging.getLogger(__name__)


@contextlib.contextmanager
def _current_directory(dirpath: str):
    cwd = os.getcwd()
    try:
        os.chdir(dirpath)
        yield
    finally:
        os.chdir(cwd)


def _get_wsystool_root() -> str:
    tools_dirpath = str(pathlib.Path(__file__).parent.absolute() / 'tools')
    return os.path.join(tools_dirpath, 'wsystool')


def _get_wsystool_path() -> str:
    ext = '.exe' if os.name == 'nt' else ''
    return os.path.join(_get_wsystool_root(), f'wsystool{ext}')


def check_wsystool() -> bool:
    return os.path.isfile(_get_wsystool_path())


def _run(args: list[str]) -> str:
    try:
        return subprocess.run(args,
                              check=True,
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              text=True).stdout
    except subprocess.CalledProcessError as e:
        command = " ".join([shlex.quote(arg) for arg in e.cmd])
        raise RuntimeError(f'Command:\n\n{command}\n\n'
                           f'Error code: {e.returncode}\n\n'
                           f'Output:\n\n{e.output}') from e
    except Exception as e:
        command = " ".join([shlex.quote(arg) for arg in args])
        raise RuntimeError(f'Command:\n\n{command}\n\n'
                           f'Exception type: {type(e).__name__}\n\n'
                           f'Message:\n\n{str(e)}') from e


def compile_and_install_wsystool():
    WSYSTOOL_GIT_URL = 'https://github.com/XAYRGA/wsystool.git'
    WSYSTOOL_GIT_SHA = '41a429931734ddf57bb5bbdb7a537148c20e7b3a'

    with tempfile.TemporaryDirectory(prefix='mkddpatcher_') as tmp_dir:
        with _current_directory(tmp_dir):
            log.info('Checking out WSYSTool...')
            _run(('git', 'clone', WSYSTOOL_GIT_URL))

            with _current_directory('wsystool'):
                _run(('git', 'checkout', WSYSTOOL_GIT_SHA))

                log.info('Compiling WSYSTool...')
                _run((
                    'dotnet',
                    'build',
                    'wsystool.sln',
                    '--configuration',
                    'Release',
                    '--output',
                    _get_wsystool_root(),
                ))

    assert check_wsystool(), 'Tool should be available after successful installation'

    log.info(f'WSYSTool installed successfully in "{_get_wsystool_root()}"')


def unpack_wsys(src_filepath: str, dst_dirpath, awpath: str, export_waves: bool):
    args = [
        _get_wsystool_path(),
        'unpack',
        src_filepath,
        dst_dirpath,
        '-awpath',
        awpath,
    ]
    if export_waves:
        args.extend([
            '-waveout',
            os.path.join(dst_dirpath, 'wav'),
        ])
    _run(args)


def pack_wsys(src_dirpath: str, dst_filepath: str, awpath: str):
    _run((
        _get_wsystool_path(),
        'pack',
        src_dirpath,
        dst_filepath,
        '-awpath',
        awpath,
    ))
