import sys
import time

load_percent = int(sys.argv[1])

duration = 60
if len(sys.argv) > 2:
    duration = int(sys.argv[2])

print("\n Will create {}% load for {} seconds.\n".format(load_percent, duration))

def count(start: int = 1000000 * 0.02):
    while start > 0:
        start -= 1


interval = 0.05
count_part = interval * load_percent/100
sleep_part = interval * max(0, (1-(load_percent/100)))


s = time.time()

while time.time()-s < duration:

    s1 = time.perf_counter()

    while time.perf_counter()-s1 < count_part:

        count()

    while time.perf_counter()-s1 < interval:

        time.sleep(0.001)

    #time.sleep(sleep_part)


e = time.time()

print("{:.1f}ms".format((e-s)*1000))




