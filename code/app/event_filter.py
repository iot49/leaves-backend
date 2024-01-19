from time import ticks_ms, ticks_diff
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

"""Filter state updates."""


# raised by filter to signal no update
class NoUpdate(Exception):
    pass


class ABC:
    pass

class AbstractFilter(ABC):

    def filter(value):
        raise NotImplementedError("StateFilter is an abstract class")


class DuplicateFilter(AbstractFilter):

    def __init__(self, _):
        self.last = None

    def filter(self, value):
        if value == self.last:
            raise NoUpdate()
        self.last = value
        return value


class AbstolFilter(AbstractFilter):

    def __init__(self, absol):
        self.abstol = float(absol)
        self.last = None

    def filter(self, value):
        if self.last == None:
            self.last = value
            return value
        delta = abs(value - self.last)
        self.last = value
        if delta < self.abstol:
            logger.debug(f"abstol {delta} < {self.abstol} v={value}")
            raise NoUpdate()
        return value


class LpfFilter(AbstractFilter):

    def __init__(self, tau):
        # tau is in seconds, but filter measures time in ms
        self.wc = 0.001/float(tau)
        self.last_v = None
        self.last_t = None

    def filter(self, value):
        t = ticks_ms()
        if self.last_v == None:
            self.last_v = value
            self.last_t = t
            return value
        ts = ticks_diff(t, self.last_t)
        self.last_t = t
        beta = 1/(1 + self.wc*ts)
        self.last_v = beta*self.last_v + (1-beta)*value
        return self.last_v


class OffsetFilter(AbstractFilter):

    def __init__(self, offset):
        self._offset = float(offset)

    def filter(self, value):
        return value + self._offset
    

class ScaleFilter(AbstractFilter):

    def __init__(self, scale):
        self._scale = float(scale)

    def filter(self, value):
        return value * self._scale
