rem Create and enter a temporary directory.
cd %TMP%
IF EXIST MKDDP_BUNDLE_TMP rmdir /s /q MKDDP_BUNDLE_TMP
mkdir MKDDP_BUNDLE_TMP
cd MKDDP_BUNDLE_TMP

rem Create a virtual environment.
set PYTHONNOUSERSITE=1
set "PYTHONPATH="
python -m venv venv
call venv/Scripts/activate.bat


rem Retrieve a fresh checkout from the repository to avoid a potentially
rem polluted local checkout.
git clone https://github.com/RenolY2/mkdd-track-patcher.git
cd mkdd-track-patcher


rem Install cx_Freeze and its dependencies.
python -m pip install -r requirements-build-windows.txt

rem Install the application's dependencies.
python -m pip install -r requirements.txt

rem Build the bundle.
python setup.py build

rem Open directory in file explorer.
cd build
start .
