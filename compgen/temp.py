import tempfile
import os
import shutil
import logging

logger = logging.getLogger(__name__)


class TempDirectory:
    """Context manager for creating and cleaning up a temporary directory."""

    def __init__(self, options):
        self.base_dir = options.get("storage", {}).get("temp_dir", None)
        self.delete_after = options.get("storage", {}).get("delete_temp_dir", False)

    def __enter__(self):
        if self.base_dir:
            os.makedirs(self.base_dir, exist_ok=True)
        self.temp_dir = tempfile.mkdtemp(dir=self.base_dir)
        logger.info("Created temporary directory at %s", self.temp_dir)
        self.orig_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        return self.orig_cwd, self.temp_dir

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self.orig_cwd)
        logger.info("Returning to original directory %s", self.orig_cwd)
        if self.temp_dir and self.delete_after:
            logger.info("Deleting temporary directory %s", self.temp_dir)
            shutil.rmtree(self.temp_dir)
