"""python -m forensics bench    traced failures, the Flash regression and the injection test, written to results/"""
import sys

from .bench import bench

if __name__ == "__main__":
    if sys.argv[1:] != ["bench"]:
        sys.exit(__doc__)
    print(bench())
