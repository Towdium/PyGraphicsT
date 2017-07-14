#include <Python.h>
#include <wchar.h>
#include <locale.h>

static PyObject *wcwidth_wcwidth(PyObject *self, PyObject *args)
{
    const Py_UNICODE *command;

    if (!PyArg_ParseTuple(args, "u", &command))
        return NULL;

    return PyLong_FromLong(wcwidth(command[0]));
}

static PyMethodDef wcwidth_methods[] = {
    {"wcwidth",  wcwidth_wcwidth, METH_VARARGS, "Get width of a wchar."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef wcwidth_module = {
    PyModuleDef_HEAD_INIT,
    "pygraphicst._wcwidth",      // name of module
    NULL,                        // module documentation, may be NULL
    -1,
    wcwidth_methods
};

PyMODINIT_FUNC PyInit__wcwidth(void)
{
    setlocale(LC_ALL, "");
    return PyModule_Create(&wcwidth_module);
}