import subprocess
import os
import hashlib
import time
import wmctrl
from pydm.widgets import PyDMRelatedDisplayButton


class PyDMEDMDisplayButton(PyDMRelatedDisplayButton):
    """
    A button specifically designed for launching EDM displays from PyDM.
    This class launches an instance of EDM in server mode when it instantiates.
    When the user interacts with the button, commands are sent to the EDM server
    to open new windows, or raise existing windows if they are available.

    This class only works on platforms that can run EDM.  In some window managers,
    EDM cannot raise its own windows.  This class uses the 'wmctrl' tool
    (http://tripie.sweb.cz/utils/wmctrl/) to try and work around that problem.
    If wmctrl is installed and on the PATH, it will be used to raise windows.
    If it is not detected, all we can do is ask EDM to raise the window for you
    and hope it works.
    """

    edm_command = ['edm', '-server']
    edm_server_proc = subprocess.Popen(edm_command)
    windows = {}

    def window_name(self):
        """
        Generates a unique string identifier for this window, using the
        filename and any macros.
        """
        window_name = os.path.basename(self.displayFilename)
        if self._macro_string:
            window_name += hashlib.md5(self._macro_string).hexdigest()
        return window_name

    def open_display(self, target=PyDMEDMDisplayButton.EXISTING_WINDOW):
        """
        Open the configured `filename` with the given `target`.
        If `target` is PyDMEDMDisplayButton.EXISTING_WINDOW, an existing window will
        be raised, if it exists.  If it does not exist, a new one
        will be spawned.

        If `target` is PyDMEDMDisplayButton.NEW_WINDOW, a new window will always be
        spawned.
        """
        #Ensure the EDM server is up and running, if not, restart it.
        if PyDMEDMDisplayButton.edm_server_proc.poll() is not None:
            PyDMEDMDisplayButton.edm_server_proc = subprocess.Popen(PyDMEDMDisplayButton.edm_command)
        # Store the window name for the duration of this method to avoid
        # computing hashes repeatedly.
        wname = self.window_name()
        if not self.displayFilename:
            return
        if target == self.NEW_WINDOW:
            # First check if this file is something we've already got open.
            # If it is, our EDM server will refuse to open a new copy.
            # Luckily, there is a workaround. Turns out you can do an UNLIMITED
            # number of the same display as long as you pass different macro
            # variables. So just put some unique nonsense (the current
            # timestamp) into a macro variable in this case.
            macros = self._macro_string
            if wname in PyDMEDMDisplayButton.windows:
                if macros is None:
                    macros = ""
                macros = "pydm_dup_workaround={noise},{macros}".format(noise=time.time(), macros=macros)
            
            # First we need to get a list of currently open windows
            before_list = {w.id: w for w in wmctrl.Window.list()}
            #Then open up the new one.
            edm_command = PyDMEDMDisplayButton.edm_command
            if macros:
                edm_command.extend(['-m', macros])
            subprocess.Popen(edm_command.extend(['-open', '{windowname}={filename}'.format(windowname=wname, filename=self.displayFilename)]))
            #Then poll the list of open windows until it shows up.
            new_window = None
            start_time = time.time()
            while new_window is None:
                after_list = wmctrl.Window.list()
                for win in after_list:
                    if win.id in before_list:
                        new_window = win
                        break
                end_time = time.time()
                if end_time - start_time > 5.0:
                    raise Exception("Timeout expired while trying to launch EDM window.")
            assert new_window is not None
            PyDMEDMDisplayButton.windows[wname] = new_window
        else: #If we're not explicity launching a new window
            # First check if this is something we've got in our dictionary of windows.
            # If it isn't, we've got no choice but to open it up as a new one.
            if wname not in PyDMEDMDisplayButton.windows:
                self.open_display(target=self.NEW_WINDOW)
                return
            else:
                PyDMEDMDisplayButton.windows[wname].activate()
        #Finally, take a little time to evict closed windows from our dictionary
        PyDMEDMDisplayButton.invalidate_closed_windows()

    @classmethod
    def invalidate_closed_windows(cls):
        """
        Clear out any windows that have been closed.
        """
        open_windows = {w.id: w for w in wmctrl.Window.list()}
        cls.windows = {wname: w for (wname, w) in w.items() if w.id in open_windows}
