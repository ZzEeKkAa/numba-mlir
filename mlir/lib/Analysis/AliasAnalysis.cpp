// SPDX-FileCopyrightText: 2022 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "numba/Analysis/AliasAnalysis.hpp"

#include <mlir/Interfaces/FunctionInterfaces.h>

/// Check if value is function argument.
static bool isFuncArg(mlir::Value val) {
  auto blockArg = mlir::dyn_cast<mlir::BlockArgument>(val);
  if (!blockArg)
    return false;

  return mlir::isa_and_nonnull<mlir::FunctionOpInterface>(
      blockArg.getOwner()->getParentOp());
}

/// Check if value has "restrict" attribute. Value must be a function argument.
static bool isRestrict(mlir::Value val) {
  auto blockArg = val.cast<mlir::BlockArgument>();
  auto func =
      mlir::cast<mlir::FunctionOpInterface>(blockArg.getOwner()->getParentOp());
  return !!func.getArgAttr(blockArg.getArgNumber(),
                           numba::getRestrictArgName());
}

mlir::AliasResult numba::LocalAliasAnalysis::aliasImpl(mlir::Value lhs,
                                                       mlir::Value rhs) {
  if (lhs == rhs)
    return mlir::AliasResult::MustAlias;

  // Assume no aliasing if both values are function arguments and any of them
  // have restrict attr.
  if (isFuncArg(lhs) && isFuncArg(rhs))
    if (isRestrict(lhs) || isRestrict(rhs))
      return mlir::AliasResult::NoAlias;

  return mlir::LocalAliasAnalysis::aliasImpl(lhs, rhs);
}

llvm::StringRef numba::getRestrictArgName() { return "numba.restrict"; }
