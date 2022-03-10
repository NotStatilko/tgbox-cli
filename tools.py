import tgbox

from typing import AsyncGenerator
from os import system, _exit, name as os_name


# This is a dirty way to exit from program,
# but should be OK for this CLI design. The
# default sys.exit doesn't work, and script
# just freeze, seems that event loop isn't
# closed for some reason, or maybe some
# threads prevent stoping. Tgbox is async
# library, so maybe we should deal with it.
exit_program = lambda: _exit(0) # Kill and return 0 exitcode.

# This will clear console, we use it once.
clear_console = lambda: system('cls' if os_name in ('nt','dos') else 'clear')

class Progress:
    """
    This is a little wrapper around enlighten
    
    from enlighten import get_manager

    manager = get_manager()
    
    tgbox.api.DecryptedLocalBox.push_file(
        ..., progress_callback=Progress(manager).update
    )
    """
    def __init__(self, manager, desc: str=None):
        self.desc = desc
        self.counter = None
        self.manager = manager
        
        # For update
        self.total_blocks = 0
        
        # For update_2
        self.initialized = False

        self.BAR_FORMAT = '{desc} {percentage:3.0f}%|{bar}| [ETA {eta}]'

    def update(self, _, total):
        if not self.total_blocks:
            self.total_blocks = total / 524288
        
            if int(self.total_blocks) != self.total_blocks:
                self.total_blocks = int(self.total_blocks) + 1
            
            desc = self.desc[:40]
            
            if desc != self.desc:
                desc = desc[:37] + '...'

            while len(desc) < 40:
                desc += ' '

            self.counter = self.manager.counter(
                total=self.total_blocks, desc=desc,
                unit='x 512KB', color='gray', 
                bar_format=self.BAR_FORMAT
            )
        self.counter.update()

    def update_2(self, current, total):
        if not self.initialized:
            self.counter = self.manager.counter(
                total=total, desc='Synchronizing...',
                unit='ID', color='gray', 
                bar_format=self.BAR_FORMAT
            )
            for _ in range(current):
                self.counter.update()
            self.initialized = True
        else:
            self.counter.update()


def format_bytes(size):
    # That's not mine. Thanks to the 
    # https://stackoverflow.com/a/49361727
    
    power, n = 2**10, 0
    power_labels = {
        0 : '', 
        1: 'K', 
        2: 'M', 
        3: 'G'
    }
    while size > power:
        size /= power; n += 1
    return f'{round(size,1)}{power_labels[n]}B'

def sync_async_gen(async_gen: AsyncGenerator):
    """
    This will make async generator to sync
    generator, so we can write "async for".
    """
    try:
        while True:
            yield tgbox.sync(tgbox.tools.anext(async_gen)) 
    except StopAsyncIteration:
        return 

def filters_to_searchfilter(filters: tuple) -> tgbox.tools.SearchFilter:
    """
    This function will make SearchFilter from
    tuple like ('id=5', 'max_size='1024', ...)
    """
    include = {}
    exclude = {}
    current = 0 # Include
    
    for filter in filters:
        if filter in ('+i', '++include'):
            current = 0
        elif filter in ('+e', '++exclude'):
            current = 1
        else:
            current_filter = exclude if current else include
            filter = filter.split('=',1)

            if filter[0] not in current_filter:
                current_filter[filter[0]] = [filter[1]]
            else:
                current_filter[filter[0]].append(filter[1])
    
    return tgbox.tools.SearchFilter(**include).exclude(**exclude)
