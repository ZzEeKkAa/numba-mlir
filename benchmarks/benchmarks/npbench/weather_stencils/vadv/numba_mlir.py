# SPDX-FileCopyrightText: 2014-2021 ETH Zurich
# SPDX-FileCopyrightText: 2007 Free Software Foundation, Inc. <https://fsf.org/>
# SPDX-FileCopyrightText: 2021 ETH Zurich and the NPBench authors
# SPDX-FileCopyrightText: 2022 - 2023 Intel Corporation
#
# SPDX-License-Identifier: GPL-3.0-or-later

from .common import initialize, get_impl, parameters, presets
import numba_mlir.mlir.benchmarking
from numba_mlir.mlir.benchmarking import (
    get_numba_mlir_context,
    get_numpy_context,
    assert_allclose_recursive,
)


class Benchmark(numba_mlir.mlir.benchmarking.BenchmarkBase):
    params = presets
    param_names = ["preset"]

    def get_func(self):
        return get_impl(get_numba_mlir_context())

    def initialize(self, preset):
        self.is_expected_failure = self.is_validate
        preset = parameters[preset]
        return initialize(**preset)

    def validate(self, args, res):
        np_ver = get_impl(get_numpy_context())
        np_res = np_ver(*args)
        assert_allclose_recursive(res, np_res)
