import os
import platform
import re
import shutil
import subprocess
import sys
import time

from cx_Freeze import setup, Executable


def get_git_revision_hash() -> str:
    return subprocess.check_output(('git', 'rev-parse', 'HEAD')).decode('ascii').strip()


# To avoid importing the module, simply parse the file to find the version variable in it.
with open('src/patcher.py', 'r', encoding='utf-8') as f:
    main_file_data = f.read()
for line in main_file_data.splitlines():
    if '__version__' in line:
        version = re.search(r"'(.+)'", line).group(1)
        break
else:
    raise RuntimeError('Unable to parse product version.')

is_ci = bool(os.getenv('CI'))
triggered_by_tag = os.getenv('GITHUB_REF_TYPE') == 'tag'
commit_sha = os.getenv('GITHUB_SHA') or get_git_revision_hash()
build_time = time.strftime("%Y-%m-%d %H-%M-%S")

version_suffix = f'-{commit_sha[:8]}' if commit_sha and not triggered_by_tag else ''

# Replace constants in source file.
main_file_data = main_file_data.replace('OFFICIAL = False', f"OFFICIAL = {triggered_by_tag}")
main_file_data = main_file_data.replace("COMMIT_SHA = ''", f"COMMIT_SHA = '{commit_sha}'")
main_file_data = main_file_data.replace("BUILD_TIME = None", f"BUILD_TIME = '{build_time}'")
with open('src/patcher.py', 'w', encoding='utf-8') as f:
    f.write(main_file_data)

# Compile WSYSTool.
subprocess.run((sys.executable, '-c', 'import wsystool; wsystool.compile_and_install_wsystool()'),
               cwd='src',
               check=True)

system = platform.system().lower()

ARCH_USER_FRIENDLY_ALIASES = {'AMD64': 'x64', 'x86_64': 'x64'}
machine = platform.machine()
arch = ARCH_USER_FRIENDLY_ALIASES.get(machine) or machine.lower()

build_dirpath = 'build'
bundle_dirname = f'mkdd-patcher-{version}{version_suffix}-{system}-{arch}'
bundle_dirpath = os.path.join(build_dirpath, bundle_dirname)

include_files = ["src/resources", "src/tools"]
build_exe_options = {
    "packages": [],
    "includes": [],
    "excludes": [],
    "optimize": 0,
    "build_exe": bundle_dirpath,
    "include_files": include_files
}

setup(name="MKDD Patcher",
      version=version,
      description="Patcher for MKDD.",
      options={"build_exe": build_exe_options},
      executables=[Executable("mkdd_patcher.py", base=None, icon="src/resources/logo.ico")])

os.remove(os.path.join(bundle_dirpath, 'frozen_application_license.txt'))

if not is_ci:
    # Create the ZIP archive.
    current_dirpath = os.getcwd()
    os.chdir(build_dirpath)
    try:
        print('Creating ZIP archive...')
        shutil.make_archive(bundle_dirname, 'zip', '.', bundle_dirname)
    finally:
        os.chdir(current_dirpath)
