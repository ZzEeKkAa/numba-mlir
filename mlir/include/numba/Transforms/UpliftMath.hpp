// SPDX-FileCopyrightText: 2021 - 2022 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include <memory>

namespace mlir {
class MLIRContext;
class RewritePatternSet;
class Pass;
} // namespace mlir

namespace numba {
void populateUpliftMathPatterns(mlir::RewritePatternSet &patterns);

/// This pass tries to uplift libm-style func call to math dialect ops.
std::unique_ptr<mlir::Pass> createUpliftMathPass();
} // namespace numba
