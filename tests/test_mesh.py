import os
from unittest.mock import patch, MagicMock
import pytest
from compgen.mesh import sculpt

def test_sculpt_with_full_settings():
    """Test sculpt when all keys are explicitly set under settings['sculpt']."""
    settings = {
        "sculpt": {
            "executable": "/path/to/psculpt",
            "mpi": "/path/to/mpiexec",
            "rank_command": "-np",
            "epu": "/path/to/epu",
            "options": ["--smooth", "5"],
            "environment": {"VAR": "VALUE"}
        },
        "mpi": {
            "ranks": "4"
        },
        "verbose": True
    }

    with patch("subprocess.run") as mock_run:
        sculpt("input_mesh.e", prefix="sculpted_", settings=settings)

        assert mock_run.call_count == 2
        
        # Check first run (sculpt execution)
        first_call_args = mock_run.call_args_list[0]
        cmd = first_call_args[0][0]
        kwargs = first_call_args[1]
        
        assert cmd == [
            "/path/to/mpiexec",
            "-np",
            "4",
            "/path/to/psculpt",
            "--smooth",
            "5",
            "-ice",
            "input_mesh.e",
            "--exodus_file",
            "sculpted_input_mesh"
        ]
        assert kwargs["env"]["VAR"] == "VALUE"
        assert kwargs["capture_output"] is False  # verbose is True

        # Check second run (epu execution)
        second_call_args = mock_run.call_args_list[1]
        epu_cmd = second_call_args[0][0]
        
        assert epu_cmd == [
            "/path/to/epu",
            "-auto",
            "sculpted_input_mesh.e.4.0"
        ]


def test_sculpt_with_missing_keys_fallback():
    """Test sculpt when sculpt.mpi, sculpt.rank_command, and sculpt.epu are missing.
    This replicates the KeyError scenario reported by the user.
    """
    settings = {
        "sculpt": {
            "executable": "/path/to/psculpt",
            "options": ["--smooth", "5"]
        },
        "mpi": {
            "executable": "mpirun",
            "rank_command": "-np",
            "ranks": "6"
        },
        "verbose": False
    }

    with patch("subprocess.run") as mock_run:
        sculpt("input_mesh.e", prefix="sculpted_", settings=settings)

        assert mock_run.call_count == 2
        
        # Check first run (sculpt execution using fallback keys)
        first_call_args = mock_run.call_args_list[0]
        cmd = first_call_args[0][0]
        kwargs = first_call_args[1]
        
        assert cmd == [
            "mpirun",          # falls back to mpi.executable
            "-np",             # falls back to mpi.rank_command
            "6",               # mpi.ranks
            "/path/to/psculpt",
            "--smooth",
            "5",
            "-ice",
            "input_mesh.e",
            "--exodus_file",
            "sculpted_input_mesh"
        ]
        assert kwargs["capture_output"] is True  # verbose is False

        # Check second run (epu execution, falls back to "epu" name)
        second_call_args = mock_run.call_args_list[1]
        epu_cmd = second_call_args[0][0]
        
        assert epu_cmd == [
            "epu",             # falls back to default "epu"
            "-auto",
            "sculpted_input_mesh.e.6.0"
        ]


def test_sculpt_with_epu_beside_executable():
    """Test that sculpt automatically finds epu next to sculpt executable if present."""
    settings = {
        "sculpt": {
            "executable": "/path/to/psculpt",
            "options": []
        },
        "mpi": {
            "executable": "mpirun",
            "rank_command": "-np",
            "ranks": "2"
        }
    }

    with patch("subprocess.run") as mock_run, \
         patch("os.path.isfile", side_effect=lambda path: path == "/path/to/epu"):
        sculpt("input_mesh.e", settings=settings)

        second_call_args = mock_run.call_args_list[1]
        epu_cmd = second_call_args[0][0]
        
        # Since os.path.isfile for "/path/to/epu" returns True, it should use that path
        assert epu_cmd == [
            "/path/to/epu",
            "-auto",
            "sculpted_input_mesh.e.2.0"
        ]
