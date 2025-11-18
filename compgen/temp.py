import tempfile


def make_temp_directory(options):
    """Create a temporary directory for storing intermediate files.

    Args:
        options (dict): Configuration options dictionary.
    """
    base_temp_dir = options.get("storage", {}).get("temp_dir", None)
    return tempfile.mkdtemp(dir=base_temp_dir)
