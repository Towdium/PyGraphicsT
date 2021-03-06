import curses

import pygraphicst as gpx


def f3():
    with gpx.Window(lambda a, b: ()) as w:
        w.pause()
        f = [True]
        i = gpx.WInterface(None)
        w.interface = i

        # noinspection PyDefaultArgument
        def get(n, w=gpx.WLabel('')):
            w.set_str(str(n))
            return w

        wp = gpx.WPager(get, sizer=lambda x, y: (0, 5), buffered=False)
        i.widget_add(gpx.WButton('>', locator=lambda x, y, w: (x - 2 - w, y - 2), exe=lambda: wp.page_next()))
        i.widget_add(gpx.WButton('<', locator=lambda x, y, w: (2, y - 2), exe=lambda: wp.page_prev()))
        i.widget_add(wp)

        def lsnr(ch): f[0] = ch != '\n'

        w.key_lsnr.append(lsnr)
        w.serve(lambda: f[0])


def f1():
    class WClick(gpx.Widget):
        def on_mouse(self, x, y, state) -> bool:
            curses.beep()
            self.canvas.draw_str('0', x, y, color_f=gpx.constants.Color.WEAK_GREEN)
            return True

    class Wm(gpx.Widget):
        def on_draw(self):
            self.canvas.draw_str('黑龙江凯撒酱立刻到工具栏；可视角度复合控件；口脚镣手铐甲胺磷；圣诞节风口浪尖撒离开家岛风', x_left=10, y_top=5,
                                 color_f=gpx.constants.Color.WEAK_GREEN)

    class WDButton(gpx.WButton):
        def __init__(self, locator, text, exe):
            gpx.WButton.__init__(self, text, exe=exe, locator=locator, color_normal_b=gpx.constants.Color.YELLOW)

    class WTest(gpx.Widget):
        def on_draw(self) -> None:
            self.canvas.draw_str('啊黄浦', x_left=-2, wrap=False)
            self.canvas.draw_str('黑龙江凯撒酱立刻到工具栏；可视角度复合控件；口脚镣手铐甲胺磷；圣诞节风口浪尖撒离开家岛风', length=6, x_left=-1, wrap=True)

    f = [True]
    ws = gpx.WStatus()
    with gpx.Window(lambda s, t: ws.set_str(s)) as w:
        def lsnr(c): f[0] = c != '\n'

        w.key_lsnr.append(lsnr)
        w.pause()
        # w.add_widget(b)
        # b.add_widget(WTest())
        i = gpx.WInterface(None)

        # p = gpx.WContainer(lambda a, b: (0.25 * a, 0.25 * b), lambda a, b: (0.25 * a, 0.25 * b))
        # p.add_widget(WClick())
        # p.add_widget(Wm())
        # w.add_widget(p)
        i.widget_add(ws)
        #
        # b = gpx.WCBordered(lambda a, b: (0.25 * a, 0.25 * b), sizer_widget=lambda a, b: (30, 20))
        # l = gpx.WLabel()
        # l.set_str('A Test Text 龙江凯撒酱立刻到工具栏；可视角度复合控件；口脚镣手铐甲胺磷；圣诞节风口浪尖撒离开家岛风')
        # b.add_widget(l)
        # w.add_widget(b)
        #
        i1 = gpx.WInterface(i)
        i1.widget_add(gpx.WLabel('Hey!'))
        i1.widget_add(ws)

        def f1():
            w.interface = i1

        i.widget_add(gpx.WDebug())
        s = gpx.WSelect(locator=lambda a, b: (a / 4, b / 4), sizer=lambda a, b: (a / 2, 3),
                        items=[('a', lambda: True), ('b', lambda: True), ('c', lambda: True), ('d', f1)])
        i.widget_add(s)

        # def func(): f[0] = False

        # w.add_widget(WDButton(lambda a, b: (2, 3), 'exit', func))

        # def func1(): w.log('Clicked')

        # w.add_widget(WDButton(lambda a, b: (2, 4), 'log', func1))

        # w.add_widget(WTest())
        # i.add_widget(gpx.WText(sizer=lambda x, y: (10, 5)))
        w.interface = i
        i.focus = s
        w.serve(lambda: f[0] == True)


def f2():
    def main(scr):
        # curses.mousemask(0 | curses.BUTTON1_PRESSED | curses.BUTTON1_RELEASED)
        w = scr.subwin(5, 5, 5, 5)
        w.addstr('asd')
        scr.getch()

    curses.wrapper(main)


f3()
