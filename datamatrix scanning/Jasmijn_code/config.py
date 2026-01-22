# =============================================================================
# Configuration settings for the datamatrix scanning application
# =============================================================================

# Set to True for production (disables all timing prints and reduces logging)
# Set to False for debugging (enables timing prints and verbose logging)
PRODUCTION_MODE = False


def create_timer_decorator(module_name: str = "", active: bool = False):
    """
    Creates a timer decorator that respects PRODUCTION_MODE.
    In production mode, the decorator does nothing (no overhead).
    In debug mode, it prints execution time.
    
    Usage:
        timer_func = create_timer_decorator("MyModule", active=True)
        
        @timer_func
        def my_function():
            pass
    """
    import time
    
    def timer_func(func):
        if PRODUCTION_MODE or not active:
            return func  # No overhead in production or if not active
        
        def wrap_func(*args, **kwargs):
            t1 = time.perf_counter()    
            result = func(*args, **kwargs)
            t2 = time.perf_counter()
            prefix = f"{module_name} - " if module_name else ""
            print(f'{prefix}Function {func.__name__!r} executed in {(t2-t1)*1000:.4f} milliseconds')
            return result
        return wrap_func
    
    return timer_func
