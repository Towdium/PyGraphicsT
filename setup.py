from distutils.core import setup, Extension

module1 = Extension('pygraphicst._wcwidth',
                    sources=['pygraphicst/wcwidth.c'])

setup(name='pygraphicst',
      version='0.0.1',
      description='Yet another wrapper of ncurses',
      ext_modules=[module1])
