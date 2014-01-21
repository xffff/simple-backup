import os, time, shutil, sys, zipfile, wx

class RedirectText(object):
    def __init__(self,aWxTextCtrl):
        self.out=aWxTextCtrl
    def write(self,string):
        wx.CallAfter(self.out.WriteText, string)

class FileOps(wx.Frame):         
    def make_zipfile(self, output_filename, source_dir):
        relroot = os.path.abspath(os.path.join(source_dir, os.pardir))
        with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as zip:
            for root, dirs, files in os.walk(source_dir):
                # add directory (needed for empty dirs)
                zip.write(root, os.path.relpath(root, relroot))
                for file in files:
                    filename = os.path.join(root, file)
                    if os.path.isfile(filename): # regular files only
                        arcname = os.path.join(os.path.relpath(root, relroot), file)
                        print "Archiving:", filename
                        # don't try and archive yourself
                        if output_filename not in filename:
                            zip.write(filename, arcname)
                            
    def run(self, src, dst):
        filename = time.strftime("%Y%m%d") + '_backup.zip'
        print "Zip file: ", filename
        if not os.path.exists(os.path.join(dst, filename)):
            try:
                # dont bother making the archive if it exists in the folder already
                if not os.path.exists(filename):
                    self.make_zipfile(filename, src)
            except:
                print "Error archiving"
            try:
                print "Moving archive to: ", dst
                # shutil.move(filename, dst)
                self.copyFile(os.path.abspath(filename), dst+filename)
            except IOError as e:
                print "Error: ", e
            try:
                print "Removing temp file: ", filename
                os.remove(filename)
            except IOError as e:
                print "Error deleting temp file", e
        else:
            print "Backup already exists for today"

    # http://www.daniweb.com/software-development/python/threads/178615/large-shutil-copies-are-slow
    def copyFile(self, old, new):
        """ This function is a blind and fast copy operation.
              old and new are absolute file paths. """
        fsrc = None
        fdst = None
        keepGoing = False
        max = os.stat(old).st_size
        try:
            fsrc = open(old, 'rb')
            fdst = open(new, 'wb')
            dlg = wx.ProgressDialog("File Copy Progress",
                                    "Copied 0 bytes of " + str(max) + " bytes.",
                                    maximum = max,
                                    parent  = self,
                                    style   = wx.PD_CAN_ABORT | \
                                    wx.PD_APP_MODAL | \
                                    wx.PD_ELAPSED_TIME | \
                                    wx.PD_REMAINING_TIME)
            keepGoing = True
            count = 0
            #
            while keepGoing:
                # Read blocks of size 2**20 = 1048576
                # Depending on system may require smaller
                #  or could go larger... 
                #  check your fs's max buffer size
                buf = fsrc.read(2**20)
                if not buf:
                    break
                    fdst.write(buf)
                    count += len(buf)
                    (keepGoing, skip) = dlg.Update(count, "Copied " + \
                                                   str(count) + " bytes of " + str(max) + " bytes.")
                    dlg.Destroy()
        finally:
            if fdst:
                fdst.close()
            if fsrc:
                fsrc.close()                        
        return keepGoing
        
class MyFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="Backup")
        panel = wx.Panel(self, wx.ID_ANY)
        log = wx.TextCtrl(panel,
                          wx.ID_ANY,
                          size=(300,600),
                          style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(log, 1, wx.ALL | wx.EXPAND, 5)
        panel.SetSizer(sizer)
        redir = RedirectText(log)
        sys.stdout = redir
        fops       = FileOps(self)
        fops.run(sys.argv[1], sys.argv[2])
    
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "Usage: {0} source-dir dest-dir".format(sys.argv[0])
    else:
        if os.path.exists(sys.argv[1]):
            if not os.path.exists(sys.argv[2]):
                print "Creating directory: {0}".format(sys.argv[2])
                os.mkdir(sys.argv[2])
        else:
            print "Source Directory doesn't exist"

        app = wx.App()
        frame = MyFrame().Show()
        app.MainLoop()
