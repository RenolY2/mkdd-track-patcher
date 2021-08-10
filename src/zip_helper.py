import os 
import zipfile
import logging
from io import BytesIO
from pathlib import Path

log = logging.getLogger(__name__)


class ZipLikeFolder(object):
    def __init__(self, filepath):
        self.filepath = filepath 
    
    def path(self, subpath):
        return Path(os.path.join(self.filepath, subpath))

    # zipfile's open does not seem to expect to be closed after use.
    # To mimic that, we write files into BytesIO and return that.
    def open(self, path):
        handle = BytesIO()

        try:
            with open(os.path.join(self.filepath, path), "rb") as f:
                handle.write(f.read())
        except:
            raise KeyError("{0} not found.".format(path))
        handle.seek(0)
        return handle

    def namelist(self):
        result = []
        base = os.path.basename(self.filepath)

        for root, dirs, files in os.walk(self.filepath):
            for dirpath in dirs:
                result.append(os.path.join(root, dirpath))
            for filepath in files:
                result.append(os.path.join(root, filepath))

        for i in range(len(result)):
            result[i] = os.path.join(base, os.path.relpath(result[i], self.filepath))
        result.insert(0, base)
        return result

    def is_dir(self, path):
        path = os.path.join(self.filepath, path)
        return os.path.isdir(path)

    # We only use getinfo for checking if the file exists,
    # so we do not need to return a valid ZipInfo object
    def getinfo(self, path):
        path = os.path.join(self.filepath, path)
        print(path)
        if not os.path.exists(path):
            raise KeyError("{0} doesn't exist.".format(path))
        else:
            return None


def find_arc(path: Path):
    for i, part in enumerate(path.parts):
        if part.find(".arc") != -1:
            return i 
    return -1 
    

class ZipToIsoPatcher(object):
    def __init__(self, zip, iso):
        self.zip = zip 
        self.iso = iso
        self.root = None

        self._is_folder = False

    def is_code_patch(self):
        return (not self.src_file_exists("modinfo.ini")
                and not self.src_file_exists("trackinfo.ini")
                and self.src_file_exists("codeinfo.ini"))

    def set_zip(self, path):
        if Path(path).is_dir():
            self.zip = ZipLikeFolder(path)
            spath = Path(path)
            self._is_folder = True
        else:
            self.zip = zipfile.ZipFile(path)
            # Find the root folder:
            spath = zipfile.Path(self.zip, "/")
            self._is_folder = False

        root = None 
        for entry in spath.iterdir():
            if root is None:
                if entry.is_dir():
                    root = entry.name
                else:
                    # the first entry we found is not a dir 
                    root = None 
                    break 
            else:
                # We found more than one entry in the root dir 
                root = None 
                break 
                
        if root is None or self._is_folder:
            self.root = ""
        else:
            self.root = root+"/"

        if not self._is_folder:
            # Workaround for a weird bug where zipfile object considers itself closed
            # after the above zipfile.Path call
            self.zip = zipfile.ZipFile(path)
    
    def zip_open(self, filepath):
        log.debug(f"open: {filepath}")
        fp = self.zip.open(self.root+filepath)
        return fp
    
    def get_file_changes(self, startpath):
        startpath = Path(self.root+startpath)
        arcs = {}
        files = []

        for filepath in self.zip.namelist():
            filepath_path = Path(filepath)
            if self._is_folder:
                if self.zip.is_dir(filepath):
                    continue
            else:
                zippath = zipfile.Path(self.zip, filepath)
                if zippath.is_dir():
                    continue

            if filepath_path.is_relative_to(startpath):
                path = filepath_path.relative_to(startpath)
                if len(path.parts) == 0:
                    continue 
                
                arc = find_arc(path)
                
                if arc != -1:
                    if filepath.count(".arc") > 1:
                        continue 
                        
                    if arc+1 < len(path.parts):
                        arcpath = "/".join(path.parts[:arc+1])
                        filepath = "/".join(path.parts[arc+1:])
                        
                        if arcpath not in arcs:
                            arcs[arcpath] = [filepath]
                        else:
                            arcs[arcpath].append(filepath)
                else:
                    files.append("/".join(path.parts))
        
        return arcs, files 

    def src_file_exists(self, filepath):
        try:
            self.zip.getinfo(self.root+filepath)
        except KeyError:
            return False 
        return True 

    def copy_file(self, srcpath, destpath, missing_ok=True):
        try:
            file = self.zip.open(self.root+srcpath)
        except KeyError:
            if not missing_ok:
                raise 
        else:
            self.iso.changed_files[destpath] = file
    
    def copy_or_add_file(self, srcpath, destpath, missing_ok=True):
        try:
            file = self.zip.open(self.root+srcpath)
        except KeyError:
            if not missing_ok:
                raise 
        else:
            self.iso.change_or_add_file(destpath, file)
    
    def copy_file_into_arc(self, srcpath, arc, destpath, missing_ok=True):
        try:
            src_file = self.zip.open(self.root+srcpath)
        except KeyError:
            if not missing_ok:
                raise
        else:
            file = arc[destpath]
            file.seek(0)
            file.write(src_file.read())
            file.truncate()
    
    def change_file(self, destpath, filedata):
        self.iso.changed_files[destpath] = filedata 
    
    def get_iso_file(self, path):
        if path in self.iso.changed_files:
            return self.iso.changed_files[path]
        else:
            return self.iso.read_file_data(path)


if __name__ == "__main__":
    testzip = zipfile.ZipFile("C:\\Users\\User\\Documents\\GitHub\\mkdd-track-patcher\\test/ExtraCollision.zip")
    testfolder = ZipLikeFolder("C:\\Users\\User\\Documents\\GitHub\\mkdd-track-patcher\\test\\ExtraCollision")

    print(testzip.namelist())
    print(testfolder.namelist())

    for path in testfolder.namelist():
        print(path, testfolder.is_dir(path))

    zipper = ZipToIsoPatcher(None, None)
    zipper.set_zip("C:\\Users\\User\\Documents\\GitHub\\mkdd-track-patcher\\test\\ExtraCollision")
    print(zipper.is_code_patch())
    print(zipper.src_file_exists("codeinfo.ini"))