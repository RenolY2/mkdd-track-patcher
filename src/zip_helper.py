import os 
import zipfile
from pathlib import Path

class ZipLikeFolder(object):
    def __init__(self, filepath):
        self.filepath = filepath 
    
    #def 

def find_arc(path):
    for i, part in enumerate(path.parts):
        if part.find(".arc") != -1:
            return i 
    return -1 
    

class ZipToIsoPatcher(object):
    def __init__(self, zip, iso):
        self.zip = zip 
        self.iso = iso 
    
    def set_zip(self, path):
        self.zip = zipfile.ZipFile(path)
        # Find the root folder:
        spath = zipfile.Path(self.zip, "/")
        
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
                
        if root is None:
            self.root = ""
        else:
            self.root = root+"/"
            
        # Workaround for a weird bug where zipfile object considers itself closed
        # after the above zipfile.Path call
        self.zip = zipfile.ZipFile(path)
    
    def zip_open(self, filepath):
        #print("open:", filepath)
        fp = self.zip.open(self.root+filepath)
        return fp
    
    def get_file_changes(self, startpath):
        startpath = self.root+startpath
        arcs = {}
        files = []
        
        for filepath in self.zip.namelist():
            zippath = zipfile.Path(self.zip, filepath)
            if zippath.is_dir():
                continue 
                
            if filepath.startswith(startpath):
                path = Path(filepath[len(startpath):])
                if len(path.parts) == 0:
                    continue 
                
                arc = find_arc(path)
                
                if arc != -1:
                    if filepath.count(".arc") > 1:
                        continue 
                        
                    if arc+1 < len(path.parts):
                        arcpath = "/".join(path.parts[:arc+1])
                        filepath =  "/".join(path.parts[arc+1:])
                        
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