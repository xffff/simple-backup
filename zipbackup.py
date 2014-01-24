import os, time, shutil, sys, zipfile, wx
from threading import *

EVT_RESULT_ID = wx.NewId()

def EVT_RESULT(win, func):
    win.Connect(-1, -1, EVT_RESULT_ID, func)

class ResultEvent(wx.PyEvent):
    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_RESULT_ID)
        self.data = data

class RedirectText(object):
    def __init__(self,aWxTextCtrl):
        self.out=aWxTextCtrl
    def write(self,string):
        wx.CallAfter(self.out.WriteText, string)

class ZipWorker(Thread):
    def __init__(self, notify, zipfilename, source_dir):
        Thread.__init__(self)
        self._notify      = notify
        self._want_abort  = 0
        self._source_dir  = source_dir
        self._zipfilename = zipfilename
        # start on creation of thread
        self.start()

    def run(self):
        self.makeZipfile()

    def abort(self):
        self._want_abort = 1
        
    def makeZipfile(self):
        if os.path.exists(self._zipfilename):
            print "Archive already exists in local folder, overwriting: ", self._zipfilename
        relroot = os.path.abspath(os.path.join(self._source_dir, os.pardir))
        with zipfile.ZipFile(self._zipfilename, "w", zipfile.ZIP_DEFLATED) as zip:
            for root, dirs, files in os.walk(self._source_dir):
                # add directory (needed for empty dirs)
                zip.write(root, os.path.relpath(root, relroot))
                for file in files:
                    filename = os.path.join(root, file)
                    if os.path.isfile(filename): # regular files only
                        arcname = os.path.join(os.path.relpath(root, relroot), file)
                        print "Archiving:", filename
                        # don't try and archive yourself
                        if self._zipfilename not in filename:
                            zip.write(filename, arcname)
                    if self._want_abort:
                        wx.PostEvent(self._notify, ResultEvent(None))
                        return
        wx.PostEvent(self._notify, ResultEvent(1))

class CopyWorker(Thread):
    def __init__(self, notify, frame, zipfilename, dst_dir):
        Thread.__init__(self)
        self._notify = notify
        self._want_abort = 0
        self._dst_dir = dst_dir
        self._zipfilename = zipfilename
        self._frame = frame
        self.start()
        
    def run(self):
        self.copyFile()

    # http://www.daniweb.com/software-development/python/threads/178615/large-shutil-copies-are-slow
    def copyFile(self):
        """ This function is a blind and fast copy operation.
              old and new are absolute file paths. """
        old = os.path.abspath(self._zipfilename)
        new = os.path.join(self._dst_dir, self._zipfilename)
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
                                    # parent  = self,
                                    parent = self._frame,
                                    style   = wx.PD_CAN_ABORT | \
                                    wx.PD_APP_MODAL | \
                                    wx.PD_ELAPSED_TIME | \
                                    wx.PD_REMAINING_TIME)
            keepGoing = True
            count = 0
            #
            while keepGoing:
                # Read blocks of size 2**24
                # Depending on system may require smaller
                #  or could go larger... 
                #  check your fs's max buffer size
                buf = fsrc.read(2**24)
                if not buf:
                    break
                fdst.write(buf)
                count += len(buf)
                (keepGoing, skip) = dlg.Update(count, "Copied " + str(count) + \
                                               " bytes of " + str(max) + " bytes.")
            dlg.Destroy()
        except Exception, e:
            print "Error in file move:", e
            wx.PostEvent(self._notify, ResultEvent(None))
            return
        finally:
            if fdst:
                fdst.close()
            if fsrc:
                fsrc.close()
        print "Done moving files"
        wx.PostEvent(self._notify, ResultEvent(2))
        
class MainFrame(wx.Frame):
    def __init__(self, parent, id):
        self._frame = wx.Frame.__init__(self, None, title="Backup", size=(800,300))
        panel = wx.Panel(self, wx.ID_ANY)

        # # abort abort abort
        # wx.Button(self, ID_STOP, 'Stop', pos=(0,0))
        # self.Bind(wx.EVT_BUTTON, self.stopWorker, id=ID_STOP)

        # log for messages
        log = wx.TextCtrl(panel,
                          wx.ID_ANY,
                          size=(800,300),
                          pos=(50,0),
                          style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(log, 1, wx.ALL | wx.EXPAND, 5)
        panel.SetSizer(sizer)

        # all text should go to the wxFrame        
        sys.stdout = RedirectText(log)

        # event handler for any worker thread results
        EVT_RESULT(self, self.onResult)
        self.worker = None
        
        # only bother doing anything once the thing is drawn
        wx.FutureCall(0, self.afterDrawn)
        
    def afterDrawn(self):                
        if os.path.exists(sys.argv[1]):
            self._src_dir = sys.argv[1]
            print "Source directory: ", self._src_dir
            if not os.path.exists(sys.argv[2]):
                print "Creating directory: {0}".format(sys.argv[2])
                os.mkdir(sys.argv[2])
            self._dst_dir = sys.argv[2]                
            print "Destination directory: ", self._dst_dir
        else:
            print "Source Directory doesn't exist"
                
        self._zipfilename = time.strftime("%Y%m%d") + '_backup.zip'
        print "Zip file: ", self._zipfilename

        # start zipping immediately
        self.startZip()
        
    def startZip(self):
        if not self.worker:
            self.worker = ZipWorker(self, self._zipfilename, self._src_dir)

    def startCopy(self):
        if not self.worker:
            self.worker = CopyWorker(self, self._frame, self._zipfilename, self._dst_dir)

    def stopWorker(self, event):
        if self.worker:
            self.worker.abort()

    def onResult(self, event):
        if event.data is None:
            print "Computation failed"
        elif event.data == 1:
            print "Archiving Finished!"
            self.worker = None
            self.startCopy()
        elif event.data == 2:
            self.worker = None
            print "Copying Finished!"
            self.cleanup()
        else:
            print "Weird ouput: ", event.data
            self.worker = None

    def cleanup(self):
        try:
            print "Deleting: ", self._zipfilename
            os.remove(self._zipfilename)
        except Exception, e:
            print "Error deleting local zipfile: ", e

    # http://www.daniweb.com/software-development/python/threads/178615/large-shutil-copies-are-slow
    def copyFile(self, dst):
        """ This function is a blind and fast copy operation.
              old and new are absolute file paths. """
        old = os.path.abspath(self.zipfilename)
        new = os.path.join(dst, self.zipfilename)
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
                # Read blocks of size 2**24
                # Depending on system may require smaller
                #  or could go larger... 
                #  check your fs's max buffer size
                buf = fsrc.read(2**24)
                if not buf:
                    break
                fdst.write(buf)
                count += len(buf)
                (keepGoing, skip) = dlg.Update(count, "Copied " + \
                                               str(count) + " bytes of " + str(max) + " bytes.")
            dlg.Destroy()
        except Exception, e:
            print "Error in file move:", e
        finally:
            if fdst:
                fdst.close()
            if fsrc:
                fsrc.close()
        print "Done moving files"

class MainApp(wx.App):
    def OnInit(self):
        self.frame = MainFrame(None, -1)
        self.frame.Show(True)
        self.SetTopWindow(self.frame)
        return True
        
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "Usage: {0} source-dir dest-dir".format(sys.argv[0])
    else:
        app = MainApp(0)
        app.MainLoop()    
