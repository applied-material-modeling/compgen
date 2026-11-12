# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import sys

sys.path.append("..")

from compgen import runner

if __name__ == "__main__":
    # This demo shows how to run predefined structures from a numpy file.
    # Take a look at 'demos/predefined_structures.json' for the problem configuration, which mirrors
    # our "fixed material' elasticity examples, but rather than make random structures it loads them from
    # test_structures.npy.

    # test_structures.npy is a (1,256,256) array.  The first index can be the number of structures you want
    # to evaluate.

    # There is an annoyance: my previous generators were meant to generate infinite structures on demand, so the
    # gen.FromNumpyGenerator class will just infinitely loop over the structures in the file.
    # The annoyance then is you should set 'number' in the JSON to the number of structures in the npy file (here 1),
    # otherwise it will just loop what you have to make up the difference.

    # Also note you need to setup 'demos/machine_config.json' to your machine information.  I can help with this on aurora.

    results = runner.run("predefined_structures.json", "machine_config.json")

    # Results is a list of of a list of dictionaries.  The outer list is over each structure in your input.
    # The inner list is over each loading direction in our standard set (here 3 for 2D, 6 for 3D).

    # The dictionaries are the results, basically in the same structure as our HDF5 output files.

    print(results)
