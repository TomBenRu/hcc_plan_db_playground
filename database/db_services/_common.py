import inspect
import logging

logger = logging.getLogger(__name__)
LOGGING_ENABLED = False


def log_function_info():
    if not LOGGING_ENABLED:
        return
    frame = inspect.currentframe().f_back
    module_name = frame.f_globals.get('__name__', '?')
    func_name = frame.f_code.co_name
    logger.info(f'function: {module_name}.{func_name}\n'
                f'args: {frame.f_locals}')