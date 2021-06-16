"""
Send TTL

A utility for using the Soloist controller PSO hardware to send TTL pulses.

Usage:
    send_ttl.py <num> <gap>
    send_ttl.py (-h | --help)
    send_ttl.py --version

Options:
    -h --help    Show this screen.
    --version    Show version.
        <num>    Number of pulses.
        <gap>    Interval between pulses (ms).
"""

from edc.motor import ABRS
import docopt

ABRS_NAME = "ABRS1605-01:deg"
air_rot = ABRS(ABRS_NAME)


def test_n_ttl(Num, Gap=100):
    air_rot.PSO_ttl(Num, Gap).join()


if __name__ == ("__main__"):
    args = docopt.docopt(__doc__, version="Jan 15, 2021")
    test_n_ttl(int(args["<num>"]), int(args["<gap>"]))
