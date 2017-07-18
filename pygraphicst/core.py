import curses as _curses
import curses.ascii as _ascii
import math as _math
import re as _re
import time as _time
import typing as _typing
from typing import Callable as _Callable
from typing import Optional as _Optional

import pygraphicst.constants as _constants
import pygraphicst.wcwidth as _wcwidth

N = _typing.TypeVar('N', int, float)
_pattern_backspace = _re.compile('.' + chr(127))


def _dist(items, exe):
    f = False
    for i in items:
        if exe(i):
            f = True
    return f


def _call(e):
    def f(w):
        e(w)
        return False

    return f


class Timer:
    def __init__(self, ms: int, exe):
        self.frequency = ms / 1000
        self.next = _time.time() + self.frequency
        self.exe = exe

    def trigger(self):
        t = _time.time()
        if t >= self.next:
            self.exe()
            while self.next <= t:
                self.next += self.frequency

    def reset(self):
        self.next = _time.time() + self.frequency


class Logger:
    def __init__(self, exe, number=True):
        self.exe = exe
        self.number = number
        self.counter = 0

    def log(self, s, type_=0):
        self.exe('[{:d}]: {:s}'.format(self.counter, s), type_)
        self.counter += 1


class Canvas:
    def draw_str(
            self, string: str, x_left: int = 0, y_top: int = 0, length=0,
            attr=_constants.Attibute.NORMAL,
            color_f: int = _constants.Color.DEFAULT,
            color_b: int = _constants.Color.DEFAULT
    ):
        pass

    def draw_border(self):
        pass

    def cursor_set(self, x, y):
        pass

    def cursor_unset(self):
        pass

    def clear(self):
        pass

    def canvas(self, x_left, y_top, x_size, y_size, x_start, y_start) -> 'Canvas':
        pass

    @property
    def xy_position(self) -> _typing.Tuple[int, int]:
        return 0, 0


class Widget:
    def __init__(self, locator: _Callable = lambda x, y: (0, 0)):
        self.canvas = None
        self.locator = locator
        self.x_left = self.y_top = -1
        self.container = None

    def on_refresh(self) -> None:
        pass

    # return if the event should be consumed
    def on_key(self, ch) -> bool:
        return False

    # return if the event should be consumed
    def on_mouse(self, x, y, state) -> bool:
        return False

    def on_canvas(self, canvas: Canvas) -> None:
        self.canvas = canvas

    def on_layout(self, x, y) -> None:
        self.x_left, self.y_top = [int(round(i)) for i in self.locator(x, y)]

    def on_draw(self) -> None:
        pass

    def on_focused(self) -> bool:
        return False

    def on_unfocused(self, w: 'Widget') -> bool:
        return True

    def on_container(self, container):
        self.container = container

    def on_next(self) -> bool:
        return False

    @property
    def xy_position(self) -> [int, int]:
        return self.x_left, self.y_top


class Window:
    INSTANCE: 'Window' = None
    STATE_INIT = 0
    STATE_LAYOUT = 1
    STATE_SERVE = 2

    def __init__(self, logger: _Callable = lambda s: ()):
        self._window = None
        self.key_lsnr: [_Callable] = []
        self.mouse_lsnr = []
        self.logger = Logger(logger)
        self.period = 0.02
        self.cursor = (-1, -1)
        self._interface: WInterface = None
        self.state = 0

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.terminate()

    def pause(self, log=True):
        if log:
            self.log('Paused')
        while True:
            try:
                self._window.get_wch()
                break
            except _curses.error:
                pass

        if log:
            self.log('Resumed')

    def log(self, s, type_=0, delay=False):
        self.logger.log(s, type_)
        if delay:
            _time.sleep(0.4)

    def serve(self, cond: _Callable):
        c = _curses.KEY_RESIZE
        t = _time.time() + self.period

        def run():
            # mouse event
            if c == _curses.KEY_MOUSE:
                try:
                    _, x, y, _, state = _curses.getmouse()
                    if not self.interface.on_mouse(x, y, state):
                        _dist(self.mouse_lsnr, lambda l: l(x, y, state))

                except _curses.error:
                    pass

            # resize event
            elif c == _curses.KEY_RESIZE:
                y, x = self._window.getmaxyx()
                self.state = Window.STATE_LAYOUT
                self.interface.on_layout(x, y)
                self._window.clear()
                self.interface.on_canvas(self._canvas(0, 0))
                self.interface.on_draw()
                self.state = Window.STATE_SERVE

            # key event
            else:
                if not self.interface.on_key(c):
                    _dist(self.key_lsnr, lambda w: w(c))

        while True:
            if c != _constants.Key.ERR:

                # enter unify
                if c == '\r':
                    c = '\n'

                run()

            if not cond() or self.interface is None:
                break

            # _time check
            td = t - _time.time()
            if td <= 0:
                self.interface.on_refresh()
                t += self.period
                td += self.period
                while td <= 0:
                    self.log('Frame dropped!')
                    t += self.period
                    td += self.period

            timeout = _math.ceil(td * 1000)
            self._window.timeout(timeout)

            # cursor
            ym, xm = self._window.getmaxyx()
            xc, yc = self.cursor
            if 0 <= xc < xm and 0 <= yc < ym:
                _curses.curs_set(1)
                self._window.move(yc, xc)
            else:
                _curses.curs_set(0)

            try:
                c = self._window.get_wch()
            except _curses.error:
                c = _constants.Key.ERR

    def initialize(self):
        if Window.INSTANCE is not None:
            raise RuntimeError('Window already present.')

        Window.INSTANCE = self

        def init_color():
            for a in range(-1, 15):
                for b in range(-1, 15):
                    if a != -1 or b != -1:
                        _curses.init_pair(self._color(a, b), a, b)

        self._window = _curses.initscr()
        self._window.keypad(True)
        self._window.timeout(1000)
        _curses.noecho()
        _curses.cbreak()
        _curses.mouseinterval(1)
        _curses.mousemask(0 | _curses.BUTTON1_PRESSED | _curses.BUTTON1_RELEASED)
        _curses.curs_set(0)

        try:
            _curses.start_color()
            _curses.use_default_colors()
            init_color()
        except _curses.error:
            pass

    def terminate(self):
        Window.INSTANCE = None
        self._window.keypad(0)
        _curses.echo()
        _curses.nocbreak()
        _curses.curs_set(1)
        _curses.endwin()

    @staticmethod
    def _color(fg, bg):
        return (fg + 1) * 17 + bg + 1

    def _canvas(self, x_left_=0, y_top_=0, x_size_=0, y_size_=0, x_start_=0, y_start_=0):
        class Cvs(Canvas):
            # absolute position
            def __init__(self, x_left=0, y_top=0, x_size=0, y_size=0, x_start=0, y_start=0):
                self.x_left = x_left
                self.y_top = y_top
                y, x = Window.INSTANCE._window.getmaxyx()
                self.x_size = x - x_left if x_size == 0 else x_size
                self.y_size = y - y_top if y_size == 0 else y_size
                if x_left + x_size > x or y_top + y_size > y:
                    raise ValueError('Size exceeds.')
                self.x_start = x_start
                self.y_start = y_start

            def draw_str(
                    self, string: str, x_left: int = 0, y_top: int = 0,
                    wrap: bool = True, length=0,
                    attr=_constants.Attibute.NORMAL,
                    color_f: int = _constants.Color.DEFAULT,
                    color_b: int = _constants.Color.DEFAULT
            ):
                # handle backspace
                string = _pattern_backspace.sub('', string)
                if len(string) > 0 and string[0] == '\b':
                    string = string[1:]

                # get values
                at = attr | _curses.color_pair(Window.INSTANCE._color(color_f, color_b))
                y_draw = y_top + self.y_start + self.y_top
                x_draw = x_left + self.x_start + self.x_left
                length = length if length != 0 else self.x_size - x_left - self.x_start
                # split to lines
                strs = _wcwidth.split(string, -1 if not wrap else length)
                # cut to canvas size
                if x_draw < 0:
                    for i in range(len(strs)):
                        strs[i] = _wcwidth.slise(strs[i], -x_draw, self.x_size)
                else:
                    for i in range(len(strs)):
                        strs[i] = _wcwidth.slise(strs[i], 0, self.x_size - x_left - self.x_start)
                # move cursor after cutting
                x_draw = max(0, x_draw)
                # draw strings
                for i in strs:
                    if y_draw == self.y_size:
                        break
                    try:
                        Window.INSTANCE._window.addstr(y_draw, x_draw, i, at)
                    except _curses.error:
                        pass
                    y_draw += 1
                Window.INSTANCE._window.refresh()

            def draw_border(self):
                w = Window.INSTANCE._window.subwin(self.y_size, self.x_size, self.y_top, self.x_left)
                w.border()
                w.refresh()

            def cursor_set(self, x, y):
                Window.INSTANCE.cursor = self.x_left + self.x_start + x, self.y_top + self.y_start + y

            def cursor_unset(self):
                Window.INSTANCE.cursor = (-1, -1)

            # relative position
            def canvas(self, x_left, y_top, x_size, y_size, x_start, y_start):
                if x_left + x_size > self.x_size or y_top + y_size > self.y_size:
                    raise ValueError("Sub-panel boundary exceeds parent's.")
                return Cvs(
                    self.x_left + x_left + self.x_start, self.y_top + y_top + self.y_start,
                    x_size, y_size, x_start, y_start
                )

            def clear(self):
                w = Window.INSTANCE._window.subwin(self.y_size, self.x_size, self.y_top, self.x_left)
                w.clear()
                w.refresh()

        return Cvs(x_left_, y_top_, x_size_, y_size_, x_start_, y_start_)

    @property
    def xy_size(self):
        return self._window.getmaxyx()[::-1]

    @property
    def interface(self):
        return self._interface

    @interface.setter
    def interface(self, interface: 'WInterface'):
        self._interface = interface
        self._interface.on_window(self)
        if self.state == Window.STATE_SERVE:
            self._interface.on_layout(*self.xy_size)
            self._window.clear()
            self._interface.on_canvas(self._canvas(0, 0))
            self._interface.on_draw()


class WBoundary(Widget):
    def __init__(
            self, locator: _Callable = lambda x, y: (0, 0),
            sizer: _Callable = lambda x, y: (x, y)
    ):
        Widget.__init__(self, locator)
        self.x_size = self.y_size = 0
        self.sizer = sizer

    def on_layout(self, x, y):
        super().on_layout(x, y)
        self.x_size, self.y_size = [int(round(i)) for i in self.sizer(x, y)]

    def on_canvas(self, canvas: Canvas) -> None:
        super().on_canvas(canvas.canvas(0, 0, *self.xy_size, 0, 0))

    def encloses(self, x, y) -> bool:
        x_, y_ = self.xy_size
        return 0 <= x < x_ and 0 <= y < y_

    @property
    def xy_size(self) -> [int, int]:
        return self.x_size, self.y_size


class WContainer(WBoundary):
    def __init__(
            self, locator: _Callable = lambda x, y: (0, 0),
            sizer: _Callable = lambda x, y: (x, y)
    ):
        WBoundary.__init__(self, locator, sizer)
        self._widgets: [Widget] = []
        self._focus = None

    def widget_add(self, w: Widget):
        self._widgets.append(w)
        w.on_container(self)
        if Window.INSTANCE.state is not Window.STATE_INIT and self.x_left != -1 and self.y_top != -1:
            w.on_layout(*self.xy_size)
        if Window.INSTANCE.state is Window.STATE_SERVE and self.canvas is not None:
            w.on_canvas(self.canvas.canvas(0, 0, *self.xy_size, *w.xy_position))
            w.on_draw()

    def widget_remove(self, w: Widget):
        if self.focus is w:
            self.focus = None
            if self.focus is not None:
                raise RuntimeError('Window focus refuses to release.')
            self._widgets.remove(w)
            for i in self._widgets:
                self.focus = i
                if self.focus is i:
                    return
        else:
            self._widgets.remove(w)

        if self.canvas is not None and Window.INSTANCE.state is not Window.STATE_LAYOUT:
            self.canvas.clear()
            self.on_draw()

    def widget_clear(self):
        self._widgets.clear()
        self.focus = None
        if self.focus is not None:
            raise RuntimeError('Window focus refuses to release.')

        if self.canvas is not None and Window.INSTANCE.state is not Window.STATE_LAYOUT:
            self.canvas.clear()
            self.on_draw()

    def on_draw(self) -> None:
        _dist(self._widgets, _call(lambda w: w.on_draw()))

    def on_layout(self, x, y) -> None:
        super().on_layout(x, y)
        _dist(self._widgets, _call(lambda w: w.on_layout(x, y)))

    def on_mouse(self, x, y, state) -> bool:
        if super().encloses(x, y):
            def f(w: Widget):
                xw, yw = w.xy_position
                return w.on_mouse(x - xw, y - yw, state)

            if not _dist(self._widgets, f):
                self.focus = None
                return False
            else:
                return True
        else:
            return False

    def on_canvas(self, canvas: Canvas) -> None:
        super().on_canvas(canvas)
        _dist(self._widgets, _call(lambda w: w.on_canvas(
            canvas.canvas(0, 0, *self.xy_size, *w.xy_position)
        )))

    @property
    def xy_position(self) -> [int, int]:
        return self.x_left, self.y_top

    def on_key(self, ch) -> bool:
        return _dist(self._widgets, lambda w: w.on_key(ch))

    def on_refresh(self) -> None:
        _dist(self._widgets, _call(lambda w: w.on_refresh()))

    def on_container(self, container):
        super().on_container(container)
        for i in self._widgets:
            i.on_container(container)

    def log(self, s, type_=0, delay=False):
        self.container.log(s, type_, delay)

    def on_focused(self) -> bool:
        if self._focus is None:
            if len(self._widgets) == 0:
                return True
            else:
                for i in self._widgets:
                    self._focus = i
                    if i.on_focused():
                        return True
                    else:
                        self._focus = None
                return False
        else:
            return self._focus.on_focused()

    def on_unfocused(self, w: Widget) -> bool:
        if self._focus is None:
            return True
        else:
            return self._focus.on_unfocused(w)

    @property
    def focus(self) -> _Optional[Widget]:
        if self.container.focus is self:
            return self._focus
        else:
            return None

    @focus.setter
    def focus(self, w: _Optional[Widget]):
        if self._focus is w:
            return

        f = self._focus
        self._focus = w

        self.container.focus = self
        if self.container.focus is not self:
            self._focus = f
            return

        if f is not None:
            if not f.on_unfocused(w):
                self._focus = f
                return

        if w is not None:
            if not w.on_focused():
                self._focus = None

    def on_next(self) -> bool:
        start = -1 if self.focus is None else self._widgets.index(self.focus)
        if self.focus.on_next():
            return True
        else:
            for i in range(start + 1, len(self._widgets)):
                self._focus = self._widgets[i]
                if self._focus.on_focused():
                    return True
                else:
                    self._focus = None
            return False


class WInterface(WContainer):
    def __init__(self, parent: _Optional['WInterface']):
        WContainer.__init__(self, lambda a, b: (0, 0), lambda a, b: (a, b))
        self.window = None
        self.parent = parent
        self.cmd = {
            chr(127): self.op_back,
            '\t': self.on_next
        }

    def on_window(self, window):
        self.window = window

    def log(self, s, type_=0, delay=False):
        self.window.log(s, type_, delay)

    def op_back(self):
        self.window.interface = self.parent

    def op_next(self):
        if not self.on_next():
            self.on_next()

    def on_active(self):
        if self.canvas is not None:
            self.on_draw()

    def on_inactive(self):
        pass

    def on_key(self, ch) -> bool:
        if not super().on_key(ch):
            c = self.cmd.get(ch)
            if c is not None:
                c()
        else:
            return True

    @property
    def focus(self) -> _Optional[Widget]:
        return self._focus

    @focus.setter
    def focus(self, w: _Optional[Widget]):
        if self._focus is w:
            return

        f = self._focus
        self._focus = w

        if f is not None:
            if not f.on_unfocused(w):
                self._focus = f
                return

        if w is not None:
            if not w.on_focused():
                self._focus = None


class WLabel(Widget):
    def __init__(self, s='', locator: _Callable = lambda x, y: (0, 0)):
        Widget.__init__(self, locator)
        self.text = s

    def on_draw(self):
        self.canvas.draw_str(self.text)

    def set_str(self, s):
        if self.canvas is not None:
            self.canvas.draw_str(' ' * _wcwidth.width(self.text))
            self.text = s
            self.canvas.draw_str(s)


class WStatus(WLabel):
    def __init__(self):
        WLabel.__init__(self, '', lambda x, y: (0, y - 1))


class WButton(WBoundary):
    def __init__(
            self, text, width=1, auto=True, keys=None,
            exe: _Callable = lambda: (), locator: _Callable = lambda x, y, w: (0, 0),
            color_normal_f=_constants.Color.DEFAULT, color_normal_b=_constants.Color.DEFAULT,
            color_focused_f=_constants.Color.CYAN, color_focused_b=_constants.Color.DEFAULT
    ):
        WBoundary.__init__(self, lambda x, y: locator(x, y, self.pos_x))
        self.text = text
        self.exe = exe
        self.keys = keys if keys is not None else []
        self.width = width
        self.auto = auto
        self.cnf = color_normal_f
        self.cnb = color_normal_b
        self.cff = color_focused_f
        self.cfb = color_focused_b
        self.pos_x = width if not auto else 2 * width + _wcwidth.width(text)

    def on_focused(self) -> bool:
        if self.canvas is not None:
            self.on_draw()
        return True

    def on_unfocused(self, w) -> bool:
        self.on_draw()
        return True

    def on_key(self, ch):
        if ch in self.keys:
            self.exe()
            return True
        if self is self.container.focus and ch == '\n':
            self.exe()
            return True

    def on_mouse(self, x, y, state):
        if super().encloses(x, y):
            if state == _constants.Button.B1_PRESSED:
                self.container.focus = self
                return True
            elif state == _constants.Button.B1_RELEASED and self.container.focus is self:
                self.exe()
                return True
        return False

    def on_draw(self):
        if self.container.focus is self:
            cf = self.cff
            cb = self.cfb
        else:
            cf = self.cnf
            cb = self.cnb

        if self.auto:
            s = (self.width * ' ') + self.text + (self.width * ' ')
            self.canvas.draw_str(s, color_f=cf, color_b=cb, wrap=False)
        else:
            self.canvas.draw_str(self.width * ' ', color_f=cf, color_b=cb)
            self.canvas.draw_str(self.text, color_f=cf, color_b=cb)

    @property
    def xy_size(self) -> [int, int]:
        return self.pos_x, 1


class WText(WBoundary):
    def _inv(self):
        if self.container.focus is self:
            self.inv = not self.inv
            self.on_draw()

    def __init__(
            self, secret=False,
            locator: _Callable = lambda x, y: (0, 0), sizer: _Callable = lambda x, y: (x, y),
            color_normal_f=_constants.Color.DEFAULT, color_normal_b=_constants.Color.DEFAULT,
            color_focused_f=_constants.Color.DEFAULT, color_focused_b=_constants.Color.DEFAULT,
    ):
        super().__init__(locator, sizer)
        self.secret = secret
        self.cursor = (0, 0)
        self.pos = (0, 0)
        self.lines: [str] = ['']
        self.inv = True
        self.Timer = Timer(500, self._inv)
        self.cnf = color_normal_f
        self.cnb = color_normal_b
        self.cff = color_focused_f
        self.cfb = color_focused_b
        self.cmd = {
            chr(127): self.op_backspace,
            '\n': self.op_enter,
            _constants.Key.UP: self.op_cursor_up,
            _constants.Key.DOWN: self.op_cursor_down,
            _constants.Key.LEFT: self.op_cursor_left,
            _constants.Key.RIGHT: self.op_cursor_right
        }

    def on_mouse(self, x, y, state):
        if super().encloses(x, y):
            if state == _constants.Button.B1_PRESSED:
                self.cursor = self._get_cursor_at(x, y)
                self._cursor_refresh()
                self.container.focus = self
            return True
        return False

    def on_refresh(self) -> None:
        self.Timer.trigger()

    def _get_index(self, x, y):
        s = self.lines[y]
        csr, _ = _wcwidth.index(s, x, True)
        csr = csr if csr != -1 else len(s)
        return csr, y

    def _get_char_at(self, x, y):
        s = self.lines[y]
        if x == len(s):
            return ' '
        else:
            return s[x]

    def on_draw(self) -> None:
        self.canvas.clear()

        for i in range(self.pos[1], min(self.pos[1] + self.xy_size[1], len(self.lines))):
            s = self.lines[i]
            self.canvas.draw_str(s, x_left=-self.pos[0], y_top=i - self.pos[1], wrap=False)

        if self is self.container.focus:
            xp, yp = self.pos
            xc, yc = self.cursor
            self.canvas.cursor_set(min(_wcwidth.width(self.lines[yc]), xc) - xp, yc - yp)
        else:
            self.canvas.cursor_unset()

    def on_key(self, ch) -> bool:
        if self is self.container.focus:
            cmd = self.cmd.get(ch)
            if cmd is not None:
                cmd()
                self._cursor_refresh()
                return True
            elif isinstance(ch, str):
                if _ascii.isascii(ch):
                    if _ascii.isprint(ch):
                        self.add_char(ch)
                        self._cursor_refresh()
                        return True
                else:
                    self.add_char(ch)
                    self._cursor_refresh()
                    return True
        return False

    def on_unfocused(self, w) -> bool:
        self.on_draw()
        return True

    def on_focused(self) -> bool:
        self._cursor_refresh()
        return True

    def add_char(self, ch):
        x, y = self.cursor
        x_, y_ = self._get_index(*self.cursor)
        s = self.lines[y]
        self.cursor = (_wcwidth.width(s[:x_] + ch), y_)
        self.lines[y] = s[:x_] + ch + s[x_:]

    def _get_cursor_at(self, x, y):
        xp, yp = self.pos
        return x + xp, min(len(self.lines) - 1, y + yp)

    def _cursor_refresh(self):
        self.inv = True
        self._pos_move_no_trailing()
        self._pos_move_show_cursor()
        self.on_draw()
        self.Timer.reset()

    def _pos_move_show_cursor(self):
        x, y = self.cursor
        w = _wcwidth.width(self._get_char_at(*self._get_index(x, y)))
        xl, yt = self.pos
        xr = xl + self.x_size
        yb = yt + self.y_size

        if x < xl:
            self.pos = (x, self.pos[1])
        elif x >= xr:
            x += w - 1
            self.pos = (x - self.x_size + 1, self.pos[1])

        if y < yt:
            self.pos = (self.pos[0], y)
        elif y >= yb:
            self.pos = (self.pos[0], y - self.y_size + 1)

    def _pos_move_no_trailing(self):
        xl, yt = self.pos
        xr = xl + self.x_size
        yb = yt + self.y_size
        x_max = 0

        for i in range(len(self.lines)):
            x_max = max(x_max, _wcwidth.width(self.lines[i]) + (0 if self.cursor[1] != i else 1))

        if yb > len(self.lines):
            yt = max(0, len(self.lines) - self.y_size)

        if xr > x_max:
            xl = max(0, x_max - self.x_size)

        self.pos = (xl, yt)

    def op_backspace(self):
        x, y = self.cursor
        s = self.lines[y]
        if x != 0:
            l = _wcwidth.width(s)
            if x >= l:
                self.lines[y] = s[:-1]
                self.cursor = (l - _wcwidth.width(s[-1]), y)
            else:
                x_, y_ = self._get_index(x, y)
                self.cursor = (x - _wcwidth.width(self._get_char_at(x_ - 1, y_)), y)
                self.lines[y] = s[:x_ - 1] + s[x_:]
        else:
            if y != 0:
                self.cursor = (_wcwidth.width(self.lines[y - 1]), y - 1)
                self.lines[y - 1] += self.lines[y]
                self.lines.pop(y)

    def op_enter(self):
        x_, y_ = self._get_index(*self.cursor)
        s = self.lines[y_]
        self.lines[y_] = s[:x_]
        self.lines.insert(y_ + 1, s[x_:])
        self.cursor = (0, y_ + 1)

    def op_cursor_up(self):
        x, y = self.cursor
        if y != 0:
            self.cursor = (x, y - 1)
        else:
            self.cursor = (0, 0)

    def op_cursor_down(self):
        x, y = self.cursor
        if y != len(self.lines) - 1:
            self.cursor = (x, y + 1)
        else:
            self.cursor = (_wcwidth.width(self.lines[-1]), y)

    def op_cursor_left(self):
        x, y = self.cursor
        l = _wcwidth.width(self.lines[y])
        x_, y_ = self._get_index(x, y)
        w = _wcwidth.width(self._get_char_at(x_ - 1, y_))

        if x == 0:
            if y != 0:
                self.cursor = (len(self.lines[y - 1]), y - 1)
        elif x >= l:
            self.cursor = (l - w, y)
        else:
            self.cursor = (x - w, y)

    def op_cursor_right(self):
        x, y = self.cursor
        l = _wcwidth.width(self.lines[y])

        if x >= l:
            if y != len(self.lines) - 1:
                self.cursor = (0, y + 1)
        else:
            self.cursor = (x + _wcwidth.width(self._get_char_at(*self._get_index(*self.cursor))), y)


class WDebug(Widget):
    def on_key(self, ch) -> bool:
        s = 'Key pressed: {:s}'.format(str(ch))
        if isinstance(ch, str) and len(ch) == 1:
            s += ', ord: {:d}'.format(ord(ch))

        self.container.log(s)
        return False

    def on_mouse(self, x, y, state):
        self.container.log('Mouse: ({:d}, {:d}), {:d}'.format(x, y, state))
        return False


class WWrapper(WContainer):
    def on_container(self, container):
        WBoundary.on_container(self, container)
        self.widget.on_container(self)

    def on_focused(self) -> bool:
        return self.widget.on_focused()

    def on_unfocused(self, w: 'Widget') -> bool:
        return self.widget.on_unfocused(w)

    def encloses(self, x, y) -> bool:
        return WBoundary.encloses(self, x, y)

    def on_mouse(self, x, y, state) -> bool:
        return self.widget.on_mouse(x, y, state)

    def on_canvas(self, canvas: Canvas) -> None:
        WBoundary.on_canvas(self, canvas)
        self.widget.on_canvas(self.canvas.canvas(
            self.bl, self.bt, self.x_size - self.bl - self.bt, self.y_size - self.bt - self.bb, 0, 0
        ))

    def on_draw(self) -> None:
        self.widget.on_draw()
        self.painter(self.canvas)

    def on_refresh(self) -> None:
        self.widget.on_refresh()

    def on_layout(self, x, y):
        WBoundary.on_layout(self, x, y)
        self.widget.on_layout(self.x_size - self.bl - self.br, self.y_size - self.bt - self.bb)

    def on_next(self) -> bool:
        return self.widget.on_next()

    def on_key(self, ch) -> bool:
        return self.widget.on_key(ch)

    def __init__(
            self, widget,
            locator: _Callable = lambda x, y: (0, 0),
            sizer_w: _Callable = lambda x, y: (x, y),
            sizer_b: _Callable = lambda x, y: (0, 0, 0, 0),
            painter: _Callable = lambda p: True
    ):
        WBoundary.__init__(self, locator, sizer_w)
        self.sizer_b = sizer_b
        self._widget = widget
        self.painter = painter
        self.bl = self.br = self.bt = self.bb = 0

    @property
    def focus(self) -> _Optional[Widget]:
        if self is self.container.focus:
            return self.widget
        else:
            return None

    @focus.setter
    def focus(self, w):
        if w is not self.widget and Window.INSTANCE is not None:
            Window.INSTANCE.log("Do you really want to call this? I'm a wrapper.")

    @property
    def widget(self):
        return self._widget

    @widget.setter
    def widget(self, widget):
        w = self._widget
        self._widget = widget
        if self.container is not None and (self is self.container.focus and not w.on_unfocused(widget)):
            raise RuntimeError('Widget refuses to release focus.')

        if Window.INSTANCE.state != Window.STATE_INIT:
            self._widget.on_layout(*self.xy_size)
        if Window.INSTANCE.state == Window.STATE_SERVE:
            if self.canvas is None:
                raise RuntimeError('The WWrapper don\'t have canvas. Maybe it\'s not correctly added.')

            c = self.canvas.canvas(
                self.bl, self.bt, self.x_size - self.bl - self.bt, self.y_size - self.bt - self.bb, 0, 0
            )
            c.clear()
            self._widget.on_canvas(c)
            self._widget.on_draw()
            if self is self.container.focus:
                self._widget.on_focused()

    def widget_clear(self):
        Window.INSTANCE.log("Do you really want to call this? I'm a wrapper.")

    def widget_add(self, w: Widget):
        Window.INSTANCE.log("Do you really want to call this? I'm a wrapper.")

    def widget_remove(self, w: Widget):
        Window.INSTANCE.log("Do you really want to call this? I'm a wrapper.")


class WSelect(WWrapper):
    def __init__(self, locator, sizer, items: _typing.List[_typing.Tuple[str, _Callable]] = None):
        WWrapper.__init__(self, WContainer(), locator, sizer)
        self.items = items if items is not None else []
        self.index = 0
        self.list = []

    def on_layout(self, x, y) -> None:
        super().on_layout(x, y)
        self._arrange()

    def _arrange(self):
        x, y = self.xy_size
        index = self.list.index(self.widget.focus) if self.widget.focus is not None else 0
        self.widget.widget_clear()
        self.list.clear()
        for i in range(self.index, min(len(self.items), self.index + y)):
            b = WButton(text=self.items[i][0], auto=False, width=x, exe=self.items[i][1],
                        locator=lambda x_, y_: (0, i - self.index))
            self.widget.widget_add(b)
            self.list.append(b)
        self.widget.focus = self.list[min(len(self.list) - 1, index)]

    def on_key(self, ch) -> bool:
        if super().on_key(ch):
            return True

        if self.container.focus is self:
            if ch == _constants.Key.UP:
                index = self.list.index(self.widget.focus)
                if index == 0:
                    if self.index > 0:
                        self.index -= 1
                        self._arrange()
                        self.widget.focus = self.list[index]
                        self.canvas.clear()
                        self.on_draw()
                        return True
                    else:
                        self.index = len(self.items) - self.y_size
                        self._arrange()
                        self.widget.focus = self.list[-1]
                        self.canvas.clear()
                        self.on_draw()
                        return True
                else:
                    self.widget.focus = self.list[index - 1]
                    return True
            elif ch == _constants.Key.DOWN:
                index = self.list.index(self.widget.focus)
                if index == self.y_size - 1:
                    if self.index + self.y_size < len(self.items):
                        self.index += 1
                        self._arrange()
                        self.widget.focus = self.list[index]
                        self.canvas.clear()
                        self.on_draw()
                        return True
                    else:
                        self.index = 0
                        self._arrange()
                        self.widget.focus = self.list[0]
                        self.canvas.clear()
                        self.on_draw()
                        return True
                else:
                    self.widget.focus = self.list[index - len(self.list) + 1]
                    return True
            else:
                return False
        else:
            return False


class WPager(WWrapper):
    # getter = callable: page (int) -> content (widget)
    def __init__(
            self, getter: _Callable, page=0, size=-1, buffered=True,
            locator: _Callable = lambda x, y: (0, 0),
            sizer: _Callable = lambda x, y: (x, y)
    ):
        super().__init__(Widget(), locator, sizer)
        self.getter = getter
        self.page = page
        self.size = size
        self._buffered = buffered
        self.buffer = {}
        self.page_set(page)

    def page_set(self, n):
        self._range_check(n)
        self.page = n
        if self.buffered:
            w = self.buffer.get(n)
            if w is not None:
                self.widget = w
            else:
                self.buffer[n] = self.getter(n)
                self.widget = self.buffer[n]
        else:
            self.widget = self.getter(n)

    def page_prev(self):
        self.page_set(self.page - 1)

    def page_next(self):
        self.page_set(self.page + 1)

    def page_has_prev(self):
        return self.page > 0

    def page_has_next(self):
        return self.page + 1 < self.size

    def _range_check(self, n):
        if self.size == -1:
            return
        if not 0 <= n < self.size:
            raise ValueError('Index exceeds boundary.')

    @property
    def buffered(self):
        return self._buffered

    @buffered.setter
    def buffered(self, b):
        if not b:
            self.buffer.clear()
        self._buffered = b
