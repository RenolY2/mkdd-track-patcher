import os
import re
import shutil
import subprocess
import sys

from cx_Freeze import setup, Executable

# To avoid importing the module, simply parse the file to find the version variable in it.
with open('src/patcher.py', 'r', encoding='utf-8') as f:
    data = f.read()
for line in data.splitlines():
    if '__version__' in line:
        version = re.search(r"'(.+)'", line).group(1)
        break
else:
    raise RuntimeError('Unable to parse product version.')

# Compile WSYSTool.
subprocess.run((sys.executable, '-c', 'import wsystool; wsystool.compile_and_install_wsystool()'),
               cwd='src',
               check=True)

build_dirpath = 'build'
bundle_dirname = f'mkdd-patcher-{version}'
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

# Create the ZIP archive.
current_dirpath = os.getcwd()
os.chdir(build_dirpath)
try:
    print('Creating ZIP archive...')
    shutil.make_archive(bundle_dirname, 'zip', '.', bundle_dirname)
finally:
    os.chdir(current_dirpath)
