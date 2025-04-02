from globals import LSLAvailable

from pylsl import local_clock
from time import perf_counter

# clock function, that uses LSL clock if available, else it uses per_counter
# since on windows it is more precise than time.time
def clock():
    if LSLAvailable:
        return local_clock()
    else:
        return perf_counter()