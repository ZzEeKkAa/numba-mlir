// SPDX-FileCopyrightText: 2021 - 2022 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "numba/Transforms/PromoteBoolMemref.hpp"

#include "numba/Dialect/numba_util/Dialect.hpp"
#include "numba/Transforms/TypeConversion.hpp"

#include <mlir/Dialect/Arith/IR/Arith.h>
#include <mlir/Dialect/MemRef/IR/MemRef.h>
#include <mlir/Pass/Pass.h>
#include <mlir/Transforms/DialectConversion.h>

namespace {

static bool isI1(mlir::Type type) { return type.isSignlessInteger(1); }

static bool isMemI1(mlir::Type type) {
  if (auto memref = type.dyn_cast<mlir::MemRefType>())
    return isI1(memref.getElementType());

  return false;
}

static std::optional<bool> checkOp(mlir::Operation *op) {
  if (llvm::any_of(op->getOperandTypes(), &isMemI1) ||
      llvm::any_of(op->getResultTypes(), &isMemI1))
    return false;

  return true;
}

class ConvertDimOp : public mlir::OpConversionPattern<mlir::memref::DimOp> {
public:
  using OpConversionPattern::OpConversionPattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::memref::DimOp op, mlir::memref::DimOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    rewriter.replaceOpWithNewOp<mlir::memref::DimOp>(op, adaptor.getSource(),
                                                     adaptor.getIndex());
    return mlir::success();
  }
};

class ConvertLoadOp : public mlir::OpConversionPattern<mlir::memref::LoadOp> {
public:
  using OpConversionPattern::OpConversionPattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::memref::LoadOp op,
                  mlir::memref::LoadOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto loc = op->getLoc();
    auto res = rewriter.create<mlir::memref::LoadOp>(loc, adaptor.getMemref(),
                                                     adaptor.getIndices());
    rewriter.replaceOpWithNewOp<mlir::arith::TruncIOp>(
        op, rewriter.getIntegerType(1), res);
    return mlir::success();
  }
};

class ConvertStoreOp : public mlir::OpConversionPattern<mlir::memref::StoreOp> {
public:
  using OpConversionPattern::OpConversionPattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::memref::StoreOp op,
                  mlir::memref::StoreOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto loc = op->getLoc();
    auto val = rewriter.create<mlir::arith::ExtUIOp>(
        loc, rewriter.getIntegerType(8), adaptor.getValue());
    rewriter.replaceOpWithNewOp<mlir::memref::StoreOp>(
        op, val, adaptor.getMemref(), adaptor.getIndices());
    return mlir::success();
  }
};

class ConvertAllocOp : public mlir::OpConversionPattern<mlir::memref::AllocOp> {
public:
  using OpConversionPattern::OpConversionPattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::memref::AllocOp op,
                  mlir::memref::AllocOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto *converter = getTypeConverter();
    auto resType = converter->convertType(op.getType())
                       .dyn_cast_or_null<mlir::MemRefType>();
    if (!resType)
      return mlir::failure();

    rewriter.replaceOpWithNewOp<mlir::memref::AllocOp>(
        op, resType, adaptor.getDynamicSizes(), adaptor.getSymbolOperands(),
        adaptor.getAlignmentAttr());
    return mlir::success();
  }
};

class ConvertAllocaOp
    : public mlir::OpConversionPattern<mlir::memref::AllocaOp> {
public:
  using OpConversionPattern::OpConversionPattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::memref::AllocaOp op,
                  mlir::memref::AllocaOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto *converter = getTypeConverter();
    auto resType = converter->convertType(op.getType())
                       .dyn_cast_or_null<mlir::MemRefType>();
    if (!resType)
      return mlir::failure();

    rewriter.replaceOpWithNewOp<mlir::memref::AllocaOp>(
        op, resType, adaptor.getDynamicSizes(), adaptor.getSymbolOperands(),
        adaptor.getAlignmentAttr());
    return mlir::success();
  }
};

class ConvertDeallocOp
    : public mlir::OpConversionPattern<mlir::memref::DeallocOp> {
public:
  using OpConversionPattern::OpConversionPattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::memref::DeallocOp op,
                  mlir::memref::DeallocOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    rewriter.replaceOpWithNewOp<mlir::memref::DeallocOp>(op,
                                                         adaptor.getMemref());
    return mlir::success();
  }
};

class ConvertCastOp : public mlir::OpConversionPattern<mlir::memref::CastOp> {
public:
  using OpConversionPattern::OpConversionPattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::memref::CastOp op,
                  mlir::memref::CastOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto *converter = getTypeConverter();
    auto resType = converter->convertType(op.getType())
                       .dyn_cast_or_null<mlir::MemRefType>();
    if (!resType)
      return mlir::failure();
    rewriter.replaceOpWithNewOp<mlir::memref::CastOp>(op, resType,
                                                      adaptor.getSource());
    return mlir::success();
  }
};

class ConvertSubviewOp
    : public mlir::OpConversionPattern<mlir::memref::SubViewOp> {
public:
  using OpConversionPattern::OpConversionPattern;

  mlir::LogicalResult
  matchAndRewrite(mlir::memref::SubViewOp op,
                  mlir::memref::SubViewOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto *converter = getTypeConverter();
    auto resType = converter->convertType(op.getType())
                       .dyn_cast_or_null<mlir::MemRefType>();
    if (!resType)
      return mlir::failure();
    rewriter.replaceOpWithNewOp<mlir::memref::SubViewOp>(
        op, resType, adaptor.getSource(), adaptor.getOffsets(),
        adaptor.getSizes(), adaptor.getStrides(), adaptor.getStaticOffsets(),
        adaptor.getStaticSizes(), adaptor.getStaticStrides());
    return mlir::success();
  }
};

class ConvertRetainOp
    : public mlir::OpConversionPattern<numba::util::RetainOp> {
public:
  using OpConversionPattern::OpConversionPattern;

  mlir::LogicalResult
  matchAndRewrite(numba::util::RetainOp op,
                  numba::util::RetainOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto *converter = getTypeConverter();
    auto resType = converter->convertType(op.getType())
                       .dyn_cast_or_null<mlir::MemRefType>();
    if (!resType)
      return mlir::failure();
    rewriter.replaceOpWithNewOp<numba::util::RetainOp>(op, resType,
                                                       adaptor.getSource());
    return mlir::success();
  }
};
} // namespace

void numba::populatePromoteBoolMemrefConversionRewritesAndTarget(
    mlir::TypeConverter &typeConverter, mlir::RewritePatternSet &patterns,
    mlir::ConversionTarget &target) {
  auto context = patterns.getContext();
  auto i8 = mlir::IntegerType::get(context, 8);
  typeConverter.addConversion(
      [i8](mlir::MemRefType type) -> std::optional<mlir::Type> {
        auto elemType = type.getElementType();
        if (isI1(elemType))
          return type.clone(i8);

        return std::nullopt;
      });

  target.addDynamicallyLegalDialect<mlir::memref::MemRefDialect>(&checkOp);
  target.addDynamicallyLegalOp<numba::util::RetainOp>(&checkOp);

  patterns.insert<ConvertDimOp, ConvertLoadOp, ConvertStoreOp, ConvertAllocOp,
                  ConvertAllocaOp, ConvertDeallocOp, ConvertCastOp,
                  ConvertSubviewOp, ConvertRetainOp>(typeConverter, context);
}

namespace {
struct PromoteBoolMemrefPass
    : public mlir::PassWrapper<PromoteBoolMemrefPass, mlir::OperationPass<>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(PromoteBoolMemrefPass)

  virtual void
  getDependentDialects(mlir::DialectRegistry &registry) const override {
    registry.insert<mlir::arith::ArithDialect>();
    registry.insert<mlir::memref::MemRefDialect>();
  }

  void runOnOperation() override {
    auto &context = getContext();

    mlir::TypeConverter typeConverter;
    // Convert unknown types to itself
    typeConverter.addConversion([](mlir::Type type) { return type; });

    mlir::RewritePatternSet patterns(&context);
    mlir::ConversionTarget target(context);

    numba::populateTupleTypeConversionRewritesAndTarget(typeConverter, patterns,
                                                        target);
    numba::populateControlFlowTypeConversionRewritesAndTarget(typeConverter,
                                                              patterns, target);

    numba::populatePromoteBoolMemrefConversionRewritesAndTarget(
        typeConverter, patterns, target);
    if (mlir::failed(mlir::applyFullConversion(getOperation(), target,
                                               std::move(patterns))))
      signalPassFailure();
  }
};
} // namespace

std::unique_ptr<mlir::Pass> numba::createPromoteBoolMemrefPass() {
  return std::make_unique<PromoteBoolMemrefPass>();
}
