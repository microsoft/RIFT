import idaapi
import idautils
import ida_ida
import ida_loader
from librift_ida.rift_ida_core import RiftIdaCore,RIFTNotSupported
from librift.utils import get_logger
from librift_ida.rift_form import RiftIdaForm
import os


class RiftIda(idaapi.plugin_t):

    flags = idaapi.PLUGIN_FIX
    comment = "RIFT"
    help = "FLIRT Signature Generator for rust binaries"
    wanted_name = "RIFT"
    wanted_hotkey = ""
    dialog = None

    def init(self):
        self.window = None
        self.logger = get_logger()
        self.core_initialized = False
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        ess_path = os.path.join(plugin_dir, "rift_essentials")
        self.core = RiftIdaCore(self.logger, ess_path)
        return idaapi.PLUGIN_KEEP
    
    def run(self, arg):
        
        # Initialize Core, abort if we cannot initialize it
        if not self.core_initialized:
            self.core_initialized = self.core.init_env()
        if not self.core_initialized:
            return 0

        rustmeta = self.core.get_rustmeta()
        if rustmeta is None:
            self.logger.error("Could not generate RustMeta from strings")
            return 0
        try:
            rustmeta.arch = self.core.get_arch()
            rustmeta.filetype = self.core.get_ftype()
        except RIFTNotSupported:
            self.logger.exception("Binary is not supported by RIFT!")
            return 0

        # initialize window, pass information
        self.window = RiftIdaForm(self.core, self.logger, rustmeta)
        self.window.Show("RIFT")
        self.logger.info("Spawned Window!")
        return 1
           
plugin = RiftIda()

def PLUGIN_ENTRY():
    global plugin
    return plugin