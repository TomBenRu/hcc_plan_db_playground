import math
import random


def anneal(val_old: float, val_new: float, temperature: float) -> bool:
    if val_new <= val_old:
        return True
    a = math.exp(-(val_new - val_old) / temperature)
    print(a)

    return a > random.random()


if __name__ == '__main__':
    print(anneal(5, 5.001, 0.001))
