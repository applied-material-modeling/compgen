import logging
import traceback
from compgen import runner

logging.basicConfig(level=logging.DEBUG)

try:
    results = runner.run("fracture_predefined.json", "machine_config.json")
    print("Results:", results)
except Exception as e:
    print("Caught exception in main:")
    traceback.print_exc()
