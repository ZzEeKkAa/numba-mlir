# SPDX-FileCopyrightText: 2021 - 2022 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

import numba

from numba_mlir import njit as orig_njit
from numba_mlir import vectorize
from numba_mlir.mlir.passes import print_pass_ir, get_print_buffer
from numpy.testing import assert_equal, assert_allclose  # for nans comparison
import numpy as np
import itertools
import math
from functools import partial
import pytest
from sklearn.datasets import make_regression

from .utils import parametrize_function_variants
from .utils import njit_cached as njit

np.seterr(all="ignore")


def _vectorize_reference(func, arg1):
    ret = np.empty(arg1.shape, arg1.dtype)
    for ind, val in np.ndenumerate(arg1):
        ret[ind] = func(val)
    return ret


_arr_dtypes = [
    bool,
    np.int8,
    np.uint8,
    np.int16,
    np.uint16,
    np.int32,
    np.uint32,
    np.int64,
    np.uint64,
    np.float32,
    np.float64,
    np.complex64,
    np.complex128,
]

_arr_1d_bool = np.array([True, False, True, True, False, True, True, True])
_arr_1d_int32 = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=np.int32)
_arr_1d_int64 = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=np.int64)
_arr_1d_float32 = np.array([1.0, 2.1, 3.2, 4.3, 5.4, 6.5, 7.6, 8.7], dtype=np.float32)
_arr_1d_float64 = np.array([1.0, 2.1, 3.2, 4.3, 5.4, 6.5, 7.6, 8.7], dtype=np.float64)
_arr_2d_int = np.array([[1, 2, 3, 4], [5, 6, 7, 8]])
_arr_2d_float = np.array([[1.0, 2.1, 3.2, 4.3], [5.4, 6.5, 7.6, 8.7]])
_test_arrays = [
    # _arr_1d_bool,
    _arr_1d_int32,
    _arr_1d_int64,
    _arr_1d_float32,
    _arr_1d_float64,
    _arr_2d_int,
    _arr_2d_float,
    _arr_2d_int.T,
    _arr_2d_float.T,
]
_test_arrays_ids = [
    # '_arr_1d_bool',
    "_arr_1d_int32",
    "_arr_1d_int64",
    "_arr_1d_float32",
    "_arr_1d_float64",
    "_arr_2d_int",
    "_arr_2d_float",
    "_arr_2d_int.T",
    "_arr_2d_float.T",
]


@parametrize_function_variants(
    "py_func",
    [
        "lambda a: +a",
        "lambda a: -a",
        "lambda a: a.sum()",
        "lambda a: a.min()",
        "lambda a: a.max()",
        "lambda a: a.mean()",
        "lambda a: np.sum(a)",
        "lambda a: np.prod(a)",
        "lambda a: np.amax(a)",
        "lambda a: np.amin(a)",
        "lambda a: np.mean(a)",
        "lambda a: np.sqrt(a)",
        "lambda a: np.square(a)",
        "lambda a: np.log(a)",
        "lambda a: np.sin(a)",
        "lambda a: np.cos(a)",
        "lambda a: np.exp(a)",
        "lambda a: np.tanh(a)",
        "lambda a: np.abs(a)",
        "lambda a: np.absolute(a)",
        "lambda a: np.negative(a)",
        "lambda a: np.positive(a)",
        "lambda a: a.size",
        "lambda a: a.T",
        "lambda a: a.T.T",
        "lambda a: np.transpose(a)",
        "lambda a: a.copy()",
        "lambda a: np.asfortranarray(a)",
    ],
)
@pytest.mark.parametrize("arr", _test_arrays, ids=_test_arrays_ids)
def test_unary(py_func, arr, request):
    jit_func = njit(py_func)
    assert_allclose(py_func(arr), jit_func(arr), rtol=1e-4, atol=1e-7)


_test_binary_test_arrays = [
    # True,
    1,
    2.5,
    # np.array([True, False, True]),
    np.array([1, 2, 3], dtype=np.int32),
    np.array([1, 2, 3], dtype=np.int64),
    np.array([4.4, 5.5, 6.6], dtype=np.float32),
    np.array([4.4, 5.5, 6.6], dtype=np.float64),
]
_test_binary_test_arrays_ids = [
    # 'True',
    "1",
    "2.5",
    # 'np.array([True, False, True])', TODO
    "np.array([1,2,3], dtype=np.int32)",
    "np.array([1,2,3], dtype=np.int64)",
    "np.array([4.4,5.5,6.6], dtype=np.float32)",
    "np.array([4.4,5.5,6.6], dtype=np.float64)",
]


@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b: np.add(a, b)",
        "lambda a, b: a + b",
        "lambda a, b: np.subtract(a, b)",
        "lambda a, b: a - b",
        "lambda a, b: np.multiply(a, b)",
        "lambda a, b: a * b",
        "lambda a, b: np.power(a, b)",
        "lambda a, b: a ** b",
        "lambda a, b: np.true_divide(a, b)",
        "lambda a, b: a / b",
        "lambda a, b: np.arctan2(a, b)",
        "lambda a, b: np.minimum(a, b)",
        "lambda a, b: np.maximum(a, b)",
        "lambda a, b: np.less(a, b)",
        "lambda a, b: np.greater(a, b)",
        "lambda a, b: a < b",
        "lambda a, b: a <= b",
        "lambda a, b: a > b",
        "lambda a, b: a >= b",
        "lambda a, b: a == b",
        "lambda a, b: a != b",
        "lambda a, b: np.where(a < b, a, b)",
        "lambda a, b: np.outer(a, b)",
    ],
)
@pytest.mark.parametrize(
    "a", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
@pytest.mark.parametrize(
    "b", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
def test_binary(py_func, a, b):
    jit_func = njit(py_func)
    assert_allclose(py_func(a, b), jit_func(a, b), rtol=1e-7, atol=1e-7)


@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b, c: np.add(a, b, c)",
        "lambda a, b, c: np.subtract(a, b, c)",
        "lambda a, b, c: np.multiply(a, b, c)",
        "lambda a, b, c: np.power(a, b, c)",
        "lambda a, b, c: np.true_divide(a, b, c)",
        "lambda a, b, c: np.minimum(a, b, c)",
        "lambda a, b, c: np.maximum(a, b, c)",
    ],
)
@pytest.mark.parametrize(
    "a", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
@pytest.mark.parametrize(
    "b", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
def test_binary_inplace(py_func, a, b):
    jit_func = njit(py_func)

    res_temp = np.broadcast(np.array(a), np.array(b))
    py_res = np.zeros(res_temp.shape)
    jit_res = np.zeros(res_temp.shape)

    py_func(a, b, py_res)
    jit_func(a, b, jit_res)
    assert_allclose(py_res, jit_res, rtol=1e-7, atol=1e-7)


@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b: np.add(a, b)",
        "lambda a, b: a + b",
        "lambda a, b: np.subtract(a, b)",
        "lambda a, b: a - b",
        "lambda a, b: np.multiply(a, b)",
        "lambda a, b: a * b",
        "lambda a, b: np.true_divide(a, b)",
        "lambda a, b: a / b",
    ],
)
@pytest.mark.parametrize("a", [np.array([2.3 + 4.5j])] + _test_binary_test_arrays)
@pytest.mark.parametrize("b", [2, 3.5, 4.6 + 7.8j])
def test_binary_scalar(py_func, a, b):
    jit_func = njit(py_func)
    assert_allclose(py_func(a, b), jit_func(a, b), rtol=1e-7, atol=1e-7)


@parametrize_function_variants(
    "py_func",
    [
        "lambda a: a * 2",
        "lambda a: a * 2.3",
        "lambda a: a * 2.3j",
        "lambda a: a * 2.3 + 4.5j",
    ],
)
@pytest.mark.parametrize("a", [np.array([2.3 + 4.5j])] + _test_binary_test_arrays)
def test_binary_scalar_const(py_func, a):
    jit_func = njit(py_func)
    assert_allclose(py_func(a), jit_func(a), rtol=1e-7, atol=1e-7)


@pytest.mark.parametrize(
    "val", [0, 1, -1, 2**24, 2**24 - 1, np.uint64(0xFFFFFFFF_FFFFFFFF)]
)
@pytest.mark.parametrize("s", [0, 1, 7])
def test_rshift(val, s):
    def py_func(val, s):
        return val >> s

    jit_func = njit(py_func)
    s = type(val)(s)
    assert_equal(py_func(val, s), jit_func(val, s))


@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b, c: np.clip(a, b, c)",
    ],
)
@pytest.mark.parametrize(
    "a", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
@pytest.mark.parametrize(
    "b", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
@pytest.mark.parametrize(
    "c", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
def test_ternary(py_func, a, b, c):
    jit_func = njit(py_func)
    assert_allclose(py_func(a, b, c), jit_func(a, b, c), rtol=1e-7, atol=1e-7)


@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b, c, out: np.clip(a, b, c, out)",
        "lambda a, b, c, out: np.clip(a, b, c, out=out)",
    ],
)
@pytest.mark.parametrize(
    "a", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
@pytest.mark.parametrize(
    "b", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
@pytest.mark.parametrize(
    "c", _test_binary_test_arrays, ids=_test_binary_test_arrays_ids
)
def test_ternary_inplace(py_func, a, b, c):
    jit_func = njit(py_func)

    res_temp = np.broadcast(np.array(a), np.array(b), np.array(c))
    py_res = np.zeros(res_temp.shape)
    jit_res = np.zeros(res_temp.shape)

    py_func(a, b, c, py_res)
    jit_func(a, b, c, jit_res)
    assert_allclose(py_res, jit_res, rtol=1e-7, atol=1e-7)


_test_logical_arrays = [
    True,
    False,
    np.array([True, False]),
    np.array([[False, True], [True, False]]),
]


@parametrize_function_variants(
    "py_func",
    [
        "lambda a: np.logical_not(a)",
    ],
)
@pytest.mark.parametrize("a", _test_logical_arrays)
def test_logical1(py_func, a):
    jit_func = njit(py_func)
    assert_equal(py_func(a), jit_func(a))


@pytest.mark.smoke
@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b: np.logical_and(a, b)",
        "lambda a, b: a & b",
        "lambda a, b: np.logical_or(a, b)",
        "lambda a, b: a | b",
        "lambda a, b: np.logical_xor(a, b)",
        "lambda a, b: a ^ b",
    ],
)
@pytest.mark.parametrize("a", _test_logical_arrays)
@pytest.mark.parametrize("b", _test_logical_arrays)
def test_logical2(py_func, a, b):
    jit_func = njit(py_func)
    assert_equal(py_func(a, b), jit_func(a, b))


_test_broadcast_test_arrays = [
    1,
    np.array([1]),
    np.array([[1]]),
    np.array([[1, 2], [3, 4]]),
    np.array([5, 6]),
    np.array([[5], [6]]),
    np.array([[5, 6]]),
]
_test_broadcast_test_arrays_ids = [
    "1",
    "np.array([1])",
    "np.array([[1]])",
    "np.array([[1,2],[3,4]])",
    "np.array([5,6])",
    "np.array([[5],[6]])",
    "np.array([[5,6]])",
]


@pytest.mark.parametrize(
    "a", _test_broadcast_test_arrays, ids=_test_broadcast_test_arrays_ids
)
@pytest.mark.parametrize(
    "b", _test_broadcast_test_arrays, ids=_test_broadcast_test_arrays_ids
)
def test_broadcast(a, b):
    def py_func(a, b):
        return np.add(a, b)

    jit_func = njit(py_func)
    assert_equal(py_func(a, b), jit_func(a, b))


@pytest.mark.parametrize(
    "a_shape, b_shape",
    [((2, 3, 4), (2, 1, 4)), ((1, 2, 3), (1, 1)), ((2, 3, 4), (3, 4))],
)
def test_broadcast_setitem(a_shape, b_shape):
    def py_func(a, b):
        a[:] = b
        return a

    jit_func = njit(py_func)

    a = np.zeros(a_shape)
    b = np.arange(math.prod(b_shape)).reshape(b_shape)

    assert_equal(py_func(a.copy(), b), jit_func(a.copy(), b))


@pytest.mark.parametrize("a", [np.arange(3 * 4 * 5).reshape(3, 4, 5)])
@parametrize_function_variants(
    "py_func",
    list(
        f"lambda a: np.transpose(a, {str(axes)})"
        for axes in list(itertools.permutations((0, 1, 2)))
    ),
)
def test_transpose(a, py_func):
    jit_func = njit(py_func)
    assert_equal(py_func(a), jit_func(a))


@parametrize_function_variants(
    "py_func",
    [
        "lambda: np.pi",
        "lambda: np.e",
    ],
)
def test_np_const(py_func):
    jit_func = njit(py_func)
    assert_equal(py_func(), jit_func())


@pytest.mark.parametrize(
    "a",
    [
        # -2.5, double->int64 cast mismatch
        -1,
        -0.0,
        0,
        0.0,
        2,
        3.5,
        # -1 + 2j, TODO: complex casts
        # 2.3 - 3.4j,
    ],
)
@pytest.mark.parametrize("dtype", _arr_dtypes)
def test_dtype_cast(a, dtype):
    def py_func(val):
        return dtype(val)

    jit_func = njit(py_func)
    assert_equal(py_func(a), jit_func(a))


@pytest.mark.parametrize(
    "idx",
    [
        1,
        np.int8(1),
        np.int16(1),
        np.int32(1),
        np.int64(1),
        np.uint8(1),
        np.uint16(1),
        np.uint32(1),
        np.uint64(1),
    ],
)
def test_staticgetitem(idx):
    def py_func(a):
        return a[idx]

    jit_func = njit(py_func)
    arr = np.asarray([5, 6, 7])
    assert_equal(py_func(arr), jit_func(arr))


@pytest.mark.parametrize("i", list(range(-2, 3)))
def test_getitem1(i):
    def py_func(a, b):
        return a[b]

    jit_func = njit(py_func)
    arr = np.asarray([5, 6, 7])
    assert_equal(py_func(arr, i), jit_func(arr, i))


def test_getitem2():
    def py_func(a, b):
        return a[b]

    jit_func = njit(py_func)
    arr = np.asarray([[[1, 2, 3], [5, 6, 7]]])
    assert_equal(py_func(arr, 0), jit_func(arr, 0))


def test_getitem3():
    def py_func(a, b, c):
        return a[b, c]

    jit_func = njit(py_func)
    arr = np.asarray([[[1, 2, 3], [5, 6, 7]]])
    assert_equal(py_func(arr, 0, 0), jit_func(arr, 0, 0))


_unituple_indices = [-2, -1, 0, 1, 2]


@pytest.mark.parametrize("index", _unituple_indices)
def test_unituple_getitem1(index):
    def py_func(a, b, c, i):
        t = (a, b, c)
        return t[i]

    jit_func = njit(py_func)
    assert_equal(py_func(1, 2, 3, index), jit_func(1, 2, 3, index))


@pytest.mark.parametrize("index", _unituple_indices)
def test_unituple_getitem2(index):
    def py_func(t, i):
        return t[i]

    jit_func = njit(py_func)
    t = (1, 2, 3)
    assert_equal(py_func(t, index), jit_func(t, index))


@pytest.mark.parametrize("index", _unituple_indices)
def test_unituple_getitem3(index):
    def py_func(a, i):
        s = a.shape
        return s[i]

    jit_func = njit(py_func)
    a = np.empty((1, 2, 3))
    assert_equal(py_func(a, index), jit_func(a, index))


@pytest.mark.parametrize("index", _unituple_indices)
def test_unituple_getitem4(index):
    def py_func(t):
        return t[index]

    jit_func = njit(py_func)
    t = (1, 2, 3)
    assert_equal(py_func(t), jit_func(t))


def _skip_not_1d(args):
    # TODO: not supported by numba
    mark = lambda a: pytest.param(a, marks=pytest.mark.xfail)
    return [mark(a) if a.ndim > 1 else a for a in args]


@pytest.mark.parametrize("arr", _skip_not_1d(_test_arrays), ids=_test_arrays_ids)
@pytest.mark.parametrize("mask", [[True], [False], [True, False], [False, True]])
def test_getitem_mask(arr, mask):
    def py_func(a, m):
        return a[m]

    mask = np.resize(mask, arr.size).reshape(arr.shape)

    jit_func = njit(py_func)
    assert_equal(py_func(arr, mask), jit_func(arr, mask))


@pytest.mark.parametrize("arr", _skip_not_1d(_test_arrays), ids=_test_arrays_ids)
@pytest.mark.parametrize("offset", [[], [0], [1, 2, 3], [3, 2, 1]])
def test_getitem_offset(arr, offset):
    def py_func(a, m):
        return a[m]

    offset = np.array(offset, np.int32)

    jit_func = njit(py_func)
    assert_equal(py_func(arr, offset), jit_func(arr, offset))


def test_array_len():
    def py_func(a):
        return len(a)

    jit_func = njit(py_func)
    arr = np.asarray([5, 6, 7])
    assert_equal(py_func(arr), jit_func(arr))


def test_array_capture1():
    a = np.arange(2 * 3 * 4, dtype=np.int32).reshape(2, 3, 4)
    b = a.copy()

    def py_func(a):
        return a + b

    jit_func = njit(py_func)
    assert_equal(py_func(a), jit_func(a))


@pytest.mark.parametrize(
    "val",
    [
        np.int8(1),
        np.int16(1),
        np.int32(1),
        np.int64(1),
        np.float32(2.3),
        np.float64(2.3),
        np.complex64(3.4 - 5.6j),
        np.complex128(3.4 - 5.6j),
    ],
)
def test_array_capture2(val):
    a = np.arange(2 * 3 * 4, dtype=val.dtype).reshape(2, 3, 4)
    b = np.full(a.shape, val, dtype=a.dtype)

    def py_func(a):
        return a + b

    jit_func = njit(py_func)
    assert_equal(py_func(a), jit_func(a))


def _gen_reduce_axis_func():
    template = [
        "lambda a: np.%s(a, dtype=np.int16)",
        "lambda a: np.%s(a, dtype=np.int16, axis=0)",
        "lambda a: np.%s(a, axis=0)",
        "lambda a: np.%s(a, axis=1)",
        "lambda a: np.%s(a, axis=-1)",
        "lambda a: np.%s(a, axis=-2)",
        "lambda a: np.%s(a, axis=0, keepdims=False)",
        "lambda a: np.%s(a, axis=0, keepdims=True)",
    ]

    res = []
    for func in ["sum", "amax", "amin", "max", "min", "prod", "mean"]:
        for t in template:
            if ("max" in func or "min" in func) and "dtype=" in t:
                continue
            res.append(t % func)
    return res


@parametrize_function_variants("py_func", _gen_reduce_axis_func())
@pytest.mark.parametrize(
    "arr",
    [
        np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int32),
        np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32),
    ],
)
def test_reduce_axis(py_func, arr):
    jit_func = njit(py_func)
    assert_equal(py_func(arr), jit_func(arr))


@parametrize_function_variants(
    "py_func",
    [
        "lambda a: np.flip(a)",
    ],
)
@pytest.mark.parametrize(
    "arr",
    [
        np.array([1, 2, 3, 4, 5, 6], dtype=np.int32),
        np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int32),
        np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.int32),
    ],
)
def test_flip1(py_func, arr):
    jit_func = njit(py_func)
    assert_equal(py_func(arr), jit_func(arr))


@parametrize_function_variants(
    "py_func",
    [
        "lambda a: np.flip(a, axis=0)",
        "lambda a: np.flip(a, axis=1)",
        "lambda a: np.flip(a, axis=-1)",
        "lambda a: np.flip(a, axis=-2)",
    ],
)
@pytest.mark.parametrize(
    "arr",
    [
        np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.int32),
        np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.float32),
    ],
)
@pytest.mark.xfail
def test_flip2(py_func, arr):
    jit_func = njit(py_func)
    assert_equal(py_func(arr), jit_func(arr))


def test_sum_add():
    def py_func(a, b):
        return np.add(a, b).sum()

    jit_func = njit(py_func)
    arr1 = np.asarray([1, 2, 3])
    arr2 = np.asarray([4, 5, 6])
    assert_equal(py_func(arr1, arr2), jit_func(arr1, arr2))


def test_sum_add2():
    def py_func(a, b, c):
        t = np.add(a, b)
        return np.add(t, c).sum()

    jit_func = njit(py_func)
    arr1 = np.asarray([1, 2, 3])
    arr2 = np.asarray([4, 5, 6])
    arr3 = np.asarray([7, 8, 9])
    assert_equal(py_func(arr1, arr2, arr3), jit_func(arr1, arr2, arr3))


@pytest.mark.parametrize("arr", _test_arrays)
@pytest.mark.parametrize("name", ["sqrt", "log", "exp", "sin", "cos"])
def test_math_uplifting1(arr, name):
    py_func = eval(f"lambda a: np.{name}(a)")

    with print_pass_ir([], ["UpliftMathPass"]):
        jit_func = njit(py_func)

        assert_allclose(py_func(arr), jit_func(arr), rtol=1e-7, atol=1e-7)
        ir = get_print_buffer()
        assert ir.count(f"math.{name}") == 1, ir


_scalars = [1, 2.5, 3.6 + 4.7j]
_complex_arrays = [
    np.array([1, 2, 3]),
    np.array([1.5, 2.6, 3.7]),
    np.array([1.0 + 2.0j, -3.0 + 4.0j, 5.0 + -6.0j]),
]


@pytest.mark.parametrize("a", _complex_arrays)
@parametrize_function_variants(
    "py_func",
    [
        "lambda a: np.abs(a)",
        "lambda a: np.exp(a)",
        "lambda a: np.sqrt(a)",
    ],
)
def test_complex_unary(a, py_func):
    jit_func = njit(py_func, parallel=True)
    assert_allclose(py_func(a), jit_func(a), rtol=1e-7, atol=1e-7)


@pytest.mark.parametrize(
    "a,b", itertools.product(_scalars + _complex_arrays, _complex_arrays)
)
@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b: np.add(a, b)",
        "lambda a, b: a + b",
        "lambda a, b: a * b",
    ],
)
def test_complex_binary(a, b, py_func):
    jit_func = njit(py_func, parallel=True)
    assert_allclose(py_func(a, b), jit_func(a, b), rtol=1e-7, atol=1e-7)


@pytest.mark.parametrize("dtype", [np.int32, np.float32])
def test_dtype_indirect(dtype):
    def py_func1(dtype):
        return np.ones(10, dtype=dtype)

    jit_func1 = njit(py_func1, parallel=True)

    def py_func2(dtype):
        return jit_func1(dtype)

    jit_func2 = njit(py_func2, parallel=True)

    assert_equal(py_func2(dtype), jit_func2(dtype))


_dot_args = [
    (np.array([1, 2, 3], np.float32), np.array([4, 5, 6], np.float32)),
    (
        np.flip(np.array([1, 2, 3], np.float32), 0),
        np.flip(np.array([4, 5, 6], np.float32), 0),
    ),
    (
        np.array([[1, 2, 3], [4, 5, 6]], np.float32),
        np.array([[1, 2], [3, 4], [5, 6]], np.float32),
    ),
    (
        np.flip(np.array([[1, 2, 3], [4, 5, 6]], np.float32), 0),
        np.array([[1, 2], [3, 4], [5, 6]], np.float32),
    ),
    (
        np.array([[1, 2, 3], [4, 5, 6]], np.float32),
        np.flip(np.array([[1, 2], [3, 4], [5, 6]], np.float32), 1),
    ),
    (
        np.flip(np.array([[1, 2, 3], [4, 5, 6]], np.float32), 0),
        np.flip(np.array([[1, 2], [3, 4], [5, 6]], np.float32), 1),
    ),
]


@pytest.mark.parametrize("a,b", _dot_args)
@pytest.mark.parametrize("parallel", [False, True])
def test_dot(a, b, parallel):
    def py_func(a, b):
        return np.dot(a, b)

    jit_func = njit(py_func, parallel=parallel)
    assert_equal(py_func(a, b), jit_func(a, b))


def _skip_test_dot_out_cases(args):
    mark = lambda a: pytest.param(*a, marks=pytest.mark.xfail)

    def check(a, b):
        return a.ndim == 1 or b.ndim == 1

    return [mark((a, b)) if check(a, b) else (a, b) for a, b in args]


@pytest.mark.parametrize("a,b", _skip_test_dot_out_cases(_dot_args))
@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b, c: np.dot(a, b, c)",
        "lambda a, b, c: np.dot(a, b, out=c)",
    ],
)
def test_dot_out(a, b, py_func):
    if a.ndim == 1 or b.ndim == 1:
        pytest.xfail()  # Not supported by Numba

    jit_func = njit(py_func)

    tmp = np.dot(a, b)
    res_py = np.zeros_like(tmp)
    res_jit = np.zeros_like(tmp)

    py_func(a, b, res_py)
    jit_func(a, b, res_jit)
    assert_equal(res_py, res_jit)


def test_prange_lowering():
    def py_func(arr):
        res = 0
        for i in numba.prange(len(arr)):
            res += arr[i]

        return res

    with print_pass_ir([], ["ParallelToTbbPass"]):
        jit_func = njit(py_func, parallel=True)
        arr = np.arange(10000, dtype=np.float32)
        assert_equal(py_func(arr), jit_func(arr))
        ir = get_print_buffer()
        assert ir.count('"numba_util.parallel"') == 1, ir


@pytest.mark.skip()
def test_prange_lowering_indirect():
    def py_func1(arr):
        res = 0
        for i in numba.prange(len(arr)):
            res += arr[i]

        return res

    jit_func1 = njit(py_func1, parallel=True)

    def py_func2(arr):
        return jit_func1(arr)

    jit_func2 = njit(py_func2)

    with print_pass_ir([], ["ParallelToTbbPass"]):
        arr = np.arange(10000, dtype=np.float32)
        assert_equal(py_func1(arr), jit_func1(arr))
        ir = get_print_buffer()
        assert ir.count("numba_util.parallel") == 1, ir

    with print_pass_ir([], ["ParallelToTbbPass"]):
        arr = np.arange(10000, dtype=np.float32)
        assert_equal(py_func2(arr), jit_func2(arr))
        ir = get_print_buffer()
        assert ir.count("numba_util.parallel") == 1, ir


@pytest.mark.parametrize(
    "dtype", [np.int32, np.int64, np.float32, np.float64, np.complex64, np.complex128]
)
def test_prange_atomic(dtype):
    def py_func(n, s):
        res = np.zeros(s, dtype=dtype)
        for i in numba.prange(n):
            res[i % s] += dtype(i)

        return res

    jit_func = njit(py_func, parallel=True)

    N = 10000
    S = 10
    with print_pass_ir([], ["GenAtomicOpsPass"]):
        assert_allclose(py_func(N, S), jit_func(N, S), rtol=1e-5)
        ir = get_print_buffer()
        assert ir.count("memref.atomic_rmw") > 0, ir


def test_loop_fusion1():
    def py_func(arr):
        l = len(arr)
        res1 = 0
        for i in numba.prange(l):
            res1 += arr[i]

        res2 = 1.0
        for i in numba.prange(l):
            res2 *= arr[i]

        return res1, res2

    with print_pass_ir([], ["PostLinalgOptPass"]):
        jit_func = njit(py_func)
        arr = np.arange(1, 15, dtype=np.float32)
        assert_equal(py_func(arr), jit_func(arr))
        ir = get_print_buffer()
        assert ir.count("scf.parallel") == 1, ir
        assert ir.count("memref.load") == 1, ir


def test_loop_fusion2():
    def py_func(arr):
        l = len(arr)
        res1 = 0
        for i in numba.prange(l):
            res1 += arr[i]

        res1 += 10

        res2 = 0.0
        for i in numba.prange(l):
            res2 *= arr[i]

        return res1, res2

    with print_pass_ir([], ["PostLinalgOptPass"]):
        jit_func = njit(py_func)
        arr = np.arange(1, 15, dtype=np.float32)
        assert_equal(py_func(arr), jit_func(arr))
        ir = get_print_buffer()
        assert ir.count("scf.parallel") == 1, ir
        assert ir.count("memref.load") == 1, ir


def test_loop_fusion3():
    def py_func(arr):
        l = len(arr)
        res1 = 0
        for i in numba.prange(l):
            res1 += arr[i]

        res2 = 1.0
        for i in numba.prange(l):
            res2 *= arr[i] * res1

        return res1, res2

    with print_pass_ir([], ["PostLinalgOptPass"]):
        jit_func = njit(py_func)
        arr = np.arange(1, 15, dtype=np.float32)
        assert_equal(py_func(arr), jit_func(arr))
        ir = get_print_buffer()
        assert ir.count("scf.parallel") == 2, ir
        assert ir.count("memref.load") == 2, ir


def test_copy_fusion():
    def py_func(a, b):
        a = a + 1
        b[:] = a

    jit_func = njit(py_func)
    a = np.arange(13)

    res_py = np.zeros_like(a)
    res_jit = np.zeros_like(a)

    with print_pass_ir([], ["PostLinalgOptPass"]):
        py_func(a, res_py)
        jit_func(a, res_jit)

        assert_equal(res_py, res_jit)
        ir = get_print_buffer()
        assert ir.count("scf.parallel") == 1, ir


def test_fusion_conflict1():
    def py_func(a):
        a[:] = np.flip(a)
        return a

    jit_func = njit(py_func)
    a = np.arange(13)

    with print_pass_ir([], ["PostLinalgOptPass"]):
        assert_equal(py_func(a.copy()), jit_func(a.copy()))
        ir = get_print_buffer()
        assert ir.count("scf.parallel") == 2, ir


def test_fusion_conflict2():
    def py_func(a):
        a[:] = np.flip(a + 1)
        return a

    jit_func = njit(py_func)
    a = np.arange(13)

    with print_pass_ir([], ["PostLinalgOptPass"]):
        assert_equal(py_func(a.copy()), jit_func(a.copy()))
        ir = get_print_buffer()
        assert ir.count("scf.parallel") == 2, ir


def test_broadcast_fusion1():
    def py_func(a):
        return a + a * a

    jit_func = njit(py_func)
    a = np.arange(13)

    with print_pass_ir([], ["PostLinalgOptPass"]):
        assert_equal(py_func(a), jit_func(a))
        ir = get_print_buffer()
        assert ir.count("scf.parallel") == 1, ir


_broadcast_fusion_shapes = [
    (1, 1),
    (1, 7),
    (7, 1),
    (7, 7),
]


@pytest.mark.parametrize("a_shape", _broadcast_fusion_shapes)
@pytest.mark.parametrize("b_shape", _broadcast_fusion_shapes)
@pytest.mark.parametrize("c_shape", _broadcast_fusion_shapes)
def test_broadcast_fusion2(a_shape, b_shape, c_shape):
    def py_func(a, b, c):
        return a + b * c

    jit_func = njit(py_func)
    a = np.arange(math.prod(a_shape)).reshape(a_shape)
    b = np.arange(math.prod(b_shape)).reshape(b_shape)
    c = np.arange(math.prod(c_shape)).reshape(c_shape)

    with print_pass_ir([], ["PostLinalgOptPass"]):
        assert_equal(py_func(a, b, c), jit_func(a, b, c))
        ir = get_print_buffer()
        assert ir.count("scf.parallel") <= 1, ir


@pytest.mark.parametrize("dtype", [np.int32, np.int64, np.float32])
def test_np_reduce(dtype):
    def py_func(arr):
        return arr.sum()

    with print_pass_ir([], ["PostLinalgOptPass"]):
        jit_func = njit(py_func)
        arr = np.array([[1, 2, 3], [4, 5, 6]], dtype=dtype)
        assert_equal(py_func(arr), jit_func(arr))
        ir = get_print_buffer()
        assert ir.count("scf.parallel") == 1, ir
        assert ir.count("memref.load") == 1, ir


_indirect_array_call_args = [
    np.arange(12),
    np.arange(12).reshape(3, 4),
    np.arange(12).reshape(3, 4).T,
]


@pytest.mark.parametrize("arr", _indirect_array_call_args)
def test_indirect_call_array1(arr):
    def inner_func(a):
        return a + 3

    def func(func, a):
        return func(a)

    jit_inner_func = njit(inner_func)
    jit_func = njit(func)

    assert_equal(func(inner_func, arr), jit_func(jit_inner_func, arr))


@pytest.mark.parametrize("arr", _indirect_array_call_args)
def test_indirect_call_array2(arr):
    def inner_func(a):
        return a

    def func(func, a):
        b = func(a)
        return func(b)

    jit_inner_func = njit(inner_func)
    jit_func = njit(func)

    assert_equal(func(inner_func, arr), jit_func(jit_inner_func, arr))


def test_loop_if():
    def py_func(arr):
        for i in range(len(arr)):
            if arr[i] == 5:
                arr[i] = 6
        return arr

    jit_func = njit(py_func)
    arr1 = np.arange(100)
    arr2 = np.arange(100)
    assert_equal(py_func(arr1), jit_func(arr2))


def test_static_setitem1():
    def py_func(a):
        a[1] = 42
        return a

    jit_func = njit(py_func)
    arr = np.asarray([1, 2, 3])
    assert_equal(py_func(arr.copy()), jit_func(arr.copy()))


def test_static_setitem2():
    def py_func(a):
        a[:] = 42
        return a

    jit_func = njit(py_func)
    arr = np.asarray([1, 2, 3])
    assert_equal(py_func(arr.copy()), jit_func(arr.copy()))


def test_static_setitem3():
    def py_func(a):
        a[(0, 1)] = 42
        return a

    jit_func = njit(py_func)
    arr = np.asarray([[1, 2], [3, 4]])
    assert_equal(py_func(arr.copy()), jit_func(arr.copy()))


@pytest.mark.parametrize("i", list(range(-2, 3)))
def test_setitem1(i):
    def py_func(a, b):
        a[b] = 42
        return a[b]

    jit_func = njit(py_func)
    arr = np.asarray([1, 2, 3])
    assert_equal(py_func(arr, i), jit_func(arr, i))


def test_setitem2():
    def py_func(a, b, c):
        a[b, c] = 42
        return a[b, c]

    jit_func = njit(py_func)
    arr = np.asarray([[1, 2, 3], [4, 5, 6]])
    assert_equal(py_func(arr, 1, 2), jit_func(arr, 1, 2))


@pytest.mark.parametrize("d", [np.array([5, 6]), 7])
def test_setitem_slice1(d):
    def py_func(a, b, c, d):
        a[b:c] = d
        return a

    jit_func = njit(py_func)
    arr = np.asarray([1, 2, 3, 4])
    assert_equal(py_func(arr.copy(), 1, 3, d), jit_func(arr.copy(), 1, 3, d))


@pytest.mark.parametrize("d", [np.array([5, 6, 7]), 7])
def test_setitem_slice2(d):
    def py_func(a, c, d):
        a[:c] = d
        return a

    jit_func = njit(py_func)
    arr = np.asarray([1, 2, 3, 4])
    assert_equal(py_func(arr.copy(), 3, d), jit_func(arr.copy(), 3, d))


@pytest.mark.parametrize("d", [np.array([5, 6, 7]), 7])
def test_setitem_slice3(d):
    def py_func(a, b, d):
        a[b:] = d
        return a

    jit_func = njit(py_func)
    arr = np.asarray([1, 2, 3, 4])
    assert_equal(py_func(arr.copy(), 1, d), jit_func(arr.copy(), 1, d))


def test_setitem_loop():
    def py_func(a):
        for i in range(len(a)):
            a[i] = a[i] + i
        return a.sum()

    jit_func = njit(py_func)
    arr = np.asarray([3, 2, 1])
    assert_equal(py_func(arr.copy()), jit_func(arr.copy()))


def test_array_bounds1():
    def py_func(a):
        res = 0
        for i in range(len(a)):
            if i >= len(a) or i < 0:
                res = res + 1
            else:
                res = res + a[i]
        return res

    arr = np.asarray([3, 2, 1])

    with print_pass_ir([], ["PostLinalgOptPass"]):
        jit_func = njit(py_func)
        assert_equal(py_func(arr.copy()), jit_func(arr.copy()))
        ir = get_print_buffer()
        assert ir.count("cmpi") == 0, ir


def test_array_bounds2():
    def py_func(a):
        res = 0
        for i in range(len(a)):
            if i < len(a) and i >= 0:
                res = res + a[i]
            else:
                res = res + 1
        return res

    arr = np.asarray([3, 2, 1])

    with print_pass_ir([], ["PostLinalgOptPass"]):
        jit_func = njit(py_func)
        assert_equal(py_func(arr.copy()), jit_func(arr.copy()))
        ir = get_print_buffer()
        assert ir.count("cmpi") == 0, ir


def test_array_bounds3():
    def py_func(a):
        res = 0
        for i in range(len(a)):
            if 0 <= i < len(a):
                res = res + a[i]
            else:
                res = res + 1
        return res

    arr = np.asarray([3, 2, 1])

    with print_pass_ir([], ["PostLinalgOptPass"]):
        jit_func = njit(py_func)
        assert_equal(py_func(arr.copy()), jit_func(arr.copy()))
        ir = get_print_buffer()
        assert ir.count("cmpi") == 0, ir


def test_array_bounds4():
    def py_func(a):
        res = 0
        for i in range(len(a) - 1):
            if 0 <= i < (len(a) - 1):
                res = res + a[i]
            else:
                res = res + 1
        return res

    arr = np.asarray([3, 2, 1])

    with print_pass_ir([], ["PostLinalgOptPass"]):
        jit_func = njit(py_func)
        assert_equal(py_func(arr.copy()), jit_func(arr.copy()))
        ir = get_print_buffer()
        assert ir.count("cmpi") == 0, ir


@pytest.mark.parametrize("arr", _test_arrays, ids=_test_arrays_ids)
def test_array_shape(arr):
    def py_func(a):
        return a.shape

    jit_func = njit(py_func)
    assert_equal(py_func(arr), jit_func(arr))


@pytest.mark.parametrize("dtype", _arr_dtypes)
def test_array_itemsize(dtype):
    def py_func(a):
        return a.itemsize

    jit_func = njit(py_func)
    arr = np.array([], dtype=dtype)
    assert_equal(py_func(arr), jit_func(arr))


_strides_test_array = np.arange(3 * 4 * 5, dtype=np.int32).reshape(3, 4, 5)


@pytest.mark.parametrize(
    "arr",
    [
        np.array([1, 2, 3, 4, 5, 6], dtype=np.int32),
        np.array([1, 2, 3, 4, 5, 6], dtype=np.int32)[::2],
        np.array([1, 2, 3, 4, 5, 6], dtype=np.int32)[::3],
        np.array([1, 2, 3, 4, 5, 6], dtype=np.int32)[::-1],
        np.array([1, 2, 3, 4, 5, 6], dtype=np.int32)[::-2],
        np.array([[1, 2, 3], [4, 5, 6]], dtype=np.int32),
        _strides_test_array,
        _strides_test_array[::2, ::, ::],
        _strides_test_array[::-2, ::, ::],
        _strides_test_array[::, ::2, ::],
        _strides_test_array[::, ::-2, ::],
        _strides_test_array[::, ::, ::2],
        _strides_test_array[::, ::, ::-2],
        np.flip(_strides_test_array),
        np.flip(_strides_test_array, axis=0),
        np.flip(_strides_test_array, axis=1),
        np.flip(_strides_test_array, axis=2),
    ],
)
def test_array_strides(arr):
    def py_func(a):
        return a.strides

    jit_func = njit(py_func)
    assert_equal(py_func(arr), jit_func(arr))


def test_array_return():
    def py_func(a):
        return a

    jit_func = njit(py_func)
    arr = np.array([1, 2, 3])
    assert_equal(py_func(arr), jit_func(arr))


def test_array_prange_const():
    def py_func(a, b):
        a[0] = 42
        for i in numba.prange(b):
            a[0] = 1
        return a[0]

    jit_func = njit(py_func, parallel=True)
    arr = np.array([0.0])
    assert_equal(py_func(arr, 5), jit_func(arr, 5))


def test_empty1():
    def py_func(d):
        a = np.empty(d)
        for i in range(d):
            a[i] = i
        return a

    jit_func = njit(py_func)
    assert_equal(py_func(5), jit_func(5))


def test_empty2():
    def py_func(d1, d2):
        a = np.empty((d1, d2))
        for i in range(d1):
            for j in range(d2):
                a[i, j] = i + j * 10
        return a

    jit_func = njit(py_func)
    assert_equal(py_func(5, 7), jit_func(5, 7))


@pytest.mark.parametrize("dtype", ["int32", "int64", "float32", "float64"])
def test_empty3(dtype):
    def py_func(a):
        return np.empty(a.shape, a.dtype)

    jit_func = njit(py_func)
    arr = np.array([1, 2, 3], dtype=dtype)
    assert_equal(py_func(arr).shape, jit_func(arr).shape)
    assert_equal(py_func(arr).dtype, jit_func(arr).dtype)


@pytest.mark.parametrize("shape", [1, (2,), (2, 3), (4, 5, 6)])
@pytest.mark.parametrize("dtype", ["int32", "int64", "float32", "float64"])
def test_empty_like(shape, dtype):
    def py_func(a):
        return np.empty_like(a)

    jit_func = njit(py_func)
    arr = np.empty(shape=shape, dtype=dtype)
    assert_equal(py_func(arr).shape, jit_func(arr).shape)
    assert_equal(py_func(arr).dtype, jit_func(arr).dtype)


@pytest.mark.parametrize("func", [np.zeros, np.ones], ids=["zeros", "ones"])
def test_init1(func):
    def py_func(d):
        return func(d)

    jit_func = njit(py_func)
    assert_equal(py_func(5), jit_func(5))


@pytest.mark.parametrize("func", [np.zeros, np.ones], ids=["zeros", "ones"])
@pytest.mark.parametrize("dtype", _arr_dtypes)
def test_init2(func, dtype):
    def py_func(a):
        return func(a.shape, a.dtype)

    jit_func = njit(py_func)
    arr = np.array([1, 2, 3], dtype=dtype)
    assert_equal(py_func(arr).shape, jit_func(arr).shape)
    assert_equal(py_func(arr).dtype, jit_func(arr).dtype)


@pytest.mark.parametrize("func", [np.zeros, np.ones], ids=["zeros", "ones"])
@pytest.mark.xfail
def test_init3(func):
    def py_func(d):
        return func(d, dtype=np.dtype("int64"))

    jit_func = njit(py_func)
    assert_equal(py_func(5), jit_func(5))


@pytest.mark.parametrize("func", [np.zeros, np.ones], ids=["zeros", "ones"])
def test_init4(func):
    def py_func(d):
        return func(d)

    jit_func = njit(py_func)
    assert_equal(py_func((2, 1)), jit_func((2, 1)))


@pytest.mark.parametrize("shape", [2, (3, 4), (5, 6, 7)])
@pytest.mark.parametrize("dtype", _arr_dtypes)
@pytest.mark.parametrize(
    "func", [np.zeros_like, np.ones_like], ids=["zeros_like", "ones_like"]
)
def test_init_like1(shape, dtype, func):
    def py_func(d):
        return func(d)

    a = np.empty(shape=shape, dtype=dtype)
    jit_func = njit(py_func)
    assert_equal(py_func(a), jit_func(a))


@pytest.mark.parametrize("shape", [2, (3, 4), (5, 6, 7)])
@pytest.mark.parametrize("dtype", _arr_dtypes)
@pytest.mark.parametrize(
    "func", [np.zeros_like, np.ones_like], ids=["zeros_like", "ones_like"]
)
def test_init_like2(shape, dtype, func):
    def py_func(d, shape):
        return func(d, shape=shape)

    a = np.empty(shape=shape, dtype=dtype)
    jit_func = njit(py_func)
    assert_equal(py_func(a, shape), jit_func(a, shape))


def _skip_bool(dtypes):
    mark = lambda a: pytest.param(a, marks=pytest.mark.xfail)
    return [mark(a) if a is bool else a for a in dtypes]


@pytest.mark.parametrize("shape", [2, (3, 4), (5, 6, 7)])
@pytest.mark.parametrize("dtype", _skip_bool([None] + _arr_dtypes))
@pytest.mark.parametrize(
    "func", [np.zeros_like, np.ones_like], ids=["zeros_like", "ones_like"]
)
def test_init_like3(shape, dtype, func):
    def py_func(d, dtype):
        return func(d, dtype=dtype)

    a = np.empty(shape=shape, dtype=np.int32)
    jit_func = njit(py_func)
    assert_equal(py_func(a, dtype), jit_func(a, dtype))


@pytest.mark.parametrize("shape", [2, (3, 4), (5, 6, 7)])
@pytest.mark.parametrize("dtype", _skip_bool([None] + _arr_dtypes))
@pytest.mark.parametrize(
    "func", [np.zeros_like, np.ones_like], ids=["zeros_like", "ones_like"]
)
def test_init_like4(shape, dtype, func):
    def py_func(d, shape, dtype):
        return func(d, shape=shape, dtype=dtype)

    a = np.empty(shape=1, dtype=np.int32)
    jit_func = njit(py_func)
    assert_equal(py_func(a, shape, dtype), jit_func(a, shape, dtype))


@parametrize_function_variants(
    "py_func",
    [
        "lambda : np.arange(0)",
        "lambda : np.arange(1)",
        "lambda : np.arange(7)",
        "lambda : np.arange(-1)",
        "lambda : np.arange(-1,6)",
        "lambda : np.arange(-1,6,1)",
        "lambda : np.arange(-1,6,2)",
        "lambda : np.arange(-1,6,3)",
        "lambda : np.arange(6,-1,-1)",
        "lambda : np.arange(6,-1,-2)",
        "lambda : np.arange(6,-1,-3)",
        "lambda : np.arange(5,dtype=np.int32)",
        "lambda : np.arange(5,dtype=np.float32)",
    ],
)
def test_arange(py_func):
    jit_func = njit(py_func)
    assert_equal(py_func(), jit_func())


@pytest.mark.parametrize("dtype", [np.int32, np.int64, np.float32, np.float64])
def test_dtype_param(dtype):
    def py_func(dt):
        return np.zeros((1,), dtype=dt)

    jit_func = njit(py_func)

    jit_func = njit(py_func)
    assert_equal(py_func(dtype).shape, jit_func(dtype).shape)
    assert_equal(py_func(dtype).dtype, jit_func(dtype).dtype)


def test_parallel():
    def py_func(a, b):
        return np.add(a, b)

    jit_func = njit(py_func, parallel=True)
    arr = np.asarray([[[1, 2, 3], [4, 5, 6]], [[1, 2, 3], [4, 5, 6]]])
    assert_equal(py_func(arr, arr), jit_func(arr, arr))


def test_parallel_reduce():
    def py_func(a):
        shape = a.shape
        res = 0
        for i in range(shape[0]):
            for j in numba.prange(shape[1]):
                for k in numba.prange(shape[2]):
                    res = res + a[i, j, k]
        return res

    jit_func = njit(py_func, parallel=True)
    arr = np.asarray([[[1, 2, 3], [4, 5, 6]]]).repeat(10000, 0)
    assert_equal(py_func(arr), jit_func(arr))


@parametrize_function_variants(
    "func",
    [
        "lambda a : a + 1",
        "lambda a : math.erf(a)",
        # 'lambda a : 5 if a == 1 else a', TODO: investigate
    ],
)
@pytest.mark.parametrize("arr", _test_arrays, ids=_test_arrays_ids)
def test_vectorize(func, arr):
    arr = np.array(arr)
    vec_func = vectorize(func)
    # assert_equal(_vectorize_reference(func, arr), vec_func(arr))
    assert_allclose(
        _vectorize_reference(func, arr), vec_func(arr), rtol=1e-7, atol=1e-7
    )


@pytest.mark.parametrize("arr", _test_arrays, ids=_test_arrays_ids)
def test_vectorize_indirect(arr):
    def func(a):
        return a + 1

    vec_func = vectorize(func)

    def py_func(a):
        return vec_func(a)

    jit_func = njit(py_func, parallel=True)

    arr = np.array(arr)
    assert_equal(_vectorize_reference(func, arr), jit_func(arr))


@pytest.mark.parametrize(
    "arr",
    [
        np.array([[1, 2], [3, 4]]),
        np.array([[1, 2], [3, 4]]).T,
    ],
)
def test_fortran_layout(arr):
    def py_func(a):
        return a.T

    jit_func = njit(py_func)

    assert_equal(py_func(arr), jit_func(arr))


def test_contigious_layout_opt1():
    def py_func(a):
        return a[0, 1]

    jit_func = njit(py_func)

    a = np.array([[1, 2], [3, 4]])
    b = a.T

    layoutStr = "strided<[?, ?], offset: ?>"
    with print_pass_ir([], ["MakeStridedLayoutPass"]):
        assert_equal(py_func(a), jit_func(a))
        ir = get_print_buffer()
        assert ir.count(layoutStr) == 0, ir

    with print_pass_ir([], ["MakeStridedLayoutPass"]):
        assert_equal(py_func(b), jit_func(b))
        ir = get_print_buffer()
        assert ir.count(layoutStr) != 0, ir


def test_contigious_layout_opt2():
    def py_func(s, a):
        return a[s, 1]

    jit_func = njit(py_func)

    a = np.array([[1, 2, 3], [4, 5, 6]])
    b = a.T
    s = slice(2, 3)

    layoutStr = "strided<[?, ?], offset: ?>"
    with print_pass_ir([], ["MakeStridedLayoutPass"]):
        assert_equal(py_func(s, a), jit_func(s, a))
        ir = get_print_buffer()
        assert ir.count(layoutStr) == 0, ir

    with print_pass_ir([], ["MakeStridedLayoutPass"]):
        assert_equal(py_func(s, b), jit_func(s, b))
        ir = get_print_buffer()
        assert ir.count(layoutStr) != 0, ir


@pytest.mark.skip(reason="Layout type inference need rework")
def test_contigious_layout_return():
    def py_func1():
        return np.ones((2, 3), np.float32).T

    jit_func1 = njit(py_func1)

    def py_func2(a):
        return a

    jit_func2 = njit(py_func2)

    def py_func3():
        a = jit_func1()
        return jit_func2(a)

    jit_func3 = njit(py_func3)

    assert_equal(py_func3(), jit_func3())


@parametrize_function_variants(
    "a",
    [
        # 'np.array(1)', TODO zero rank arrays
        # 'np.array(2.5)',
        "np.array([])",
        "np.array([1,2,3])",
        "np.array([[1,2,3]])",
        "np.array([[1,2],[3,4],[5,6]])",
    ],
)
def test_atleast2d(a):
    def py_func(a):
        return np.atleast_2d(a)

    jit_func = njit(py_func)
    assert_equal(py_func(a), jit_func(a))


_test_reshape_test_array = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
_test_reshape_test_arrays = [
    _test_reshape_test_array,
    _test_reshape_test_array.reshape((2, 6)),
    _test_reshape_test_array.reshape((2, 3, 2)),
]


@parametrize_function_variants(
    "py_func",
    [
        "lambda a: a.reshape(a.size)",
        "lambda a: a.reshape((a.size,))",
        "lambda a: a.reshape((a.size,1))",
        "lambda a: a.reshape((1, a.size))",
        "lambda a: a.reshape(1, a.size)",
        "lambda a: a.reshape((1, a.size, 1))",
        # "lambda a: a.reshape((-1, a.size, 1))",
        # "lambda a: a.reshape((1, -1, 1))",
        # "lambda a: a.reshape((1, a.size, -1))",
        "lambda a: a.reshape(1, a.size, 1)",
        # "lambda a: a.reshape(-1, a.size, 1)",
        # "lambda a: a.reshape(1, -1, 1)",
        # "lambda a: a.reshape(1, a.size, -1)",
        "lambda a: np.reshape(a, a.size)",
        "lambda a: np.reshape(a, (a.size,))",
        "lambda a: np.reshape(a, (a.size,1))",
        "lambda a: np.reshape(a, (1, a.size))",
        "lambda a: np.reshape(a, (1, a.size, 1))",
    ],
)
@pytest.mark.parametrize("array", _test_reshape_test_arrays)
def test_reshape(py_func, array):
    jit_func = njit(py_func)
    assert_equal(py_func(array), jit_func(array))


@pytest.mark.xfail(reason="numba: reshape() supports contiguous array only")
def test_reshape_non_contiguous():
    def py_func(a):
        return a.reshape(4)

    jit_func = njit(py_func)
    array = np.arange(16).reshape((4, 4))[1:3, 1:3]
    assert_equal(py_func(array), jit_func(array))


@parametrize_function_variants(
    "py_func",
    [
        # 'lambda a: a.flat', TODO: flat support
        "lambda a: a.flatten()",
        "lambda a: np.ravel(a)",
    ],
)
@pytest.mark.parametrize("array", _test_reshape_test_arrays)
def test_flatten(py_func, array):
    jit_func = njit(py_func)
    assert_equal(py_func(array), jit_func(array))


@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b: ()",
        "lambda a, b: (a,b)",
        "lambda a, b: ((a,b),(a,a),(b,b),())",
    ],
)
@pytest.mark.parametrize(
    "a,b",
    itertools.product(
        *(([1, 2.5, np.array([1, 2, 3]), np.array([4.5, 6.7, 8.9])],) * 2)
    ),
)
def test_tuple_ret(py_func, a, b):
    jit_func = njit(py_func)
    assert_equal(py_func(a, b), jit_func(a, b))


@pytest.mark.parametrize(
    "arrays",
    [
        ([1, 2, 3], [4, 5, 6]),
        ([[1, 2], [3, 4]], [[5, 6], [7, 8]]),
        ([[[1], [2]], [[3], [4]]], [[[5], [6]], [[7], [8]]]),
        ([1, 2, 3], [4, 5, 6], [7, 8, 9]),
        ([1, 2], [3, 4], [5, 6], [7, 8]),
    ],
)
@pytest.mark.parametrize("axis", [0, 1, 2])  # TODO: None
def test_concat(arrays, axis):
    arr = tuple(np.array(a) for a in arrays)
    num_dims = len(arr[0].shape)
    if axis >= num_dims:
        pytest.skip()  # TODO: unselect
    num_arrays = len(arrays)
    if num_arrays == 2:

        def py_func(arr1, arr2):
            return np.concatenate((arr1, arr2), axis=axis)

    elif num_arrays == 3:

        def py_func(arr1, arr2, arr3):
            return np.concatenate((arr1, arr2, arr3), axis=axis)

    elif num_arrays == 4:

        def py_func(arr1, arr2, arr3, arr4):
            return np.concatenate((arr1, arr2, arr3, arr4), axis=axis)

    else:
        assert False
    jit_func = njit(py_func)
    assert_equal(py_func(*arr), jit_func(*arr))


@parametrize_function_variants(
    "py_func",
    [
        "lambda a: np.vstack(a)",
        "lambda a: np.hstack(a)",
        "lambda a: np.dstack(a)",
    ],
)
@parametrize_function_variants(
    "get_args",
    [
        # "lambda a, b, c: (a)", TODO: not supported by numba
        "lambda a, b, c: ((a,))",
        "lambda a, b, c: (a, b)",
        "lambda a, b, c: (a, b, c)",
    ],
)
@pytest.mark.parametrize("shape", [(2, 3, 4), (2, 3, 4, 5), (2, 3, 4, 5, 6)])
def test_xstack(py_func, get_args, shape):
    size = math.prod(shape)
    dtype = np.int32

    start = 0
    a = np.arange(start=start, stop=start + size, dtype=dtype).reshape(shape)

    start += size
    b = np.arange(start=start, stop=start + size, dtype=dtype).reshape(shape)

    start += size
    c = np.arange(start=start, stop=start + size, dtype=dtype).reshape(shape)

    jit_func = njit(py_func)

    args = get_args(a, b, c)
    assert_equal(py_func(args), jit_func(args))


@parametrize_function_variants(
    "py_func",
    [
        "lambda a: np.triu(a)",
        "lambda a: np.triu(a, 1)",
        "lambda a: np.triu(a, k=-2)",
        "lambda a: np.tril(a)",
        "lambda a: np.tril(a, 1)",
        "lambda a: np.tril(a, k=-2)",
    ],
)
@pytest.mark.parametrize("shape", [(3, 4), (3, 4, 5), (3, 4, 5, 6)])
def test_xtri(py_func, shape):
    size = math.prod(shape)
    dtype = np.int32
    a = np.arange(size, dtype=dtype).reshape(shape)

    jit_func = njit(py_func)
    assert_equal(py_func(a), jit_func(a))


@pytest.mark.parametrize(
    "arr",
    [
        np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=np.int32),
        np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype=np.float32),
        np.array([True, False, True, True, False, True, True, True]),
    ],
)
@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b, c, d: a[b:c]",
        "lambda a, b, c, d: a[3:c]",
        "lambda a, b, c, d: a[b:4]",
        "lambda a, b, c, d: a[3:4]",
        "lambda a, b, c, d: a[1:-2]",
        "lambda a, b, c, d: a[b:c:d]",
        "lambda a, b, c, d: a[b:c:1]",
        "lambda a, b, c, d: a[b:c:2]",
        "lambda a, b, c, d: a[3:4:2]",
    ],
)
def test_slice1(arr, py_func):
    jit_func = njit(py_func)
    assert_equal(py_func(arr, 3, 4, 2), jit_func(arr, 3, 4, 2))


def test_slice2():
    def py_func(a, i, j, k):
        a1 = a[1]
        a2 = a1[2]
        return a2[3]

    arr = np.arange(3 * 4 * 5).reshape((3, 4, 5))
    jit_func = njit(py_func)
    assert_equal(py_func(arr, 1, 2, 3), jit_func(arr, 1, 2, 3))


@pytest.mark.parametrize("count", [0, 1, 5, 7, 8, 16, 17, 32])
def test_slice3(count):
    def py_func(A):
        B = A[::3]
        for i in range(len(B)):
            B[i] = i
        return B

    arr = np.zeros(count)
    jit_func = njit(py_func)
    assert_equal(py_func(arr.copy()[::2]), jit_func(arr.copy()[::2]))


@pytest.mark.parametrize("s", [slice(1), slice(2, 3), slice(3, 4, 2)])
def test_slice_arg(s):
    def py_func(a, s):
        return a[s]

    jit_func = njit(py_func)
    arr = np.arange(10)
    assert_equal(py_func(arr, s), jit_func(arr, s))


def test_multidim_slice():
    def py_func(a, b):
        return a[1, b, :]

    jit_func = njit(py_func)

    a = np.array([[[1], [2], [3]], [[4], [5], [6]]])
    assert_equal(py_func(a, 0), jit_func(a, 0))


def test_size_ret():
    def py_func(a, b):
        return a.size / b

    jit_func = njit(py_func)

    a = np.array([[[1], [2], [3]], [[4], [5], [6]]])
    assert_equal(py_func(a, 3), jit_func(a, 3))


def test_alias1():
    def py_func():
        a = np.zeros(7)
        b = a[2:4]
        b[1] = 5
        return a

    jit_func = njit(py_func)

    a = np.ones(1)

    assert_equal(py_func(), jit_func())


def test_alias2():
    def py_func(n):
        b = np.zeros((n, n))
        a = b[0]
        for j in range(n):
            a[j] = j + 1
        return b.sum()

    jit_func = njit(py_func)

    assert_equal(py_func(4), jit_func(4))


def test_inplace_alias1():
    def py_func(a):
        a += 1
        a[:] = 3

    jit_func = njit(py_func)

    a = np.ones(1)

    py_arg = a.copy()
    jit_arg = a.copy()
    py_func(py_arg)
    jit_func(jit_arg)
    assert_equal(py_arg, jit_arg)


def test_inplace_alias2():
    def py_func(a, b):
        a[:] += b

    jit_func = njit(py_func)

    a = np.ones(1)
    b = a + 2

    py_arg = a.copy()
    jit_arg = a.copy()
    py_func(py_arg, b)
    jit_func(jit_arg, b)
    assert_equal(py_arg, jit_arg)


def test_inplace1():
    def py_func(a):
        a += 1

    jit_func = njit(py_func)

    a = np.arange(25, dtype=np.int32)

    py_arg = a.copy()
    jit_arg = a.copy()
    py_func(py_arg)
    jit_func(jit_arg)
    assert_equal(py_arg, jit_arg)


def test_inplace2():
    def py_func(a):
        for i in range(len(a)):
            a[i] += 1

    jit_func = njit(py_func)

    a = np.arange(25, dtype=np.int32)

    py_arg = a.copy()
    jit_arg = a.copy()
    py_func(py_arg)
    jit_func(jit_arg)
    assert_equal(py_arg, jit_arg)


def test_inplace3():
    def py_func(a):
        a += 1

        for i in range(len(a)):
            a[i] += 2

        a += 3

    jit_func = njit(py_func)

    a = np.arange(25, dtype=np.int32)

    py_arg = a.copy()
    jit_arg = a.copy()
    py_func(py_arg)
    jit_func(jit_arg)
    assert_equal(py_arg, jit_arg)


@pytest.mark.parametrize(
    "arr",
    [
        # np.empty(0), TODO: Need dispatchef fixes for FixedArray
        # np.ones(1),
        np.arange(12),
    ],
)
def test_array_loop1(arr):
    def py_func(arr):
        res = 0
        for a in arr:
            res += a

        return res

    jit_func = njit(py_func)

    with print_pass_ir([], ["PromoteWhilePass"]):
        jit_func = njit(py_func)
        assert_equal(py_func(arr), jit_func(arr))
        ir = get_print_buffer()
        assert ir.count("scf.for") > 0, ir


@pytest.mark.parametrize(
    "arr", [np.arange(12).reshape(3, 4), np.arange(60).reshape(3, 4, 5)]
)
def test_array_loop2(arr):
    def py_func(arr):
        res = 0
        for a in arr:
            res += np.sum(a)

        return res

    jit_func = njit(py_func)

    with print_pass_ir([], ["PromoteWhilePass"]):
        jit_func = njit(py_func)
        assert_equal(py_func(arr), jit_func(arr))
        ir = get_print_buffer()
        assert ir.count("scf.for") > 0, ir


@pytest.mark.parametrize("a", [np.array([[1, 2], [4, 5]])])
@pytest.mark.parametrize("b", [True, False])
def test_tensor_if(a, b):
    def py_func(m, rowvar):
        m_arr = np.atleast_2d(m)
        if not rowvar:
            m_arr = m_arr.T
        return m_arr

    jit_func = njit(py_func)

    assert_equal(py_func(a, b), jit_func(a, b))


def test_static_dim_call():
    def py_func1(a):
        return a.shape[0]

    jit_func1 = njit(py_func1)

    def py_func2(a, b):
        return py_func1(a), py_func1(b)

    def py_func3(a, b):
        return jit_func1(a), jit_func1(b)

    jit_func3 = njit(py_func3)

    a = np.empty(1)
    b = np.empty(10)

    assert_equal(py_func2(a, b), jit_func3(a, b))
    # assert_equal(py_func3(a, b), jit_func3(a, b)) TODO: caching issue


def test_copy_self_alias():
    def py_func(N):
        a = np.arange(N)
        a[:] += 3 * np.flip(a)
        return a

    jit_func = njit(py_func)

    N = 1000
    assert_equal(py_func(N), jit_func(N))


def _cov(m, y=None, rowvar=True, bias=False, ddof=None):
    return np.cov(m, y, rowvar, bias, ddof)


_rnd = np.random.RandomState(42)


@parametrize_function_variants(
    "m",
    [
        "np.array([[0, 2], [1, 1], [2, 0]]).T",
        "_rnd.randn(100).reshape(5, 20)",
        "np.asfortranarray(np.array([[0, 2], [1, 1], [2, 0]]).T)",
        # "_rnd.randn(100).reshape(5, 20)[:, ::2]", TODO: investigate
        "np.array([0.3942, 0.5969, 0.7730, 0.9918, 0.7964])",
        # 'np.full((4, 5), fill_value=True)', TODO
        "np.array([np.nan, 0.5969, -np.inf, 0.9918, 0.7964])",
        "np.linspace(-3, 3, 33).reshape(33, 1)",
        # non-array inputs
        "((0.1, 0.2), (0.11, 0.19), (0.09, 0.21))",  # UniTuple
        "((0.1, 0.2), (0.11, 0.19), (0.09j, 0.21j))",  # Tuple
        "(-2.1, -1, 4.3)",
        "(1, 2, 3)",
        "[4, 5, 6]",
        "((0.1, 0.2, 0.3), (0.1, 0.2, 0.3))",
        "[(1, 2, 3), (1, 3, 2)]",
        "3.142",
        # '((1.1, 2.2, 1.5),)',
        # empty data structures
        "np.array([])",
        "np.array([]).reshape(0, 2)",
        "np.array([]).reshape(2, 0)",
        "()",
    ],
)
def test_cov_basic(m):
    if isinstance(m, (list, float)) or len(m) == 0 or np.iscomplexobj(m):
        pytest.xfail()
    py_func = _cov
    jit_func = njit(py_func)
    assert_allclose(py_func(m), jit_func(m), rtol=1e-15, atol=1e-15)


_cov_inputs_m = _rnd.randn(105).reshape(15, 7)


@pytest.mark.parametrize("m", [_cov_inputs_m])
@pytest.mark.parametrize("y", [None, _cov_inputs_m[::-1]])
@pytest.mark.parametrize("rowvar", [False, True])
@pytest.mark.parametrize("bias", [False, True])
@pytest.mark.parametrize("ddof", [None, -1, 0, 1, 3.0, True])
def test_cov_explicit_arguments(m, y, rowvar, bias, ddof):
    py_func = _cov
    jit_func = njit(py_func)
    assert_allclose(
        py_func(m=m, y=y, rowvar=rowvar, bias=bias, ddof=ddof),
        jit_func(m=m, y=y, rowvar=rowvar, bias=bias, ddof=ddof),
        rtol=1e-14,
        atol=1e-14,
    )


@parametrize_function_variants(
    "m, y, rowvar",
    [
        "(np.array([-2.1, -1, 4.3]), np.array([3, 1.1, 0.12]), True)",
        "(np.array([1, 2, 3]), np.array([1j, 2j, 3j]), True)",
        "(np.array([1j, 2j, 3j]), np.array([1, 2, 3]), True)",
        "(np.array([1, 2, 3]), np.array([1j, 2j, 3]), True)",
        "(np.array([1j, 2j, 3]), np.array([1, 2, 3]), True)",
        # "(np.array([]), np.array([]), True)", TODO: investigate
        "(1.1, 2.2, True)",
        "(_rnd.randn(10, 3), np.array([-2.1, -1, 4.3]).reshape(1, 3) / 10, True)",
        "(np.array([-2.1, -1, 4.3]), np.array([[3, 1.1, 0.12], [3, 1.1, 0.12]]), True)",
        # '(np.array([-2.1, -1, 4.3]), np.array([[3, 1.1, 0.12], [3, 1.1, 0.12]]), False)',
        "(np.array([[3, 1.1, 0.12], [3, 1.1, 0.12]]), np.array([-2.1, -1, 4.3]), True)",
        # '(np.array([[3, 1.1, 0.12], [3, 1.1, 0.12]]), np.array([-2.1, -1, 4.3]), False)',
    ],
)
def test_cov_edge_cases(m, y, rowvar):
    if (
        not isinstance(m, np.ndarray)
        or not isinstance(y, np.ndarray)
        or np.iscomplexobj(m)
        or np.iscomplexobj(y)
    ):
        pytest.xfail()
    py_func = _cov
    jit_func = njit(py_func)
    assert_allclose(
        py_func(m=m, y=y, rowvar=rowvar),
        jit_func(m=m, y=y, rowvar=rowvar),
        rtol=1e-14,
        atol=1e-14,
    )


@pytest.mark.parametrize(
    "arr",
    [
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9], dtype=np.int32).reshape((3, 3)),
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9], dtype=np.float32).reshape((3, 3)),
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], dtype=np.int32).reshape((5, 2)),
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], dtype=np.float32).reshape((5, 2)),
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], dtype=np.int32).reshape((5, 2)).T,
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], dtype=np.float32).reshape((5, 2)).T,
    ],
)
@pytest.mark.parametrize("parallel", [False, True])
def test_mean_loop(arr, parallel):
    def py_func(data):
        tdata = data.T
        m = np.empty(tdata.shape[0])
        for i in numba.prange(tdata.shape[0]):
            m[i] = np.mean(tdata[i])
        return m

    jit_func = njit(py_func, parallel=parallel)
    assert_equal(py_func(arr), jit_func(arr))


@pytest.mark.parametrize(
    "arr",
    [
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9], dtype=np.int32).reshape((3, 3)),
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9], dtype=np.float32).reshape((3, 3)),
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], dtype=np.int32).reshape((5, 2)),
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], dtype=np.float32).reshape((5, 2)),
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], dtype=np.int32).reshape((5, 2)).T,
        np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 0], dtype=np.float32).reshape((5, 2)).T,
        make_regression(n_samples=2**10, n_features=2**7, random_state=0)[0],
    ],
)
@pytest.mark.parametrize("parallel", [False, True])
def test_mean_loop_cov(arr, parallel):
    def py_func(data):
        tdata = data.T
        m = np.empty(tdata.shape[0])
        for i in numba.prange(tdata.shape[0]):
            m[i] = np.mean(tdata[i])
        c = data - m
        v = np.cov(c.T)
        return c, v

    jit_func = njit(py_func, parallel=parallel)
    c1, v1 = py_func(arr)
    c2, v2 = jit_func(arr)
    assert_allclose(c1, c2, rtol=1e-15, atol=1e-11)
    assert_allclose(v1, v2, rtol=1e-15, atol=1e-11)


@pytest.mark.parametrize(
    "N,k",
    [
        (1, 0),
        (2, -1),
        (2, 0),
        (2, 1),
        (3, -2),
        (3, -1),
        (3, 0),
        (3, 1),
        (3, 2),
    ],
)
@pytest.mark.parametrize("dtype", [np.int32, np.int64, np.float32, np.float64])
def test_eye1(N, k, dtype):
    def py_func(N, k):
        return np.eye(N=N, k=k, dtype=dtype)

    jit_func = njit(py_func)
    assert_equal(py_func(N, k), jit_func(N, k))


@pytest.mark.parametrize(
    "N,M,k",
    [
        (2, 3, -1),
        (2, 3, 0),
        (2, 3, 1),
        (3, 2, -1),
        (3, 2, 0),
        (3, 2, 1),
    ],
)
def test_eye2(N, M, k):
    def py_func(N, M, k):
        return np.eye(N, M, k)

    jit_func = njit(py_func)
    assert_equal(py_func(N, M, k), jit_func(N, M, k))


_matmul_inputs_vars = [
    ([], []),
    (np.empty((0,)), np.empty((0,))),
    (np.empty((0, 0)), np.empty((0, 0))),
    ([2], [3]),
    ([2, 3], [4, 5]),
    ([2, 3], [[2, 3], [4, 5]]),
    ([1, 2, 3], [[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
    ([[2, 3], [4, 5]], [2, 3]),
    ([[1, 2, 3], [4, 5, 6], [7, 8, 9]], [1, 2, 3]),
    ([[2, 3], [4, 5]], [[2, 3], [4, 5]]),
    (np.arange(4 * 5).reshape(4, 5), np.arange(5)),
    (np.arange(40 * 50).reshape(40, 50), np.arange(50)),
]


@parametrize_function_variants(
    "py_func",
    [
        # 'lambda a, b: np.matmul(a, b)',
        "lambda a, b: a @ b",
    ],
)
@pytest.mark.parametrize(
    "a,b", _matmul_inputs_vars
)  # ids=list(map(str, _matmul_inputs_vars))
@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.complex64, np.complex128])
def test_matmul1(py_func, a, b, dtype):
    a = np.array(a, dtype=dtype)
    b = np.array(b, dtype=dtype)

    # TODO: Some issue with caching
    # jit_func = njit(py_func)
    jit_func = orig_njit(py_func)
    assert_allclose(py_func(a, b), jit_func(a, b), rtol=1e-4, atol=1e-7)


@parametrize_function_variants(
    "py_func",
    [
        "lambda a, b: (a @ b) @ a",
    ],
)
@pytest.mark.parametrize(
    "a,b",
    [
        (np.arange(4 * 5).reshape(4, 5), np.arange(5)),
        (np.arange(20 * 25).reshape(20, 25), np.arange(25)),
        (np.arange(4000 * 5000).reshape(4000, 5000), np.arange(5000)),
    ],
)
@pytest.mark.parametrize("dtype", [np.float32, np.float64])
def test_matmul2(py_func, a, b, dtype):
    a = np.array(a, dtype=dtype)
    b = np.array(b, dtype=dtype)
    jit_func = njit(py_func)
    assert_allclose(py_func(a, b), jit_func(a, b), rtol=1e-4, atol=1e-7)


def test_batchnorm():
    def py_func(x, eps=1e-5):
        # mean = np.mean(x, axis=0, keepdims=True)
        mean = np.empty(x.shape, dtype=x.dtype)
        mean[:] = np.sum(x, axis=0) / x.shape[0]
        # std = np.std(x, axis=0, keepdims=True)
        std = np.empty(x.shape, dtype=x.dtype)
        std[:] = np.sqrt(np.sum((x - mean) ** 2, axis=0) / x.shape[0])
        return (x - mean) / np.sqrt(std + eps)

    jit_func = njit(py_func, parallel=True)

    from numpy.random import default_rng

    rng = default_rng(42)
    N, W, H, C = 8, 14, 14, 32
    input = rng.random((N, H, W, C), dtype=np.float32)
    assert_allclose(py_func(input), jit_func(input), rtol=1e-4, atol=1e-7)
