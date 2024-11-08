import ctypes


# todo: verbessern, sodass dieses Modul systemunabhängig ist (funktioniert derzeit nur unter Windows).
#  Siehe try_outs/try_out_mutex.py


def create_mutex():
    # Create a mutex
    ctypes.windll.kernel32.CreateMutexW(None, False, "UniqueHccPlanApplicationMutex")
    return ctypes.windll.kernel32.GetLastError()


def check():
    # Try to create the mutex
    last_error = create_mutex()

    # If the mutex already exists, exit the application
    return last_error != 183  # ERROR_ALREADY_EXISTS

