import multiprocessing
import time


def increase(counter: multiprocessing.Value):
    for _ in range(20):
        with counter.get_lock():
            counter.value += 1
        time.sleep(0.1)


def decrease(counter: multiprocessing.Value):
    for _ in range(20):
        with counter.get_lock():
            counter.value -= 1
        time.sleep(0.1)


counter = multiprocessing.Value('i', 0)

decrease_processes = []
increase_processes = []

def start_processes():
    for _ in range(10):
        p = multiprocessing.Process(target=increase, args=[counter])
        p.start()
        increase_processes.append(p)

    for _ in range(10):
        p_d = multiprocessing.Process(target=decrease, args=[counter])
        p_d.start()
        decrease_processes.append(p_d)

    for p in decrease_processes:
        p.join()

    for p in increase_processes:
        p.join()


if __name__ == '__main__':
    start_processes()

    print(f'{counter.value=}')
