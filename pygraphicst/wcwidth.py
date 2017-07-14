# noinspection PyProtectedMember
import pygraphicst._wcwidth as _w


def width(c: str):
    if not isinstance(c, str):
        raise TypeError('Argument is not a string')

    l = 0
    for i in c:
        l += _w.wcwidth(i)
    return l


def index(s: str, to, left) -> (int, int):
    l = 0
    for i in range(len(s)):
        w = width(s[i])
        l += w
        if l > to:
            if left or l - w == to:
                return i, to + w - l
            else:
                return i + 1, l - to
    return -1, to - l


def slise(s: str, start, length=-1) -> str:
    i, p = index(s, start, False)
    if i != -1:
        s = p * ' ' + s[i:]
        if length < 0:
            return s
        else:
            i, _ = index(s, length, True)
            return s if i == -1 else s[:i]
    else:
        return ''


def split(s, length=-1):
    def spl_clean(s_: str):
        if length < 0:
            return [s_]
        else:
            ret_ = []
            while True:
                i_, _ = index(s_, length, True)
                if i_ == -1:
                    ret_.append(s_)
                    return ret_
                else:
                    ret_.append(s_[:i_])
                    s_ = s_[i_:]

    def spl_dirty(s_: str):
        ret_ = []
        ss = s_.split('\n')
        for i_ in ss:
            ret_.extend(spl_clean(i_))
        return ret_

    if isinstance(s, str):
        return spl_dirty(s)
    try:
        ret = []
        for i in s:
            ret.extend(spl_dirty(i))
        return ret
    except Exception:
        raise ValueError(f'No suitable arg for {type(s)!s}, {type(length)!s}')
