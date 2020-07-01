import zipfile

class ZipLikeFolder(object):
    def __init__(self, filepath):
        self.filepath = filepath 
    
    #def 

class ZipToIsoPatcher(object):
    def __init__(self, zip, iso):
        self.zip = zip 
        self.iso = iso 
        
    def src_file_exists(self, filepath):
        try:
            self.zip.getinfo(filepath)
        except KeyError:
            return False 
        return True 

    def copy_file(self, srcpath, destpath, missing_ok=True):
        try:
            file = self.zip.open(srcpath)
        except FileNotFoundError:
            if not missing_ok:
                raise 
        else:
            self.iso.changed_files[destpath] = file
    
    def copy_or_add_file(self, srcpath, destpath, missing_ok=True):
        try:
            file = self.zip.open(srcpath)
        except FileNotFoundError:
            if not missing_ok:
                raise 
        else:
            self.iso.change_or_add_file(destpath, file)
    
    def copy_file_into_arc(self, srcpath, arc, destpath, missing_ok=True):
        try:
            src_file = self.zip.open(srcpath)
        except FileNotFoundError:
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