import subprocess
import os
import hashlib
import time
import logging
import socket
import threading
try:
    import wmctrl
except (ImportError, subprocess.CalledProcessError):
    wmctrl = None
from pydm.widgets import PyDMRelatedDisplayButton
from pydm.utilities import is_pydm_app

LOGGER = logging.getLogger(__name__)


def find_edm_server_socket():
    """
    Search 'ps' output for instances of EDM servers.  If there aren't any,
    open up a new socket.
    """
    pass

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
    retcode = subprocess.call(["which", "edm"])
    if retcode != 0:
        edm_server_proc = False
    try:
        import wmctrl
        wmctrl_available = True
    except (ImportError, subprocess.CalledProcessError):
        wmctrl_available = False
        LOGGER.debug("Disabling wmctrl support in edmbutton.")
    windows = {}

    @classmethod
    def initialize_edm_window(cls):
        # NOTE: This method gets called in a separate thread...
        try:
            import wmctrl
            cls.wmctrl_available = True
        except (ImportError, subprocess.CalledProcessError):
            cls.wmctrl_available = False
            return
        try:
            before_list = {w.id: w for w in wmctrl.Window.list()}
        except subprocess.CalledProcessError:
            # If wmctrl fails, it is probably because you're using some horrible X server
            # that doesn't support retrieving a list of all open windows, like FastX (boooo!).
            # If that is the case, wmctrl just gets disabled entirely.
            cls.wmctrl_available = False
            LOGGER.debug("Disabling wmctrl support in edmbutton.")
            return
        new_window = None
        start_time = time.time()
        while new_window is None:
            try:
                after_list = wmctrl.Window.list()
            except subprocess.CalledProcessError:
                return
            for win in after_list:
                if win.id not in before_list and win.wm_class.decode('utf-8') == 'edm.edm' and win.wm_name.decode('utf-8').startswith('edm'):
                    new_window = win
                    break
            end_time = time.time()
            if end_time - start_time > 5.0:
                break
        if new_window:
            new_window.set_always_on_bottom()
            return 


    @classmethod
    def ensure_server_is_available(cls):
        """
        Check if the class-wide EDM server is running.  If not, start one.
        """
        if cls.edm_server_proc is False:
            return
        if is_pydm_app():
            if cls.edm_server_proc is None or cls.edm_server_proc.poll() is not None:
                LOGGER.info("Starting EDM server process with command '{}'".format(" ".join(cls.edm_command)))
                try:
                    if not cls.wmctrl_available or not hasattr(wmctrl.Window, 'set_always_on_bottom'):
                        cls.edm_server_proc = subprocess.Popen(cls.edm_command)
                        LOGGER.debug("EDM server process launched.")
                    else:
                        # If wmctrl is availabe, and knows how to send a window to the bottom,
                        # we look for the stupid EDM postage stamp window, and if we find it,
                        # we send it to the bottom so that it doesn't overlap with PyDM.
                        cls.edm_server_proc = subprocess.Popen(cls.edm_command)
                        LOGGER.debug("EDM server process launched.")
                        t = threading.Thread(target=cls.initialize_edm_window)
                        t.start()
                except FileNotFoundError as e:
                    LOGGER.info("EDM was not found.  Disabling EDM buttons.")
                    cls.edm_server_proc = False
                LOGGER.debug("EDMButton: ensure_server_is_available complete.")

    def __init__(self, parent=None, filename=None):
        super(PyDMEDMDisplayButton, self).__init__(parent, filename)
        if PyDMEDMDisplayButton.edm_server_proc == False:
            self.setEnabled(False)        


    @classmethod
    def window_name(cls, filename, macro_string=""):
        """
        Generates a unique string identifier for this window, using the
        filename and any macros.
        """
        window_name = os.path.basename(filename)
        if macro_string:
            window_name += hashlib.md5(macro_string.encode('utf-8')).hexdigest()[0:5]
        return window_name
    
    @classmethod
    def open_edm_display(cls, filename, macro_string="", in_new_window=False):
        """
        Open an EDM display, either in a new window, or an existing one if possible.
        """
        LOGGER.debug("open_edm_display(filename={}, macro_string={}, in_new_window={})".format(filename, macro_string, in_new_window))
        if not filename:
            return
        filename = os.path.expanduser(os.path.expandvars(filename))
        cls.ensure_server_is_available()
        # Store the window name for the duration of this method to avoid
        # computing hashes repeatedly.
        wname = cls.window_name(filename, macro_string)
        if not cls.wmctrl_available:
            macro_string = "pydm_dup_workaround={noise},{macros}".format(noise=time.time(), macros=macro_string)
            cls._open_new_window(filename, wname, macro_string)
            return
        cls.invalidate_closed_windows()
        if in_new_window:
            # First check if this file is something we've already got open.
            # If it is, our EDM server will refuse to open a new copy.
            # Luckily, there is a workaround. Turns out you can do an UNLIMITED
            # number of the same display as long as you pass different macro
            # variables. So just put some unique nonsense (the current
            # timestamp) into a macro variable in this case.
            if wname in cls.windows:
                macro_string = "pydm_dup_workaround={noise},{macros}".format(noise=time.time(), macros=macro_string)
            # Next, we need to get a list of currently open windows
            try:
                before_list = {w.id: w for w in wmctrl.Window.list()}
                #Then open up the new one.
                cls._open_new_window(filename, wname, macro_string)
                # Then poll the list of open windows until it shows up.
                # Do this in a separate thread.
                window_finder_thread = threading.Thread(target=cls.wait_for_new_edm_window, args=(wname, before_list))
                window_finder_thread.start()
                #cls.wait_for_new_edm_window(wname, before_list)
            except subprocess.CalledProcessError:
                cls.wmctrl_available = False
                LOGGER.debug("Disabling wmctrl support in edmbutton.")
                macro_string = "pydm_dup_workaround={noise},{macros}".format(noise=time.time(), macros=macro_string)
                cls._open_new_window(filename, wname, macro_string)
                return              
        else: #If we're not explicity launching a new window
            # First check if this is something we've got in our dictionary of windows.
            # If it isn't, we've got no choice but to open it up as a new one.
            if wname not in cls.windows:
                cls.open_edm_display(filename, macro_string, in_new_window=True)
                return
            else:
                cls.windows[wname].activate()

    @classmethod
    def wait_for_new_edm_window(cls, wname, before_list):
        """
        Poll the list of windows from wmctrl repeatedly until we one that 
        looks like a new EDM window. Once the window is found, add it to the
        class' dictionary of windows. 
        
        This method is typically called from a separate thread to avoid locking
        everything up while polling is in progress.
        """
        new_window = None
        start_time = time.time()
        while new_window is None:
            after_list = wmctrl.Window.list()
            for win in after_list:
                # We want a window that is:
                # 1. New, not in the list of windows that existed before launching EDM
                # 2. Has a "wm class" of "edm.edm", which all EDM windows apparently have
                # 3. Does not have a window name that starts with "edm R1" - 
                #    these are the "postage stamp" windows.  We want the real display window.
                # If all of the above are met, we assume it is the window we're looking for.
                # There's no guarantee, though.  This is just a heuristic.
                if win.id not in before_list and win.wm_class.decode('utf-8') == "edm.edm" and not win.wm_name.decode('utf-8').startswith("edm R1"):
                    new_window = win
                    break
            end_time = time.time()
            if end_time - start_time > 10.0:
                LOGGER.debug("Timeout expired while trying to launch EDM window.")
                return
            time.sleep(0.1)
        assert new_window is not None
        # We completely rely on the GIL to ensure writing to this dict is safe.
        cls.windows[wname] = new_window

    @classmethod
    def invalidate_closed_windows(cls):
        """
        Clear out any windows that have been closed.
        """
        if not cls.wmctrl_available:
            return
        if len(cls.windows) == 0:
            return
        try:
            open_windows = {w.id: w for w in wmctrl.Window.list()}
            cls.windows = {wname: w for (wname, w) in cls.windows.items() if w.id in open_windows}
        except subprocess.CalledProcessError as e:
            cls.wmctrl_available = False
            LOGGER.debug("Disabling wmctrl support in edmbutton.")
            return
    
    @classmethod
    def _open_new_window(cls, filename, wname, macros):
        command = cls.edm_command
        if macros:
            command = command + ['-m', macros]
        full_command = command + ['-open', '{windowname}={filename}'.format(windowname=wname, filename=filename)]
        subprocess.Popen(full_command)

    def open_display(self, filename, macro_string="", target=None):
        """
        Open the configured `filename` with the given `target`.
        If `target` is PyDMEDMDisplayButton.EXISTING_WINDOW, an existing window will
        be raised, if it exists.  If it does not exist, a new one
        will be spawned.

        If `target` is PyDMEDMDisplayButton.NEW_WINDOW, a new window will always be
        spawned.
        """
        if not filename:
            return
        if filename.endswith(".ui") or filename.endswith(".py"):
            super(PyDMEDMDisplayButton, self).open_display(filename, macro_string, target)
            return
        if self._shift_key_was_down:
            target = self.NEW_WINDOW
        if target is None:
            if self._open_in_new_window:
                target = self.NEW_WINDOW
            else:
                target = self.EXISTING_WINDOW
        self.open_edm_display(filename, macro_string, in_new_window=(target==self.NEW_WINDOW))
