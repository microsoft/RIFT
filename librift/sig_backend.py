from abc import ABC, abstractmethod

# Signature formats RIFT knows how to emit. Single source of truth shared by the
# CLI, the server and the generator so the three cannot drift apart.
SUPPORTED_FORMATS = ("flirt", "fid")

# Default format, keeps the pre-existing IDA behaviour for callers that do not
# ask for anything specific. The CLI selects formats with one boolean flag each
# (--flirt, --fidb), so there is no combined alias.
DEFAULT_FORMAT = "flirt"

class SignatureBackendError(Exception):
    """Raised when a signature backend cannot produce its artifact."""
    pass


class SignatureBackend(ABC):
    """
    Abstract base class for signature file creators.
        
    Attributes:
        name (str): Format identifier, one of SUPPORTED_FORMATS.
        extension (str): Artifact file extension, including the leading dot.
    """

    name = None
    extension = None

    def __init__(self, logger):
        """Initialization routine."""
        self.logger = logger

    @abstractmethod
    def generate(self, coff_files, out_path, meta, crate=None):
        """
        Generate signature files from the given COFF files.

        Args:
            coff_files (list): Paths to the object files to describe.
            out_path (str): Absolute output path of the artifact. 
            meta (RustMetadata): Metadata of the analyzed binary, carrying the
                rust version and target triple identity of the artifact.
            crate (RustCrate, optional): The crate being described. None when
                the artifact covers the rustc toolchain itself.
        Returns:
            str: Path to the generated artifact (out_path).
        Raises:
            SignatureBackendError: If the artifact could not be produced.
        """
        pass
