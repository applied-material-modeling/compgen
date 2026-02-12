import sys
sys.path.append('../../../..')

from compgen import runner

if __name__ == "__main__":
    runner.run("demo.json", "../elasticity_config.json", "../parallel_config.json", "../../machine_config.json")
