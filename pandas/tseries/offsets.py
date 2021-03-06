from datetime import datetime, timedelta

import numpy as np

from pandas.core.common import _count_not_none
from pandas.tseries.tools import to_datetime

# import after tools, dateutil check
from dateutil.relativedelta import relativedelta

from pandas._tseries import Timestamp
import pandas._tseries as lib

#-------------------------------------------------------------------------------
# DateOffset


class CacheableOffset(object):

    _cacheable = True


class DateOffset(object):
    """
    Standard kind of date increment used for a date range.

    Works exactly like relativedelta in terms of the keyword args you
    pass in, use of the keyword n is discouraged-- you would be better
    off specifying n in the keywords you use, but regardless it is
    there for you. n is needed for DateOffset subclasses.

    DateOffets work as follows.  Each offset specify a set of dates
    that conform to the DateOffset.  For example, Bday defines this
    set to be the set of dates that are weekdays (M-F).  To test if a
    date is in the set of a DateOffset dateOffset we can use the
    onOffset method: dateOffset.onOffset(date).

    If a date is not on a valid date, the rollback and rollforward
    methods can be used to roll the date to the nearest valid date
    before/after the date.

    DateOffsets can be created to move dates forward a given number of
    valid dates.  For example, Bday(2) can be added to a date to move
    it two business days forward.  If the date does not start on a
    valid date, first it is moved to a valid date.  Thus psedo code
    is:

    def __add__(date):
      date = rollback(date) # does nothing is date is valid
      return date + <n number of periods>

    When a date offset is created for a negitive number of periods,
    the date is first rolled forward.  The pseudo code is:

    def __add__(date):
      date = rollforward(date) # does nothing is date is valid
      return date + <n number of periods>

    Zero presents a problem.  Should it roll forward or back?  We
    arbitrarily have it rollforward:

    date + BDay(0) == BDay.rollforward(date)

    Since 0 is a bit weird, we suggest avoiding its use.
    """
    _cacheable = False
    _normalize_cache = True

    def __init__(self, n=1, **kwds):
        self.n = int(n)
        self.kwds = kwds
        if len(kwds) > 0:
            self._offset = relativedelta(**kwds)
        else:
            self._offset = timedelta(1)

    def apply(self, other):
        if len(self.kwds) > 0:
            if self.n > 0:
                for i in xrange(self.n):
                    other = other + self._offset
            else:
                for i in xrange(-self.n):
                    other = other - self._offset
            return other
        else:
            return other + timedelta(self.n)

    def isAnchored(self):
        return (self.n == 1)

    def copy(self):
        return self.__class__(self.n, **self.kwds)

    def _should_cache(self):
        return self.isAnchored() and self._cacheable

    def _params(self):
        attrs = [(k, v) for k, v in vars(self).iteritems()
                 if k not in ['kwds', '_offset', 'name']]
        attrs.extend(self.kwds.items())
        attrs = sorted(set(attrs))

        params = tuple([str(self.__class__)] + attrs)
        return params

    def __repr__(self):
        if hasattr(self, 'name') and len(self.name):
            return self.name

        className = getattr(self, '_outputName', type(self).__name__)
        exclude = set(['n', 'inc'])
        attrs = []
        for attr in self.__dict__:
            if ((attr == 'kwds' and len(self.kwds) == 0)
                or attr.startswith('_')):
                continue
            if attr not in exclude:
                attrs.append('='.join((attr, repr(getattr(self, attr)))))

        if abs(self.n) != 1:
            plural = 's'
        else:
            plural = ''

        out = '<%s ' % self.n + className + plural
        if attrs:
            out += ': ' + ', '.join(attrs)
        out += '>'
        return out

    def __eq__(self, other):
        if other is None:
            return False

        if isinstance(other, basestring):
            from pandas.tseries.frequencies import to_offset
            other = to_offset(other)

        if not isinstance(other, DateOffset):
            return False

        return self._params() == other._params()

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self._params())

    def __call__(self, other):
        return self.apply(other)

    def __add__(self, other):
        return self.apply(other)

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, datetime):
            raise TypeError('Cannot subtract datetime from offset!')
        elif type(other) == type(self):
            return self.__class__(self.n - other.n, **self.kwds)
        else: # pragma: no cover
            raise TypeError('Cannot subtract %s from %s'
                            % (type(other), type(self)))

    def __rsub__(self, other):
        return self.__class__(-self.n, **self.kwds) + other

    def __mul__(self, someInt):
        return self.__class__(n=someInt * self.n, **self.kwds)

    def __rmul__(self, someInt):
        return self.__mul__(someInt)

    def __neg__(self):
        return self.__class__(-self.n, **self.kwds)

    def rollback(self, someDate):
        """Roll provided date backward to next offset only if not on offset"""
        if not self.onOffset(someDate):
            someDate = someDate - self.__class__(1, **self.kwds)
        return someDate

    def rollforward(self, dt):
        """Roll provided date forward to next offset only if not on offset"""
        if isinstance(dt, np.datetime64):
            dt = Timestamp(dt)
        if not self.onOffset(dt):
            dt = dt + self.__class__(1, **self.kwds)
        return dt

    def onOffset(self, dt):
        if type(self) == DateOffset:
            return True

        # Default (slow) method for determining if some date is a member of the
        # date range generated by this offset. Subclasses may have this
        # re-implemented in a nicer way.
        a = dt
        b = ((dt + self) - self)
        return a == b



class BusinessDay(DateOffset, CacheableOffset):
    """
    DateOffset subclass representing possibly n business days
    """
    def __init__(self, n=1, **kwds):
        self.n = int(n)
        self.kwds = kwds
        self.offset = kwds.get('offset', timedelta(0))
        self.normalize = kwds.get('normalize', False)

    def rule_code(self):
        return 'B'

    def __repr__(self):
        if hasattr(self, 'name') and len(self.name):
            return self.name

        className = getattr(self, '_outputName', self.__class__.__name__)
        attrs = []

        if self.offset:
            attrs = ['offset=%s' % repr(self.offset)]

        if abs(self.n) != 1:
            plural = 's'
        else:
            plural = ''

        out = '<%s ' % self.n + className + plural
        if attrs:
            out += ': ' + ', '.join(attrs)
        out += '>'
        return out

    def isAnchored(self):
        return (self.n == 1)

    def apply(self, other):
        if isinstance(other, datetime):
            n = self.n

            if n == 0 and other.weekday() > 4:
                n = 1

            result = other

            while n != 0:
                k = n // abs(n)
                result = result + timedelta(k)
                if result.weekday() < 5:
                    n -= k

            if self.normalize:
                result = datetime(result.year, result.month, result.day)

            if self.offset:
                result = result + self.offset

            return result

        elif isinstance(other, (timedelta, Tick)):
            return BDay(self.n, offset=self.offset + other,
                        normalize=self.normalize)
        else:
            raise Exception('Only know how to combine business day with '
                            'datetime or timedelta!')
    @classmethod
    def onOffset(cls, dt):
        if isinstance(dt, np.datetime64):
             dt = Timestamp(dt)
        return dt.weekday() < 5


class MonthEnd(DateOffset, CacheableOffset):
    """DateOffset of one month end"""

    def apply(self, other):
        n = self.n
        _, days_in_month = lib.monthrange(other.year, other.month)
        if other.day != days_in_month:
            other = other + relativedelta(months=-1, day=31)
            if n <= 0:
                n = n + 1
        other = other + relativedelta(months=n, day=31)
        return other

    @classmethod
    def onOffset(cls, dt):
        __junk, days_in_month = lib.monthrange(dt.year, dt.month)
        return dt.day == days_in_month

    def rule_code(self):
        return 'M'


class MonthBegin(DateOffset, CacheableOffset):
    """DateOffset of one month at beginning"""

    def apply(self, other):
        n = self.n

        if other.day > 1 and n <= 0: #then roll forward if n<=0
            n += 1

        other = other + relativedelta(months=n, day=1)
        return other

    @classmethod
    def onOffset(cls, dt):
        firstDay, _ = lib.monthrange(dt.year, dt.month)
        return dt.day == (firstDay + 1)

    def rule_code(self):
        return 'MS'


class BusinessMonthEnd(DateOffset, CacheableOffset):
    """DateOffset increments between business EOM dates"""

    def isAnchored(self):
        return (self.n == 1)

    def apply(self, other):
        n = self.n

        wkday, days_in_month = lib.monthrange(other.year, other.month)
        lastBDay = days_in_month - max(((wkday + days_in_month - 1) % 7) - 4, 0)

        if n > 0 and not other.day >= lastBDay:
            n = n - 1
        elif n <= 0 and other.day > lastBDay:
            n = n + 1
        other = other + relativedelta(months=n, day=31)

        if other.weekday() > 4:
            other = other - BDay()
        return other

    def rule_code(self):
        return 'BM'


class BusinessMonthBegin(DateOffset, CacheableOffset):
    """DateOffset of one business month at beginning"""

    def apply(self, other):
        n = self.n

        wkday, _ = lib.monthrange(other.year, other.month)
        first = _get_firstbday(wkday)

        if other.day > first and n<=0:
            # as if rolled forward already
            n += 1

        other = other + relativedelta(months=n)
        wkday, _ = lib.monthrange(other.year, other.month)
        first = _get_firstbday(wkday)
        result = datetime(other.year, other.month, first)
        return result

    def rule_code(self):
        return 'BMS'


class Week(DateOffset, CacheableOffset):
    """
    Weekly offset

    Parameters
    ----------
    weekday : int, default None
        Always generate specific day of week. 0 for Monday
    """
    def __init__(self, n=1, **kwds):
        self.n = n
        self.weekday = kwds.get('weekday', None)

        if self.weekday is not None:
            if self.weekday < 0 or self.weekday > 6:
                raise Exception('Day must be 0<=day<=6, got %d' %
                                self.weekday)

        self.delta = timedelta(weeks=1)
        self.kwds = kwds

    def isAnchored(self):
        return (self.n == 1 and self.weekday is not None)

    def apply(self, other):
        if self.weekday is None:
            return other + self.n * self.delta

        if self.n > 0:
            k = self.n
            otherDay = other.weekday()
            if otherDay != self.weekday:
                other = other + timedelta((self.weekday - otherDay) % 7)
                k = k - 1
            for i in xrange(k):
                other = other + self.delta
        else:
            k = self.n
            otherDay = other.weekday()
            if otherDay != self.weekday:
                other = other + timedelta((self.weekday - otherDay) % 7)
            for i in xrange(-k):
                other = other - self.delta
        return other

    def onOffset(self, dt):
        return dt.weekday() == self.weekday

    def rule_code(self):
        suffix = ''
        if self.weekday is not None:
            suffix = '-%s' % (_weekday_dict[self.weekday])
        return 'W' + suffix

_weekday_dict = {
    0: 'MON',
    1: 'TUE',
    2: 'WED',
    3: 'THU',
    4: 'FRI',
    5: 'SAT',
    6: 'SUN'
}

class WeekOfMonth(DateOffset, CacheableOffset):
    """
    Describes monthly dates like "the Tuesday of the 2nd week of each month"

    Parameters
    ----------
    n : int
    week : {0, 1, 2, 3, ...}
        0 is 1st week of month, 1 2nd week, etc.
    weekday : {0, 1, ..., 6}
        0: Mondays
        1: Tuedays
        2: Wednesdays
        3: Thursdays
        4: Fridays
        5: Saturdays
        6: Sundays
    """
    def __init__(self, n=1, **kwds):
        self.n = n
        self.weekday = kwds['weekday']
        self.week = kwds['week']

        if self.n == 0:
            raise Exception('N cannot be 0')

        if self.weekday < 0 or self.weekday > 6:
            raise Exception('Day must be 0<=day<=6, got %d' %
                            self.weekday)
        if self.week < 0 or self.week > 3:
            raise Exception('Week must be 0<=day<=3, got %d' %
                            self.week)

        self.kwds = kwds

    def apply(self, other):
        offsetOfMonth = self.getOffsetOfMonth(other)

        if offsetOfMonth > other:
            if self.n > 0:
                months = self.n - 1
            else:
                months = self.n
        elif offsetOfMonth == other:
            months = self.n
        else:
            if self.n > 0:
                months = self.n
            else:
                months = self.n + 1

        return self.getOffsetOfMonth(other + relativedelta(months=months, day=1))

    def getOffsetOfMonth(self, dt):
        w = Week(weekday=self.weekday)
        d = datetime(dt.year, dt.month, 1)

        d = w.rollforward(d)

        for i in xrange(self.week):
            d = w.apply(d)

        return d

    def onOffset(self, dt):
        return dt == self.getOffsetOfMonth(dt)

    def rule_code(self):
        suffix = '-%d%s' % (self.week + 1, _weekday_dict.get(self.weekday, ''))
        return 'WOM' + suffix


class BQuarterEnd(DateOffset, CacheableOffset):
    """DateOffset increments between business Quarter dates
    startingMonth = 1 corresponds to dates like 1/31/2007, 4/30/2007, ...
    startingMonth = 2 corresponds to dates like 2/28/2007, 5/31/2007, ...
    startingMonth = 3 corresponds to dates like 3/30/2007, 6/29/2007, ...
    """
    _outputName = 'BusinessQuarterEnd'

    def __init__(self, n=1, **kwds):
        self.n = n
        self.startingMonth = kwds.get('startingMonth', 3)

        self.offset = BMonthEnd(3)
        self.kwds = kwds

    def isAnchored(self):
        return (self.n == 1 and self.startingMonth is not None)

    def apply(self, other):
        n = self.n

        wkday, days_in_month = lib.monthrange(other.year, other.month)
        lastBDay = days_in_month - max(((wkday + days_in_month - 1) % 7) - 4, 0)

        monthsToGo = 3 - ((other.month - self.startingMonth) % 3)
        if monthsToGo == 3:
            monthsToGo = 0

        if n > 0 and not (other.day >= lastBDay and monthsToGo == 0):
            n = n - 1
        elif n <= 0 and other.day > lastBDay and monthsToGo == 0:
            n = n + 1

        other = other + relativedelta(months=monthsToGo + 3*n, day=31)

        if other.weekday() > 4:
            other = other - BDay()

        return other

    def onOffset(self, dt):
        modMonth = (dt.month - self.startingMonth) % 3
        return BMonthEnd().onOffset(dt) and modMonth == 0

    def rule_code(self):
        suffix = '-%s' % _month_dict[self.startingMonth]
        return 'BQ' + suffix


_month_dict = {
    1: 'JAN',
    2: 'FEB',
    3: 'MAR',
    4: 'APR',
    5: 'MAY',
    6: 'JUN',
    7: 'JUL',
    8: 'AUG',
    9: 'SEP',
    10: 'OCT',
    11: 'NOV',
    12: 'DEC'
}


class BQuarterBegin(DateOffset, CacheableOffset):
    _outputName = "BusinessQuarterBegin"

    def __init__(self, n=1, **kwds):
        self.n = n
        self.startingMonth = kwds.get('startingMonth', 3)

        self.offset = BMonthBegin(3)
        self.kwds = kwds

    def isAnchored(self):
        return (self.n == 1 and self.startingMonth is not None)

    def apply(self, other):
        n = self.n

        wkday, _ = lib.monthrange(other.year, other.month)

        first = _get_firstbday(wkday)

        monthsSince = (other.month - self.startingMonth) % 3
        if monthsSince == 3: # on offset
            monthsSince = 0

        if n <= 0 and monthsSince != 0: # make sure to roll forward so negate
            monthsSince = monthsSince - 3

        # roll forward if on same month later than first bday
        if n <= 0 and (monthsSince == 0 and other.day > first):
            n = n + 1
        # pretend to roll back if on same month but before firstbday
        elif n > 0 and (monthsSince == 0 and other.day < first):
            n = n - 1

        # get the first bday for result
        other = other + relativedelta(months=3*n - monthsSince)
        wkday, _ = lib.monthrange(other.year, other.month)
        first = _get_firstbday(wkday)
        result = datetime(other.year, other.month, first)
        return result

    def rule_code(self):
        suffix = '-%s' % _month_dict[self.startingMonth]
        return 'BQS' + suffix


class QuarterEnd(DateOffset, CacheableOffset):
    """DateOffset increments between business Quarter dates
    startingMonth = 1 corresponds to dates like 1/31/2007, 4/30/2007, ...
    startingMonth = 2 corresponds to dates like 2/28/2007, 5/31/2007, ...
    startingMonth = 3 corresponds to dates like 3/31/2007, 6/30/2007, ...
    """
    _outputName = 'QuarterEnd'

    def __init__(self, n=1, **kwds):
        self.n = n
        self.startingMonth = kwds.get('startingMonth', 3)

        self.offset = MonthEnd(3)
        self.kwds = kwds

    def isAnchored(self):
        return (self.n == 1 and self.startingMonth is not None)

    def apply(self, other):
        n = self.n

        wkday, days_in_month = lib.monthrange(other.year, other.month)

        monthsToGo = 3 - ((other.month - self.startingMonth) % 3)
        if monthsToGo == 3:
            monthsToGo = 0

        if n > 0 and not (other.day >= days_in_month and monthsToGo == 0):
            n = n - 1

        other = other + relativedelta(months=monthsToGo + 3*n, day=31)

        return other

    def onOffset(self, dt):
        modMonth = (dt.month - self.startingMonth) % 3
        return MonthEnd().onOffset(dt) and modMonth == 0

    def rule_code(self):
        suffix = '-%s' % _month_dict[self.startingMonth]
        return 'Q' + suffix


class QuarterBegin(DateOffset, CacheableOffset):
    _outputName = 'QuarterBegin'

    def __init__(self, n=1, **kwds):
        self.n = n
        self.startingMonth = kwds.get('startingMonth', 3)

        self.offset = MonthBegin(3)
        self.kwds = kwds

    def isAnchored(self):
        return (self.n == 1 and self.startingMonth is not None)

    def apply(self, other):
        n = self.n

        wkday, days_in_month = lib.monthrange(other.year, other.month)

        monthsSince = (other.month - self.startingMonth) % 3

        if monthsSince == 3: # on an offset
            monthsSince = 0

        if n <= 0 and monthsSince != 0:
            # make sure you roll forward, so negate
            monthsSince = monthsSince - 3

        if n < 0 and (monthsSince == 0 and other.day > 1):
            # after start, so come back an extra period as if rolled forward
            n = n + 1

        other = other + relativedelta(months=3*n - monthsSince, day=1)
        return other

    def rule_code(self):
        suffix = '-%s' % _month_dict[self.startingMonth]
        return 'QS' + suffix


class BYearEnd(DateOffset, CacheableOffset):
    """DateOffset increments between business EOM dates"""
    _outputName = 'BusinessYearEnd'

    def __init__(self, n=1, **kwds):
        self.month = kwds.get('month', 12)

        if self.month < 1 or self.month > 12:
            raise Exception('Month must go from 1 to 12')

        DateOffset.__init__(self, n=n, **kwds)

    def apply(self, other):
        n = self.n

        wkday, days_in_month = lib.monthrange(other.year, self.month)
        lastBDay = (days_in_month -
                    max(((wkday + days_in_month - 1) % 7) - 4, 0))

        years = n
        if n > 0:
            if (other.month < self.month or
                (other.month == self.month and other.day < lastBDay)):
                years -= 1
        elif n <= 0:
            if (other.month > self.month or
                (other.month == self.month and other.day > lastBDay)):
                years += 1

        other = other + relativedelta(years=years)

        _, days_in_month = lib.monthrange(other.year, self.month)
        result = datetime(other.year, self.month, days_in_month,
                          other.hour, other.minute, other.second,
                          other.microsecond)

        if result.weekday() > 4:
            result = result - BDay()

        return result

    def rule_code(self):
        suffix = '-%s' % _month_dict[self.month]
        return 'BA' + suffix


class BYearBegin(DateOffset, CacheableOffset):
    """DateOffset increments between business year begin dates"""
    _outputName = 'BusinessYearBegin'

    def __init__(self, n=1, **kwds):
        self.month = kwds.get('month', 1)

        if self.month < 1 or self.month > 12:
            raise Exception('Month must go from 1 to 12')

        DateOffset.__init__(self, n=n, **kwds)

    def apply(self, other):
        n = self.n

        wkday, days_in_month = lib.monthrange(other.year, self.month)

        first = _get_firstbday(wkday)

        years = n


        if n > 0: # roll back first for positive n
            if (other.month < self.month or
                (other.month == self.month and other.day < first)):
                years -= 1
        elif n <= 0: # roll forward
            if (other.month > self.month or
                (other.month == self.month and other.day > first)):
                years += 1

        # set first bday for result
        other = other + relativedelta(years = years)
        wkday, days_in_month = lib.monthrange(other.year, self.month)
        first = _get_firstbday(wkday)
        return datetime(other.year, self.month, first)

    def rule_code(self):
        suffix = '-%s' % _month_dict[self.month]
        return 'BAS' + suffix


class YearEnd(DateOffset, CacheableOffset):
    """DateOffset increments between calendar year ends"""

    def __init__(self, n=1, **kwds):
        self.month = kwds.get('month', 12)

        if self.month < 1 or self.month > 12:
            raise Exception('Month must go from 1 to 12')

        DateOffset.__init__(self, n=n, **kwds)

    def apply(self, other):
        n = self.n
        wkday, days_in_month = lib.monthrange(other.year, self.month)
        if other.month != self.month or other.day != days_in_month:
            other = datetime(other.year - 1, self.month, days_in_month,
                             other.hour, other.minute, other.second,
                             other.microsecond)
            if n <= 0:
                n = n + 1
        other = other + relativedelta(years=n)
        return other

    def onOffset(self, dt):
        wkday, days_in_month = lib.monthrange(dt.year, self.month)
        return self.month == dt.month and dt.day == days_in_month

    def rule_code(self):
        suffix = '-%s' % _month_dict[self.month]
        return 'A' + suffix


class YearBegin(DateOffset, CacheableOffset):
    """DateOffset increments between calendar year begin dates"""

    def __init__(self, n=1, **kwds):
        self.month = kwds.get('month', 12)

        if self.month < 1 or self.month > 12:
            raise Exception('Month must go from 1 to 12')

        DateOffset.__init__(self, n=n, **kwds)

    def apply(self, other):
        n = self.n
        if other.month != 1 or other.day != 1:
            other = datetime(other.year, 1, 1,
                             other.hour, other.minute, other.second,
                             other.microsecond)
            if n <= 0:
                n = n + 1
        other = other + relativedelta(years = n, day=1)
        return other

    @classmethod
    def onOffset(cls, dt):
        return dt.month == 1 and dt.day == 1

    def rule_code(self):
        suffix = '-%s' % _month_dict[self.month]
        return 'AS' + suffix


#-------------------------------------------------------------------------------
# Ticks

class Tick(DateOffset):
    _delta = None
    _inc = timedelta(microseconds=1000)

    def __eq__(self, other):
        if isinstance(other, basestring):
            from pandas.tseries.frequencies import to_offset
            other = to_offset(other)

        if isinstance(other, Tick):
            return self.delta == other.delta
        else:
            return DateOffset.__eq__(self, other)

    def __ne__(self, other):
        if isinstance(other, basestring):
            from pandas.tseries.frequencies import to_offset
            other = to_offset(other)

        if isinstance(other, Tick):
            return self.delta != other.delta
        else:
            return DateOffset.__ne__(self, other)

    @property
    def delta(self):
        if self._delta is None:
            self._delta = self.n * self._inc

        return self._delta

    def us_stride(self):
        return _delta_to_microseconds(self.delta)

    def apply(self, other):
        if isinstance(other, (datetime, timedelta)):
            return other + self.delta
        elif isinstance(other, type(self)):
            return type(self)(self.n + other.n)

    def rule_code(self):
        return 'T'

def _delta_to_microseconds(delta):
    return (delta.days * 24 * 60 * 60 * 1000000
            + delta.seconds * 1000000
            + delta.microseconds)

class Day(Tick, CacheableOffset):
    _inc = timedelta(1)

    def rule_code(self):
        return 'D'

class Hour(Tick):
    _inc = timedelta(0, 3600)

    def rule_code(self):
        return 'H'

class Minute(Tick):
    _inc = timedelta(0, 60)

    def rule_code(self):
        return 'T'

class Second(Tick):
    _inc = timedelta(0, 1)

    def rule_code(self):
        return 'S'

class Milli(Tick):

    def rule_code(self):
        return 'L'

class Micro(Tick):
    _inc = timedelta(microseconds=1)

    def rule_code(self):
        return 'U'

BDay = BusinessDay
BMonthEnd = BusinessMonthEnd
BMonthBegin = BusinessMonthBegin

day = DateOffset()
bday = BDay()
businessDay = bday
monthEnd = MonthEnd()
yearEnd = YearEnd()
yearBegin = YearBegin()
bmonthEnd = BMonthEnd()
businessMonthEnd = bmonthEnd
bquarterEnd = BQuarterEnd()
quarterEnd = QuarterEnd()
byearEnd = BYearEnd()
week = Week()


# Functions/offsets to roll dates forward
thisMonthEnd = MonthEnd(0)
thisBMonthEnd = BMonthEnd(0)
thisYearEnd = YearEnd(0)
thisYearBegin = YearBegin(0)
thisBQuarterEnd = BQuarterEnd(0)
thisQuarterEnd = QuarterEnd(0)

# Functions to check where a date lies
isBusinessDay = BDay().onOffset
isMonthEnd = MonthEnd().onOffset
isBMonthEnd = BMonthEnd().onOffset


def _get_firstbday(wkday):
    """
    wkday is the result of monthrange(year, month)

    If it's a saturday or sunday, increment first business day to reflect this
    """
    first = 1
    if wkday == 5: # on Saturday
        first = 3
    elif wkday == 6: # on Sunday
        first = 2
    return first


def generate_range(start=None, end=None, periods=None,
                   offset=BDay(), time_rule=None):
    """
    Generates a sequence of dates corresponding to the specified time
    offset. Similar to dateutil.rrule except uses pandas DateOffset
    objects to represent time increments

    Parameters
    ----------
    start : datetime (default None)
    end : datetime (default None)
    periods : int, optional

    Note
    ----
    * This method is faster for generating weekdays than dateutil.rrule
    * At least two of (start, end, periods) must be specified.
    * If both start and end are specified, the returned dates will
    satisfy start <= date <= end.

    Returns
    -------
    dates : generator object

    """
    if time_rule is not None:
        from pandas.tseries.frequencies import get_offset
        offset = get_offset(time_rule)

    start = to_datetime(start)
    end = to_datetime(end)

    if start and not offset.onOffset(start):
        start = offset.rollforward(start)

    if end and not offset.onOffset(end):
        end = offset.rollback(end)

        if periods is None and end < start:
            end = None
            periods = 0

    if _count_not_none(start, end, periods) < 2:
        raise ValueError('Must specify 2 of start, end, periods')

    if end is None:
        end = start + (periods - 1) * offset

    if start is None:
        start = end - (periods - 1) * offset

    cur = start

    next_date = cur
    while cur <= end:
        yield cur

        # faster than cur + offset
        next_date = offset.apply(cur)
        if next_date <= cur:
            raise ValueError('Offset %s did not increment date' % offset)
        cur = next_date
