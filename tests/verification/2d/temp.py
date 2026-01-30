import sys
sys.path.append('../../..')

from compgen import runner

runner.run("thermal_conductivity.json", "../thermal_moose.json", "../test_config.json")
