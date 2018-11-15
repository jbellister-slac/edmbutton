import subprocess
import os
import hashlib
import time
import logging
import socket
try:
    import wmctrl
except ImportError:
    wmctrl = None
from PyQt5.QtCore import QSize
from pydm.widgets import PyDMRelatedDisplayButton
from pydm.utilities import is_pydm_app

LOGGER = logging.getLogger(__name__)

def find_free_socket():
    """
    Reserve an unused socket, release it, and return the socket number.
    Careful, there isn't anything to ensure this socket *stays* usused
    after the method returns, so use it quick.
    """
    temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    temp_sock.bind(('', 0))
    addr = temp_sock.getsockname()
    temp_sock.close()
    return addr[1]

class PyDMEDMDisplayButton(PyDMRelatedDisplayButton):
    """
    A button specifically designed for launching EDM displays from PyDM.
    This class launches an instance of EDM in server mode when it instantiates.
    When the user interacts with the button, commands are sent to the EDM server
    to open new windows, or raise existing windows if they are available.

    This class only works on platforms that can run EDM. In some window
    managers, EDM cannot raise its own windows.  This class can use the
    'wmctrl' tool (http://tripie.sweb.cz/utils/wmctrl/), and the 'wmctrl'
    python module (http://github.com/mattgibbs/wmctrl) to try and work around
    that problem. If wmctrl is available, it will be used to raise windows.
    If it is not available, a new EDM window will always be opened on every
    click.
    """

    edm_command = ['edm', '-server', '-port', str(find_free_socket())]
    edm_server_proc = None
    windows = {}

    @classmethod
    def ensure_server_is_available(cls):
        """
        Check if the class-wide EDM server is running.  If not, start one.
        """
        if is_pydm_app():
            if cls.edm_server_proc is None or cls.edm_server_proc.poll() is not None:
                LOGGER.info("Starting EDM server process with command '{}'".format(" ".join(cls.edm_command)))
                cls.edm_server_proc = subprocess.Popen(cls.edm_command)

    def __init__(self, parent=None, filename=None):
        super(PyDMEDMDisplayButton, self).__init__(parent, filename)
        self.ensure_server_is_available()

    def window_name(self):
        """
        Generates a unique string identifier for this window, using the
        filename and any macros.
        """
        window_name = os.path.basename(self.displayFilename)
        if self._macro_string:
            window_name += hashlib.md5(self._macro_string).hexdigest()[0:5]
        return window_name

    @classmethod
    def invalidate_closed_windows(cls):
        """
        Clear out any windows that have been closed.
        """
        open_windows = {w.id: w for w in wmctrl.Window.list()}
        PyDMEDMDisplayButton.windows = {wname: w for (wname, w) in PyDMEDMDisplayButton.windows.items() if w.id in open_windows}

    def _open_new_window(self, wname, macros):
        command = PyDMEDMDisplayButton.edm_command
        if macros:
            command = command + ['-m', macros]
        full_command = command + ['-open', '{windowname}={filename}'.format(windowname=wname, filename=self.displayFilename)]
        subprocess.Popen(full_command)

    def open_display(self, target=PyDMRelatedDisplayButton.EXISTING_WINDOW):
        """
        Open the configured `filename` with the given `target`.
        If `target` is PyDMEDMDisplayButton.EXISTING_WINDOW, an existing window will
        be raised, if it exists.  If it does not exist, a new one
        will be spawned.

        If `target` is PyDMEDMDisplayButton.NEW_WINDOW, a new window will always be
        spawned.
        """
        self.ensure_server_is_available()
        wname = self.window_name()
        if not wmctrl:
            macros = self._macro_string
            if macros is None:
                macros = ""
            macros = "pydm_dup_workaround={noise},{macros}".format(noise=time.time(), macros=macros)
            self._open_new_window(wname, macros)
            return
        self.invalidate_closed_windows()
        # Store the window name for the duration of this method to avoid
        # computing hashes repeatedly.
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
            self._open_new_window(wname, macros)
            #Then poll the list of open windows until it shows up.
            new_window = None
            start_time = time.time()
            while new_window is None:
                after_list = wmctrl.Window.list()
                for win in after_list:
                    if win.id not in before_list:
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

