// SPDX-FileCopyrightText: 2021 - 2022 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "numba/Transforms/UpliftMath.hpp"

#include <mlir/Dialect/Arith/IR/Arith.h>
#include <mlir/Dialect/Complex/IR/Complex.h>
#include <mlir/Dialect/Func/IR/FuncOps.h>
#include <mlir/Dialect/Math/IR/Math.h>
#include <mlir/IR/PatternMatch.h>
#include <mlir/Pass/Pass.h>
#include <mlir/Transforms/GreedyPatternRewriteDriver.h>

template <typename Op>
static mlir::Operation *replaceOp1(mlir::OpBuilder &builder, mlir::Location loc,
                                   mlir::ValueRange args) {
  if (args.size() != 1)
    return nullptr;

  return builder.create<Op>(loc, args.front());
}

template <typename Op>
static mlir::Operation *replaceOp2(mlir::OpBuilder &builder, mlir::Location loc,
                                   mlir::ValueRange args) {
  if (args.size() != 2)
    return nullptr;

  return builder.create<Op>(loc, args[0], args[1]);
}

namespace {
struct UpliftMathCalls : public mlir::OpRewritePattern<mlir::func::CallOp> {
  using OpRewritePattern::OpRewritePattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::func::CallOp op,
                  mlir::PatternRewriter &rewriter) const override {
    auto funcName = op.getCallee();
    if (funcName.empty())
      return mlir::failure();

    auto isNotValidType = [](mlir::Type t) { return !t.isIntOrFloat(); };

    if (llvm::any_of(op.getOperandTypes(), isNotValidType) ||
        op.getNumResults() != 1 ||
        llvm::any_of(op.getResultTypes(), isNotValidType))
      return mlir::failure();

    llvm::StringRef funcNameFPref =
        (funcName.front() == 'f' ? funcName.drop_front() : llvm::StringRef{});

    llvm::StringRef funcNameFPost =
        (funcName.back() == 'f' ? funcName.drop_back() : llvm::StringRef{});

    using func_t = mlir::Operation *(*)(mlir::OpBuilder &, mlir::Location,
                                        mlir::ValueRange);
    const std::pair<llvm::StringRef, func_t> handlers[] = {
        {"floor", &replaceOp1<mlir::math::FloorOp>},
        {"log", &replaceOp1<mlir::math::LogOp>},
        {"sqrt", &replaceOp1<mlir::math::SqrtOp>},
        {"exp", &replaceOp1<mlir::math::ExpOp>},
        {"sin", &replaceOp1<mlir::math::SinOp>},
        {"cos", &replaceOp1<mlir::math::CosOp>},
        {"erf", &replaceOp1<mlir::math::ErfOp>},
        {"tanh", &replaceOp1<mlir::math::TanhOp>},
        {"atan2", &replaceOp2<mlir::math::Atan2Op>},
    };

    for (auto &handler : handlers) {
      auto name = handler.first;
      if (name == funcName || name == funcNameFPref || name == funcNameFPost) {
        auto res = handler.second(rewriter, op.getLoc(), op.getOperands());
        if (!res)
          return mlir::failure();

        assert(res->getNumResults() == op->getNumResults());
        rewriter.replaceOp(op, res->getResults());
        return mlir::success();
      }
    }
    return mlir::failure();
  }
};

struct UpliftFabsCalls : public mlir::OpRewritePattern<mlir::func::CallOp> {
  using OpRewritePattern::OpRewritePattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::func::CallOp op,
                  mlir::PatternRewriter &rewriter) const override {
    auto funcName = op.getCallee();
    if (funcName.empty())
      return mlir::failure();

    if (funcName != "fabs" && funcName != "fabsf")
      return mlir::failure();

    auto isNotValidType = [](mlir::Type t) {
      return !t.isa<mlir::FloatType>();
    };

    if (op.getNumResults() != 1 || op.getNumOperands() != 1 ||
        llvm::any_of(op.getOperandTypes(), isNotValidType) ||
        llvm::any_of(op.getResultTypes(), isNotValidType))
      return mlir::failure();

    rewriter.replaceOpWithNewOp<mlir::math::AbsFOp>(op,
                                                    op.getOperands().front());
    return mlir::success();
  }
};

struct UpliftCabsCalls : public mlir::OpRewritePattern<mlir::func::CallOp> {
  using OpRewritePattern::OpRewritePattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::func::CallOp op,
                  mlir::PatternRewriter &rewriter) const override {
    auto funcName = op.getCallee();
    if (funcName.empty())
      return mlir::failure();

    if (funcName != "cabs" && funcName != "cabsf")
      return mlir::failure();

    if (op.getNumResults() != 1 || op.getNumOperands() != 1)
      return mlir::failure();

    auto val = op.getOperands().front();
    auto srcType = val.getType().dyn_cast<mlir::ComplexType>();

    if (!srcType || srcType.getElementType() != op.getResult(0).getType())
      return mlir::failure();

    rewriter.replaceOpWithNewOp<mlir::complex::AbsOp>(
        op, srcType.getElementType(), val);
    return mlir::success();
  }
};

struct UpliftComplexCalls : public mlir::OpRewritePattern<mlir::func::CallOp> {
  using OpRewritePattern::OpRewritePattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::func::CallOp op,
                  mlir::PatternRewriter &rewriter) const override {
    auto funcName = op.getCallee();
    if (funcName.empty())
      return mlir::failure();

    if (op.getNumResults() != 1 || op.getNumOperands() != 1)
      return mlir::failure();

    auto val = op.getOperands().front();
    auto srcType = val.getType().dyn_cast<mlir::ComplexType>();

    if (!srcType || srcType != op.getResult(0).getType())
      return mlir::failure();

    llvm::StringRef funcNameF =
        (funcName.front() == 'f' ? funcName.drop_front() : llvm::StringRef{});

    using func_t = mlir::Operation *(*)(mlir::OpBuilder &, mlir::Location,
                                        mlir::ValueRange);
    const std::pair<llvm::StringRef, func_t> handlers[] = {
        {"cexp", &replaceOp1<mlir::complex::ExpOp>},
        {"csqrt", &replaceOp1<mlir::complex::SqrtOp>},
    };

    for (auto &handler : handlers) {
      auto name = handler.first;
      if (name == funcName || name == funcNameF) {
        auto res = handler.second(rewriter, op.getLoc(), op.getOperands());
        if (!res)
          return mlir::failure();

        assert(res->getNumResults() == op->getNumResults());
        rewriter.replaceOp(op, res->getResults());
        return mlir::success();
      }
    }

    return mlir::success();
  }
};

struct UpliftMinMax : public mlir::OpRewritePattern<mlir::arith::SelectOp> {
  using OpRewritePattern::OpRewritePattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::arith::SelectOp op,
                  mlir::PatternRewriter &rewriter) const override {
    auto type = op.getType();
    if (!type.isIntOrIndexOrFloat())
      return mlir::failure();

    auto lhs = op.getTrueValue();
    auto rhs = op.getFalseValue();
    auto cond = op.getCondition();
    if (mlir::isa<mlir::FloatType>(type)) {
      // TODO: clarify mlir minf/maxf wrt nans and singed zeros semantics

      auto cmp = cond.getDefiningOp<mlir::arith::CmpFOp>();
      if (!cmp || cmp.getLhs() != lhs || cmp.getRhs() != rhs)
        return mlir::failure();

      using Pred = mlir::arith::CmpFPredicate;
      auto pred = cmp.getPredicate();
      if (pred == Pred::OLT || pred == Pred::ULT) {
        rewriter.replaceOpWithNewOp<mlir::arith::MinimumFOp>(op, lhs, rhs);
      } else if (pred == Pred::OGT || pred == Pred::UGT) {
        rewriter.replaceOpWithNewOp<mlir::arith::MaximumFOp>(op, lhs, rhs);
      } else {
        return mlir::failure();
      }
    } else {
      auto cmp = cond.getDefiningOp<mlir::arith::CmpIOp>();
      if (!cmp || cmp.getLhs() != lhs || cmp.getRhs() != rhs)
        return mlir::failure();

      using Pred = mlir::arith::CmpIPredicate;
      auto pred = cmp.getPredicate();
      if (pred == Pred::slt) {
        rewriter.replaceOpWithNewOp<mlir::arith::MinSIOp>(op, lhs, rhs);
      } else if (pred == Pred::ult) {
        rewriter.replaceOpWithNewOp<mlir::arith::MinUIOp>(op, lhs, rhs);
      } else if (pred == Pred::sgt) {
        rewriter.replaceOpWithNewOp<mlir::arith::MaxSIOp>(op, lhs, rhs);
      } else if (pred == Pred::ugt) {
        rewriter.replaceOpWithNewOp<mlir::arith::MaxUIOp>(op, lhs, rhs);
      } else {
        return mlir::failure();
      }
    }
    return mlir::success();
  }
};

struct UpliftMathPass
    : public mlir::PassWrapper<UpliftMathPass, mlir::OperationPass<>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(UpliftMathPass)

  virtual void
  getDependentDialects(mlir::DialectRegistry &registry) const override {
    registry.insert<mlir::arith::ArithDialect>();
    registry.insert<mlir::complex::ComplexDialect>();
    registry.insert<mlir::func::FuncDialect>();
    registry.insert<mlir::math::MathDialect>();
  }

  void runOnOperation() override {
    mlir::RewritePatternSet patterns(&getContext());
    numba::populateUpliftMathPatterns(patterns);
    if (mlir::failed(mlir::applyPatternsAndFoldGreedily(getOperation(),
                                                        std::move(patterns))))
      return signalPassFailure();
  }
};
} // namespace

void numba::populateUpliftMathPatterns(mlir::RewritePatternSet &patterns) {
  patterns.insert<UpliftMathCalls, UpliftFabsCalls, UpliftCabsCalls,
                  UpliftMinMax, UpliftComplexCalls>(patterns.getContext());
}

std::unique_ptr<mlir::Pass> numba::createUpliftMathPass() {
  return std::make_unique<UpliftMathPass>();
}
