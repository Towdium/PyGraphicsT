import curses
import curses.ascii as ascii
import math
import time
import typing
from typing import Callable as _Callable

import pygraphicst.constants as constants
import pygraphicst.wcwidth as wcwidth

N = typing.TypeVar('N', int, float)


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
        self.next = time.time() + self.frequency
        self.exe = exe

    def trigger(self):
        t = time.time()
        if t >= self.next:
            self.exe()
            while self.next <= t:
                self.next += self.frequency

    def reset(self):
        self.next = time.time() + self.frequency


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
            attr=constants.Attibute.NORMAL,
            color_f: int = constants.Color.DEFAULT,
            color_b: int = constants.Color.DEFAULT
    ):
        pass

    def draw_border(self):
        pass

    def clear(self):
        pass

    def canvas(self, x_left, y_top, x_size, y_size, x_start, y_start) -> 'Canvas':
        pass

    @property
    def xy_position(self) -> typing.Tuple[int, int]:
        return 0, 0


class Widget:
    def __init__(self, locator: _Callable = lambda x, y: (0, 0)):
        self.canvas = None
        self.locator = locator
        self.x_left = self.y_top = 0
        self.window = None

    def on_refresh(self) -> None:
        pass

    def on_key(self, ch) -> bool:
        return False

    def on_mouse(self, x, y, state) -> None:
        pass

    def on_canvas(self, canvas: Canvas) -> None:
        self.canvas = canvas

    def on_layout(self, x, y) -> None:
        self.x_left, self.y_top = [int(round(i)) for i in self.locator(x, y)]

    def on_draw(self) -> None:
        pass

    def on_focused(self) -> bool:
        return False

    def on_unfocused(self, w: 'Widget') -> bool:
        return False

    def on_window(self, window):
        self.window = window

    @property
    def xy_position(self) -> [int, int]:
        return self.x_left, self.y_top


class Window:
    INSTANCE: 'Window' = None

    def __init__(self, logger: _Callable = lambda s: ()):
        self._window = None
        self._line = None
        self._widgets: [Widget] = []
        self.key_lsnr: [_Callable] = []
        self.mouse_lsnr = []
        self.logger = Logger(logger)
        self.dirty = False
        self._focus: Widget = None
        self._cursor_ = (-1, -1)
        self.period = 0.02

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
            except curses.error:
                pass

        if log:
            self.log('Resumed')

    def add_widget(self, w: Widget):
        self._widgets.append(w)
        w.on_window(self)
        self.dirty = True

    def log(self, s, type_=0, delay=False):
        self.logger.log(s, type_)
        if delay:
            time.sleep(0.4)

    def serve(self, cond: _Callable):
        c = curses.KEY_RESIZE
        t = time.time() + self.period

        def run():
            # mouse event
            if c == curses.KEY_MOUSE:
                try:
                    _, x, y, _, state = curses.getmouse()

                    def f(w: Widget):
                        xw, yw = w.xy_position
                        w.on_mouse(x - xw, y - yw, state)
                        return True

                    _dist(self._widgets, f)
                    _dist(self.mouse_lsnr, lambda l: l(x, y, state))

                except curses.error:
                    pass

            # resize event
            elif c == curses.KEY_RESIZE:
                self._window.clear()
                y, x = self._window.getmaxyx()
                _dist(self._widgets, _call(lambda w: w.on_layout(x, y)))
                _dist(self._widgets, _call(lambda w: w.on_canvas(self._canvas(*w.xy_position))))
                _dist(self._widgets, _call(lambda w: w.on_draw()))

            # key event
            else:
                if not _dist(self._widgets, lambda w: w.on_key(c)):
                    _dist(self.key_lsnr, lambda w: w(c))

        while True:
            self.dirty = False

            if c != constants.Key.ERR:

                # enter unify
                if c == '\r':
                    c = '\n'

                run()

                if self.dirty:
                    c = curses.KEY_RESIZE
                    continue

            if not cond():
                break

            # time check
            td = t - time.time()
            if td <= 0:
                _dist(self._widgets, lambda w: w.on_refresh())
                t += self.period
                td += self.period
                while td <= 0:
                    self.log('Frame dropped!')
                    t += self.period
                    td += self.period

            timeout = math.ceil(td * 1000)
            self._window.timeout(timeout)

            try:
                c = self._window.get_wch()
            except curses.error:
                c = constants.Key.ERR

    def initialize(self):
        if Window.INSTANCE is not None:
            raise RuntimeError('Window already present.')

        Window.INSTANCE = self

        def init_color():
            for a in range(-1, 15):
                for b in range(-1, 15):
                    if a != -1 or b != -1:
                        curses.init_pair(self._color(a, b), a, b)

        self._window = curses.initscr()
        self._window.keypad(True)
        self._window.timeout(1000)
        curses.noecho()
        curses.cbreak()
        curses.mouseinterval(1)
        curses.mousemask(0 | curses.BUTTON1_PRESSED | curses.BUTTON1_RELEASED)
        curses.curs_set(0)

        try:
            curses.start_color()
            curses.use_default_colors()
            init_color()
        except curses.error:
            pass

    def terminate(self):
        Window.INSTANCE = None
        self._window.keypad(0)
        curses.echo()
        curses.nocbreak()
        curses.curs_set(1)
        curses.endwin()

    @staticmethod
    def _color(fg, bg):
        return (fg + 1) * 17 + bg + 1

    def _canvas(self, x_left_=0, y_top_=0, x_size_=0, y_size_=0, x_start_=0, y_start_=0):
        class Cvs(Canvas):
            # absolute position
            def __init__(self, window: 'Window', x_left=0, y_top=0, x_size=0, y_size=0, x_start=0, y_start=0):
                self._window = window
                self.x_left = x_left
                self.y_top = y_top
                self._temp = window._window.subwin(y_top, x_left)
                y, x = self._temp.getmaxyx()
                self.x_size = x if x_size == 0 else x_size
                self.y_size = y if y_size == 0 else y_size
                try:
                    self._temp.resize(self.y_size, self.x_size)
                except curses.error:
                    raise ValueError('Size exceeds.')
                self.x_start = x_start
                self.y_start = y_start
                self.cursor = (0, 0)

            def draw_str(
                    self, string: str, x_left: int = 0, y_top: int = 0,
                    wrap: bool = True, length=0,
                    attr=constants.Attibute.NORMAL,
                    color_f: int = constants.Color.DEFAULT,
                    color_b: int = constants.Color.DEFAULT
            ):
                # get values
                at = attr | curses.color_pair(self._window._color(color_f, color_b))
                y_draw = y_top + self.y_start
                x_draw = x_left + self.x_start
                length = length if length != 0 else self.x_size - x_draw
                # split to lines
                strs = wcwidth.split(string, -1 if not wrap else length)
                # cut to canvas size
                if x_draw < 0:
                    for i in range(len(strs)):
                        strs[i] = wcwidth.slise(strs[i], -x_draw, self.x_size)
                else:
                    for i in range(len(strs)):
                        strs[i] = wcwidth.slise(strs[i], 0, self.x_size - x_draw)
                # move cursor after cutting
                x_draw = max(0, x_draw)
                # draw strings
                self._temp.resize(self.y_size, self.x_size)
                for i in strs:
                    if y_draw == self.y_size:
                        self._temp.refresh()
                        break

                    self._temp.addstr(y_draw, x_draw, i, at)
                    y_draw += 1

            def draw_border(self):
                self._temp.resize(self.y_size, self.x_size)
                self._temp.border()
                self._temp.refresh()

            # relative position
            def canvas(self, x_left, y_top, x_size, y_size, x_start, y_start):
                return Cvs(self._window, self.x_left + x_left, self.y_top + y_top, x_size, y_size, x_start, y_start)

            def clear(self):
                self._temp.resize(self.y_size, self.x_size)
                self._temp.clear()
                self._temp.refresh()

            @property
            def xy_position(self):
                return self.cursor

        return Cvs(self, x_left_, y_top_, x_size_, y_size_, x_start_, y_start_)

    @property
    def focus(self) -> Widget:
        return self._focus

    @focus.setter
    def focus(self, w: Widget or None):
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

    @property
    def xy_size(self):
        return self._window.getmaxyx()[::-1]


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

    def add_widget(self, w: Widget):
        self._widgets.append(w)
        if self.window is not None:
            w.on_window(self.window)
            self.window.dirty = True

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

            return _dist(self._widgets, f)
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

    def on_key(self, ch: int) -> bool:
        return _dist(self._widgets, lambda w: w.on_key(ch))

    def on_refresh(self) -> None:
        _dist(self._widgets, _call(lambda w: w.on_refresh()))

    def on_window(self, window):
        super().on_window(window)
        for i in self._widgets:
            i.on_window(window)


class WLabel(Widget):
    def __init__(self, s='', locator: _Callable = lambda x, y: (0, 0)):
        Widget.__init__(self, locator)
        self.text = s
        self.len = 0

    def on_draw(self):
        x1, _ = self.canvas.xy_position
        self.canvas.draw_str(self.text, x_left=10, y_top=5, color_f=constants.Color.WEAK_GREEN)
        x2, _ = self.canvas.xy_position
        self.len = x2 - x1
        self.window.log('draw')

    def set_str(self, s):
        self.text = s
        if self.canvas is not None:
            self.canvas.draw_str(' ' * self.len)
            self.canvas.draw_str(s)


class WStatus(WLabel):
    def __init__(self):
        WLabel.__init__(self, '', lambda x, y: (0, y - 1))


class WButton(WBoundary):
    def __init__(
            self, text, width=1, auto=True, keys=None,
            exe: _Callable = lambda: (), locator: _Callable = lambda x, y: (0, 0),
            color_normal_f=constants.Color.DEFAULT, color_normal_b=constants.Color.DEFAULT,
            color_focused_f=constants.Color.CYAN, color_focused_b=constants.Color.DEFAULT
    ):
        WBoundary.__init__(self, locator)
        self.text = text
        self.exe = exe
        self.keys = keys if keys is not None else []
        self.width = width
        self.auto = auto
        self.cnf = color_normal_f
        self.cnb = color_normal_b
        self.cff = color_focused_f
        self.cfb = color_focused_b
        self.pos_x = 0

    def on_focused(self) -> bool:
        self.on_draw()
        return True

    def on_unfocused(self, w) -> bool:
        self.on_draw()
        return True

    def on_key(self, ch):
        if ch in self.keys:
            self.exe()
            return True

    def on_mouse(self, x, y, state):
        if super().encloses(x, y):
            if state == constants.Button.B1_PRESSED:
                self.window.focus = self
            elif state == constants.Button.B1_RELEASED and self.window.focus is self:
                self.exe()
                self.window.focus = None

    def on_draw(self):
        if self.window.focus is self:
            cf = self.cff
            cb = self.cfb
        else:
            cf = self.cnf
            cb = self.cnb

        if self.auto:
            s = (self.width * ' ') + self.text + (self.width * ' ')
            f = not self.canvas.draw_str(s, color_f=cf, color_b=cb, wrap=False)
            self.pos_x = self.canvas.xy_position[0] - f
        else:
            f = not self.canvas.draw_str(self.width * ' ', color_f=cf, color_b=cb)
            self.pos_x = self.canvas.xy_position[0] - f
            self.canvas.draw_str(self.text, color_f=cf, color_b=cb)

    @property
    def xy_size(self) -> [int, int]:
        return self.pos_x, 1


class WText(WBoundary):
    def _inv(self):
        if self.window.focus is self:
            self.inv = not self.inv
            self.on_draw()

    def __init__(
            self, secret=False,
            locator: _Callable = lambda x, y: (0, 0), sizer: _Callable = lambda x, y: (x, y),
            color_normal_f=constants.Color.DEFAULT, color_normal_b=constants.Color.DEFAULT,
            color_focused_f=constants.Color.DEFAULT, color_focused_b=constants.Color.DEFAULT,
    ):
        super().__init__(locator, sizer)
        self.secret = secret
        self.cursor = (0, 0)
        self.pos = (0, 0)
        self.lines: [str] = ['']
        self.inv = True
        self.timer = Timer(500, self._inv)
        self.cnf = color_normal_f
        self.cnb = color_normal_b
        self.cff = color_focused_f
        self.cfb = color_focused_b

    def on_mouse(self, x, y, state):
        if super().encloses(x, y):
            if state == constants.Button.B1_PRESSED:
                self.window.focus = self
        else:
            if self.window.focus is self:
                self.window.focus = None

    def on_refresh(self) -> None:
        self.timer.trigger()

    def on_draw(self) -> None:
        self.canvas.clear()

        for i in range(self.pos[1], self.pos[1] + self.xy_size[1]):
            if i >= len(self.lines):
                break

            s = self.lines[i]
            if self.cursor[1] == i:
                csr = self.cursor[0]
                inv = self.inv and self.window.focus is self
                att = constants.Attibute.REVERSE if inv else constants.Attibute.NORMAL  # TODO selection
                self.canvas.draw_str(s[:csr], x_left=-self.pos[0], y_top=i - self.pos[1], wrap=False)
                self.canvas.draw_str(s[csr] if csr < len(s) else ' ', attr=att, absolute=False, wrap=False)
                self.canvas.draw_str(s[csr + 1:] if csr < len(s) else '', absolute=False, wrap=False)
            else:
                self.canvas.draw_str(s, x_left=-self.pos[0], y_top=i - self.pos[1], wrap=False)

    def on_key(self, ch) -> bool:
        if self.window.focus is self:
            if isinstance(ch, str):
                if ascii.isascii(ch):
                    if ascii.isprint(ch):
                        self.add_char(ch)
                        self._cursor_refresh()
                        return True
                    else:
                        if self._cmd_char(ch):
                            self._cursor_refresh()
                            return True
                        else:
                            return False
                else:
                    self.add_char(ch)
                    return True
            else:
                if self._cmd_int(ch):
                    self._cursor_refresh()
                    return True
                else:
                    return False

    def on_unfocused(self, w) -> bool:
        self.on_draw()
        return True

    def on_focused(self) -> bool:
        self._cursor_refresh()
        return True

    def add_char(self, ch):
        s = self.lines[self.cursor[1]]
        self.lines[self.cursor[1]] = s[:self.cursor[0]] + ch + s[self.cursor[0]:]
        self.cursor = (self.cursor[0] + 1, self.cursor[1])

    def _cursor_refresh(self):
        self.inv = True
        self._pos_move_no_trailing()
        self._pos_move_show_cursor()
        self.on_draw()
        self.timer.reset()

    def _pos_move_show_cursor(self):
        x, y = self.cursor
        xl, yt = self.pos
        xr = xl + self.x_size
        yb = yt + self.y_size

        if x < xl:
            self.pos = (x, self.pos[1])
        elif x >= xr:
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

        for i in self.lines:
            x_max = max(x_max, len(i))

        if yb > len(self.lines):
            yt = max(0, len(self.lines) - self.y_size)

        if xr > x_max:
            xl = max(0, x_max - self.x_size)

        self.pos = (xl, yt)

    def _cmd_char(self, ch) -> bool:
        x, y = self.cursor

        if ch == chr(127):
            s = self.lines[y]
            if len(s) != 0:
                if x >= len(s):
                    self.lines[y] = s[:-1]
                    self.cursor = (len(s) - 1, y)
                    return True
                else:
                    self.lines[y] = s[:x - 1] + s[x:]
                    self.cursor = (x - 1, y)
                    return True
            else:
                if y != 0:
                    self.cursor = (len(self.lines[y - 1]), y - 1)
                    self.lines[y - 1] += self.lines[y]
                    self.lines.pop(y)
                    return True
        elif ch == '\n':
            s = self.lines[y]
            self.lines[y] = s[:x]
            self.lines.insert(y + 1, s[x:])
            self.cursor = (0, y + 1)
            return True

        return False

    def _cmd_int(self, i) -> bool:
        x, y = self.cursor
        l = len(self.lines[y])

        if i == constants.Key.UP:
            if y != 0:
                self.cursor = (x, y - 1)
                return True
            else:
                self.cursor = (0, 0)
                return True
        elif i == constants.Key.DOWN:
            if y != len(self.lines) - 1:
                self.cursor = (x, y + 1)
                return True
            else:
                self.cursor = (len(self.lines[-1]), y)
                return True
        elif i == constants.Key.LEFT:
            if x == 0:
                if y != 0:
                    self.cursor = (len(self.lines[y - 1]), y - 1)
                    return True
            elif x >= l:
                self.cursor = (l - 1, y)
                return True
            else:
                self.cursor = (x - 1, y)
                return True
        elif i == constants.Key.RIGHT:
            if x >= l:
                if y != len(self.lines) - 1:
                    self.cursor = (0, y + 1)
                    return True
            else:
                self.cursor = (x + 1, y)
                return True

        return False


class WDebug(Widget):
    def on_key(self, ch) -> bool:
        s = 'Key pressed: {:s}'.format(str(ch))
        if isinstance(ch, str) and len(ch) == 1:
            s += ', ord: {:d}'.format(ord(ch))

        self.window.log(s)
        return False

    def on_mouse(self, x, y, state):
        self.window.log('Mouse: ({:d}, {:d}), {:d}'.format(x, y, state))


class WCBordered(WContainer):
    def __init__(
            self, locator: _Callable = lambda x, y: (0, 0),
            sizer_widget: _Callable = lambda x, y: (x, y),
            sizer_border: _Callable = lambda x, y: (1, 1, 1, 1),
            painter: _Callable = lambda c, x, y: c.draw_border()
    ):
        super().__init__(locator, sizer_widget)
        self.sizer_b = sizer_border
        self.b_top = self.b_right = self.b_bottom = self.b_left = 0
        self.painter = painter

    def on_layout(self, x, y) -> None:
        super().on_layout(x, y)
        self.b_top, self.b_right, self.b_bottom, self.b_left = self.sizer_b(x, y)

    def on_canvas(self, canvas: Canvas) -> None:
        Widget.on_canvas(self, canvas.canvas(0, 0, *self.xy_size, 0, 0))
        x, y = self.xy_size
        xs = x - self.b_left - self.b_right
        ys = y - self.b_top - self.b_bottom

        _dist(self._widgets, _call(lambda w: w.on_canvas(
            canvas.canvas(self.b_left, self.b_top, xs, ys, *w.xy_position)
        )))

    def on_draw(self) -> None:
        self.canvas.clear()
        self.painter(self.canvas, *self.xy_size)
        super().on_draw()
