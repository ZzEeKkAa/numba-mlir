// SPDX-FileCopyrightText: 2022 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include "numba/Conversion/UtilToLlvm.hpp"

#include "numba/Dialect/numba_util/Dialect.hpp"
#include "numba/Transforms/FuncUtils.hpp"

#include <mlir/Conversion/LLVMCommon/ConversionTarget.h>
#include <mlir/Conversion/LLVMCommon/Pattern.h>
#include <mlir/Dialect/Func/IR/FuncOps.h>
#include <mlir/Dialect/LLVMIR/LLVMDialect.h>
#include <mlir/Dialect/MemRef/IR/MemRef.h>
#include <mlir/Pass/Pass.h>

static mlir::Type convertTupleTypes(mlir::MLIRContext &context,
                                    mlir::TypeConverter &converter,
                                    mlir::TypeRange types) {
  if (types.empty())
    return mlir::LLVM::LLVMStructType::getLiteral(&context, std::nullopt);

  auto unitupleType = [&]() -> mlir::Type {
    assert(!types.empty());
    auto elemType = types.front();
    auto tail = types.drop_front();
    if (llvm::all_of(tail, [&](auto t) { return t == elemType; }))
      return elemType;
    return nullptr;
  }();

  auto count = static_cast<unsigned>(types.size());
  if (unitupleType) {
    auto newType = converter.convertType(unitupleType);
    if (!newType)
      return {};
    return mlir::LLVM::LLVMArrayType::get(newType, count);
  }
  llvm::SmallVector<mlir::Type> newTypes;
  newTypes.reserve(count);
  for (auto type : types) {
    auto newType = converter.convertType(type);
    if (!newType)
      return {};
    newTypes.emplace_back(newType);
  }

  return mlir::LLVM::LLVMStructType::getLiteral(&context, newTypes);
}

static mlir::Type convertTuple(mlir::MLIRContext &context,
                               mlir::TypeConverter &converter,
                               mlir::TupleType tuple) {
  return convertTupleTypes(context, converter, tuple.getTypes());
}

static mlir::Type getLLVMPointerType(mlir::Type elemType) {
  assert(elemType);
  return mlir::LLVM::LLVMPointerType::get(elemType.getContext());
}

static void
populateToLLVMAdditionalTypeConversion(mlir::LLVMTypeConverter &converter) {
  converter.addConversion(
      [&converter](mlir::TupleType type) -> std::optional<mlir::Type> {
        auto res = convertTuple(*type.getContext(), converter, type);
        if (!res)
          return std::nullopt;
        return res;
      });
  auto voidPtrType =
      getLLVMPointerType(mlir::IntegerType::get(&converter.getContext(), 8));
  converter.addConversion(
      [voidPtrType](mlir::NoneType) -> std::optional<mlir::Type> {
        return voidPtrType;
      });
  converter.addConversion(
      [voidPtrType](numba::util::OpaqueType) -> std::optional<mlir::Type> {
        return voidPtrType;
      });
}

namespace {
struct LowerMemrefBitcastOp
    : public mlir::ConvertOpToLLVMPattern<numba::util::MemrefBitcastOp> {
  using ConvertOpToLLVMPattern::ConvertOpToLLVMPattern;

  mlir::LogicalResult
  matchAndRewrite(numba::util::MemrefBitcastOp op,
                  numba::util::MemrefBitcastOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto arg = adaptor.getSource();
    if (!arg.getType().isa<mlir::LLVM::LLVMStructType>())
      return mlir::failure();

    auto memrefType = op.getType().dyn_cast<mlir::MemRefType>();
    if (!memrefType)
      return mlir::failure();

    auto converter = getTypeConverter();
    assert(converter && "Invalid type converter");

    auto resType = converter->convertType(memrefType);
    if (!resType)
      return mlir::failure();

    auto loc = op.getLoc();
    mlir::MemRefDescriptor src(arg);
    auto dst = mlir::MemRefDescriptor::undef(rewriter, loc, resType);

    auto elemPtrType = dst.getElementPtrType();

    auto allocatedPtr = src.allocatedPtr(rewriter, loc);
    allocatedPtr =
        rewriter.create<mlir::LLVM::BitcastOp>(loc, elemPtrType, allocatedPtr);

    auto alignedPtr = src.alignedPtr(rewriter, loc);
    alignedPtr =
        rewriter.create<mlir::LLVM::BitcastOp>(loc, elemPtrType, alignedPtr);

    dst.setAllocatedPtr(rewriter, loc, allocatedPtr);
    dst.setAlignedPtr(rewriter, loc, alignedPtr);

    dst.setOffset(rewriter, loc, src.offset(rewriter, loc));
    for (auto i : llvm::seq(0u, static_cast<unsigned>(memrefType.getRank()))) {
      dst.setSize(rewriter, loc, i, src.size(rewriter, loc, i));
      dst.setStride(rewriter, loc, i, src.stride(rewriter, loc, i));
    }
    rewriter.replaceOp(op, static_cast<mlir::Value>(dst));
    return mlir::success();
  }
};

struct LowerBuildTuple
    : public mlir::ConvertOpToLLVMPattern<numba::util::BuildTupleOp> {
  using ConvertOpToLLVMPattern::ConvertOpToLLVMPattern;

  mlir::LogicalResult
  matchAndRewrite(numba::util::BuildTupleOp op,
                  numba::util::BuildTupleOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto converter = getTypeConverter();
    assert(converter && "Invalid type converter");

    auto type = converter->convertType(op.getType());
    if (!type)
      return mlir::failure();

    auto loc = op.getLoc();
    mlir::Value init = rewriter.create<mlir::LLVM::UndefOp>(loc, type);
    for (auto &&[i, arg] : llvm::enumerate(adaptor.getArgs())) {
      auto newType = arg.getType();
      assert(newType);
      auto index = static_cast<int64_t>(i);
      init = rewriter.create<mlir::LLVM::InsertValueOp>(loc, init, arg, index);
    }

    rewriter.replaceOp(op, init);
    return mlir::success();
  }
};

static void addToGlobalDtors(mlir::ConversionPatternRewriter &rewriter,
                             mlir::ModuleOp mod, mlir::SymbolRefAttr attr,
                             int32_t priority) {
  auto loc = mod->getLoc();
  auto dtorOps = mod.getOps<mlir::LLVM::GlobalDtorsOp>();
  auto prioAttr = rewriter.getI32IntegerAttr(priority);
  mlir::OpBuilder::InsertionGuard g(rewriter);
  if (dtorOps.empty()) {
    rewriter.setInsertionPoint(mod.getBody(), std::prev(mod.getBody()->end()));
    auto syms = rewriter.getArrayAttr(attr);
    auto priorities = rewriter.getArrayAttr(prioAttr);
    rewriter.create<mlir::LLVM::GlobalDtorsOp>(loc, syms, priorities);
    return;
  }
  assert(llvm::hasSingleElement(dtorOps));
  auto dtorOp = *dtorOps.begin();

  auto addpendArray = [&](mlir::ArrayAttr arr,
                          mlir::Attribute attr) -> mlir::ArrayAttr {
    auto vals = arr.getValue();
    llvm::SmallVector<mlir::Attribute> ret(vals.begin(), vals.end());
    ret.emplace_back(attr);
    return rewriter.getArrayAttr(ret);
  };
  auto newDtors = addpendArray(dtorOp.getDtors(), attr);
  auto newPrioritiess = addpendArray(dtorOp.getPriorities(), prioAttr);
  rewriter.setInsertionPoint(dtorOp);
  rewriter.create<mlir::LLVM::GlobalDtorsOp>(loc, newDtors, newPrioritiess);
  rewriter.eraseOp(dtorOp);
}

struct LowerTakeContextOp
    : public mlir::ConvertOpToLLVMPattern<numba::util::TakeContextOp> {
  using ConvertOpToLLVMPattern::ConvertOpToLLVMPattern;

  mlir::LogicalResult
  matchAndRewrite(numba::util::TakeContextOp op,
                  numba::util::TakeContextOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto converter = getTypeConverter();
    assert(converter);
    auto ctx = op.getContext();
    auto ctxType = converter->convertType(ctx.getType());
    if (!ctxType)
      return mlir::failure();

    mlir::ValueRange results = op.getResults();
    auto resultsCount = static_cast<unsigned>(results.size());
    llvm::SmallVector<mlir::Type> resultTypes(resultsCount);
    for (auto i : llvm::seq(0u, resultsCount)) {
      auto type = converter->convertType(results[i].getType());
      if (!type)
        return mlir::failure();

      resultTypes[i] = type;
    }

    auto ctxStructType =
        mlir::LLVM::LLVMStructType::getLiteral(getContext(), resultTypes);
    auto ctxStructPtrType = getLLVMPointerType(ctxStructType);

    auto mod = op->getParentOfType<mlir::ModuleOp>();
    assert(mod);

    auto unknownLoc = rewriter.getUnknownLoc();
    auto loc = op->getLoc();
    auto wrapperType =
        mlir::LLVM::LLVMFunctionType::get(getVoidType(), ctxType);
    auto wrapperPtrType = getLLVMPointerType(wrapperType);
    mlir::Value initFuncPtr;

    auto insertFunc = [&](mlir::StringRef name, mlir::Type type,
                          mlir::LLVM::Linkage linkage) {
      mlir::OpBuilder::InsertionGuard g(rewriter);
      rewriter.setInsertionPointToStart(mod.getBody());
      return rewriter.create<mlir::LLVM::LLVMFuncOp>(unknownLoc, name, type,
                                                     linkage);
    };

    auto lookupFunc = [&](mlir::StringRef name, mlir::Type type) {
      // TODO: fix and use lookupOrCreateFn
      if (auto func = mod.lookupSymbol<mlir::LLVM::LLVMFuncOp>(name))
        return func;

      mlir::OpBuilder::InsertionGuard g(rewriter);
      rewriter.setInsertionPointToStart(mod.getBody());
      return rewriter.create<mlir::LLVM::LLVMFuncOp>(
          unknownLoc, name, type, mlir::LLVM::Linkage::External);
    };

    if (auto initFuncSym = adaptor.getInitFuncAttr()) {
      auto funcName = initFuncSym.getLeafReference().getValue();
      auto wrapperName = (funcName + "_wrapper").str();

      auto initFunc = [&]() {
        mlir::OpBuilder::InsertionGuard g(rewriter);
        auto func =
            insertFunc(wrapperName, wrapperType, mlir::LLVM::Linkage::Private);
        auto block = rewriter.createBlock(
            &func.getBody(), mlir::Region::iterator{}, ctxType, unknownLoc);
        rewriter.setInsertionPointToStart(block);

        // Get init func declaration so we can check original return types.
        auto initFunc = mod.lookupSymbol<mlir::func::FuncOp>(initFuncSym);
        assert(initFunc && "Invalid init func");
        auto initFuncType = initFunc.getFunctionType();
        assert(initFuncType.getNumResults() == resultsCount &&
               "Invalid init func");

        auto innerResults =
            rewriter
                .create<mlir::func::CallOp>(unknownLoc, initFuncSym,
                                            initFuncType.getResults())
                ->getResults();

        mlir::Value ctxStruct =
            rewriter.create<mlir::LLVM::UndefOp>(unknownLoc, ctxStructType);
        for (auto i : llvm::seq(0u, resultsCount)) {
          auto srcType = initFuncType.getResult(i);
          auto convertedType = converter->convertType(srcType);
          assert(convertedType && "Invalid init func result type");

          mlir::Value val = innerResults[i];
          // Init function may not be type-converted at this point, so insert
          // conversion casts.
          if (convertedType != srcType)
            val = converter->materializeSourceConversion(rewriter, unknownLoc,
                                                         convertedType, val);
          assert(val && "Invalid init func result type");

          ctxStruct = rewriter.create<mlir::LLVM::InsertValueOp>(
              unknownLoc, ctxStruct, val, i);
        }
        auto ptr = rewriter.create<mlir::LLVM::BitcastOp>(
            unknownLoc, ctxStructPtrType, block->getArgument(0));
        rewriter.create<mlir::LLVM::StoreOp>(unknownLoc, ctxStruct, ptr);
        rewriter.create<mlir::LLVM::ReturnOp>(unknownLoc, std::nullopt);
        return func;
      }();

      auto funcPtr = getLLVMPointerType(initFunc.getFunctionType());
      initFuncPtr = rewriter.create<mlir::LLVM::AddressOfOp>(
          loc, funcPtr, initFunc.getSymName());
    } else {
      initFuncPtr = rewriter.create<mlir::LLVM::NullOp>(loc, wrapperPtrType);
    }

    mlir::Value deinitFuncPtr;
    if (auto deinitFuncSym = adaptor.getReleaseFuncAttr()) {
      auto funcName = deinitFuncSym.getLeafReference().getValue();
      auto wrapperName = (funcName + "_wrapper").str();

      auto deinitFunc = [&]() {
        mlir::OpBuilder::InsertionGuard g(rewriter);
        auto func =
            insertFunc(wrapperName, wrapperType, mlir::LLVM::Linkage::Private);
        auto block = rewriter.createBlock(
            &func.getBody(), mlir::Region::iterator{}, ctxType, unknownLoc);
        rewriter.setInsertionPointToStart(block);

        auto ptr = rewriter.create<mlir::LLVM::BitcastOp>(
            unknownLoc, ctxStructPtrType, block->getArgument(0));
        auto ctxStruct =
            rewriter.create<mlir::LLVM::LoadOp>(unknownLoc, ctxStructType, ptr);

        // Get deinit func declaration so we can check original arg types.
        auto deinitFunc = mod.lookupSymbol<mlir::func::FuncOp>(deinitFuncSym);
        assert(deinitFunc && "Invalid deinit func");
        auto deinitFuncType = deinitFunc.getFunctionType();
        assert(deinitFuncType.getNumInputs() == resultsCount);

        llvm::SmallVector<mlir::Value> args(resultsCount);
        for (auto i : llvm::seq(0u, resultsCount)) {
          mlir::Value val = rewriter.create<mlir::LLVM::ExtractValueOp>(
              unknownLoc, resultTypes[i], ctxStruct, i);
          auto resType = deinitFuncType.getInput(i);
          // Deinit function may not be type-converted at this point, so insert
          // conversion casts.
          if (resultTypes[i] != resType)
            val = converter->materializeTargetConversion(rewriter, unknownLoc,
                                                         resType, val);

          args[i] = val;
        }

        rewriter.create<mlir::func::CallOp>(unknownLoc, deinitFuncSym,
                                            std::nullopt, args);
        rewriter.create<mlir::LLVM::ReturnOp>(unknownLoc, std::nullopt);
        return func;
      }();

      auto funcPtr = getLLVMPointerType(deinitFunc.getFunctionType());
      deinitFuncPtr = rewriter.create<mlir::LLVM::AddressOfOp>(
          loc, funcPtr, deinitFunc.getSymName());
    } else {
      deinitFuncPtr = rewriter.create<mlir::LLVM::NullOp>(loc, wrapperPtrType);
    }

    auto takeCtxFunc = [&]() -> mlir::LLVM::LLVMFuncOp {
      llvm::StringRef name("nmrtTakeContext");
      auto retType = getVoidPtrType();
      const mlir::Type argTypes[] = {
          getLLVMPointerType(getVoidPtrType()),
          getIndexType(),
          wrapperPtrType,
          wrapperPtrType,
      };
      auto funcType = mlir::LLVM::LLVMFunctionType::get(retType, argTypes);
      return lookupFunc(name, funcType);
    }();

    auto purgeCtxFunc = [&]() -> mlir::LLVM::LLVMFuncOp {
      llvm::StringRef name("nmrtPurgeContext");
      auto retType = getVoidType();
      auto argType = getLLVMPointerType(getVoidPtrType());
      auto funcType = mlir::LLVM::LLVMFunctionType::get(retType, argType);
      return lookupFunc(name, funcType);
    }();

    auto ctxHandle = [&]() {
      mlir::OpBuilder::InsertionGuard g(rewriter);
      rewriter.setInsertionPointToStart(mod.getBody());
      auto name = numba::getUniqueLLVMGlobalName(mod, "context_handle");
      auto handle = rewriter.create<mlir::LLVM::GlobalOp>(
          unknownLoc, ctxType, /*isConstant*/ false,
          mlir::LLVM::Linkage::Internal, name, mlir::Attribute());

      llvm::StringRef cleanupFuncName(".nmrt_context_cleanup");
      auto cleanupFunc =
          mod.lookupSymbol<mlir::LLVM::LLVMFuncOp>(cleanupFuncName);
      if (!cleanupFunc) {
        auto cleanupFuncType =
            mlir::LLVM::LLVMFunctionType::get(getVoidType(), std::nullopt);
        cleanupFunc = rewriter.create<mlir::LLVM::LLVMFuncOp>(
            unknownLoc, cleanupFuncName, cleanupFuncType);
        auto block = rewriter.createBlock(&cleanupFunc.getBody());
        rewriter.setInsertionPointToStart(block);
        rewriter.create<mlir::LLVM::ReturnOp>(unknownLoc, std::nullopt);

        addToGlobalDtors(rewriter, mod, mlir::SymbolRefAttr::get(cleanupFunc),
                         0);
      }

      assert(llvm::hasSingleElement(cleanupFunc.getBody()));
      rewriter.setInsertionPointToStart(&cleanupFunc.getBody().front());

      auto ctxPtrType = getLLVMPointerType(ctxType);
      mlir::Value addr = rewriter.create<mlir::LLVM::AddressOfOp>(
          unknownLoc, ctxPtrType, handle.getSymName());
      rewriter.create<mlir::LLVM::CallOp>(unknownLoc, purgeCtxFunc, addr);

      return handle;
    }();

    auto ctxPtrType = getLLVMPointerType(ctxType);
    auto ctxHandlePtr = rewriter.create<mlir::LLVM::AddressOfOp>(
        loc, ctxPtrType, ctxHandle.getSymName());
    auto contextSize = getSizeInBytes(loc, ctxStructType, rewriter);

    const mlir::Value takeCtxArgs[] = {
        ctxHandlePtr,
        contextSize,
        initFuncPtr,
        deinitFuncPtr,
    };
    auto ctxPtr =
        rewriter.create<mlir::LLVM::CallOp>(loc, takeCtxFunc, takeCtxArgs)
            .getResult();

    llvm::SmallVector<mlir::Value> takeCtxResults;
    takeCtxResults.emplace_back(ctxPtr);

    auto ctxStructPtr =
        rewriter.create<mlir::LLVM::BitcastOp>(loc, ctxStructPtrType, ctxPtr);
    auto ctxStruct =
        rewriter.create<mlir::LLVM::LoadOp>(loc, ctxStructType, ctxStructPtr);

    for (auto i : llvm::seq(0u, resultsCount)) {
      auto res = rewriter.create<mlir::LLVM::ExtractValueOp>(
          loc, resultTypes[i], ctxStruct, i);
      takeCtxResults.emplace_back(res);
    }

    rewriter.replaceOp(op, takeCtxResults);
    return mlir::success();
  }
};

struct LowerReleaseContextOp
    : public mlir::ConvertOpToLLVMPattern<numba::util::ReleaseContextOp> {
  using ConvertOpToLLVMPattern::ConvertOpToLLVMPattern;

  mlir::LogicalResult
  matchAndRewrite(numba::util::ReleaseContextOp op,
                  numba::util::ReleaseContextOp::Adaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto mod = op->getParentOfType<mlir::ModuleOp>();
    assert(mod);

    auto unknownLoc = rewriter.getUnknownLoc();
    auto loc = op->getLoc();

    auto lookupFunc = [&](mlir::StringRef name, mlir::Type type) {
      // TODO: fix and use lookupOrCreateFn
      if (auto func = mod.lookupSymbol<mlir::LLVM::LLVMFuncOp>(name))
        return func;

      mlir::OpBuilder::InsertionGuard g(rewriter);
      rewriter.setInsertionPointToStart(mod.getBody());
      return rewriter.create<mlir::LLVM::LLVMFuncOp>(
          unknownLoc, name, type, mlir::LLVM::Linkage::External);
    };

    auto releaseCtxFunc = [&]() -> mlir::LLVM::LLVMFuncOp {
      llvm::StringRef name("nmrtReleaseContext");
      auto voidPtr = getVoidPtrType();
      auto funcType = mlir::LLVM::LLVMFunctionType::get(voidPtr, voidPtr);
      return lookupFunc(name, funcType);
    }();

    rewriter.create<mlir::LLVM::CallOp>(loc, releaseCtxFunc,
                                        adaptor.getContext());
    rewriter.eraseOp(op);
    return mlir::success();
  }
};

struct LowerApplyOffsetOp
    : public mlir::ConvertOpToLLVMPattern<numba::util::MemrefApplyOffsetOp> {
  using ConvertOpToLLVMPattern::ConvertOpToLLVMPattern;

  mlir::LogicalResult
  matchAndRewrite(numba::util::MemrefApplyOffsetOp op, OpAdaptor adaptor,
                  mlir::ConversionPatternRewriter &rewriter) const override {
    auto arg = adaptor.getSource();
    if (!arg.getType().isa<mlir::LLVM::LLVMStructType>())
      return mlir::failure();

    auto memrefType =
        mlir::dyn_cast<mlir::MemRefType>(op.getSource().getType());
    if (!memrefType)
      return mlir::failure();

    auto dstMemrefType = mlir::dyn_cast<mlir::MemRefType>(op.getType());
    if (!dstMemrefType)
      return mlir::failure();

    auto converter = getTypeConverter();
    assert(converter && "Invalid type converter");

    auto resType = converter->convertType(op.getType());
    if (!resType)
      return mlir::failure();

    auto elemType = converter->convertType(memrefType.getElementType());
    if (!elemType)
      return mlir::failure();

    auto loc = op.getLoc();
    mlir::MemRefDescriptor src(arg);
    auto dst = mlir::MemRefDescriptor::undef(rewriter, loc, resType);

    auto elemPtrType = dst.getElementPtrType();

    auto allocatedPtr = src.allocatedPtr(rewriter, loc);
    allocatedPtr =
        rewriter.create<mlir::LLVM::BitcastOp>(loc, elemPtrType, allocatedPtr);

    auto alignedPtr = src.alignedPtr(rewriter, loc);
    auto srcOffset = src.offset(rewriter, loc);
    alignedPtr = rewriter.create<mlir::LLVM::GEPOp>(loc, elemPtrType, elemType,
                                                    alignedPtr, srcOffset);

    dst.setAllocatedPtr(rewriter, loc, allocatedPtr);
    dst.setAlignedPtr(rewriter, loc, alignedPtr);

    auto zeroAttr = rewriter.getIntegerAttr(dst.getIndexType(), 0);
    auto dstOffset = rewriter.create<mlir::LLVM::ConstantOp>(loc, zeroAttr);
    dst.setOffset(rewriter, loc, dstOffset);
    for (auto i :
         llvm::seq(0u, static_cast<unsigned>(dstMemrefType.getRank()))) {
      dst.setSize(rewriter, loc, i, src.size(rewriter, loc, i));
      dst.setStride(rewriter, loc, i, src.stride(rewriter, loc, i));
    }
    rewriter.replaceOp(op, static_cast<mlir::Value>(dst));
    return mlir::success();
  }
};

/// Convert operations from the numba_util dialect to the LLVM dialect.
struct NumbaUtilToLLVMPass
    : public mlir::PassWrapper<NumbaUtilToLLVMPass,
                               mlir::OperationPass<mlir::ModuleOp>> {
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(NumbaUtilToLLVMPass)

  NumbaUtilToLLVMPass(
      std::function<mlir::LowerToLLVMOptions(mlir::MLIRContext &)> &&getter)
      : optsGetter(std::move(getter)) {}

  void runOnOperation() override {
    mlir::Operation *op = getOperation();
    auto &context = getContext();
    auto options = optsGetter(context);

    mlir::LLVMTypeConverter typeConverter(&context, options);
    populateToLLVMAdditionalTypeConversion(typeConverter);
    mlir::RewritePatternSet patterns(&context);

    patterns.insert<
        // clang-format off
        LowerBuildTuple,
        LowerMemrefBitcastOp,
        LowerTakeContextOp,
        LowerReleaseContextOp,
        LowerApplyOffsetOp
        // clang-format on
        >(typeConverter);

    mlir::LLVMConversionTarget target(context);
    target.addLegalOp<mlir::func::FuncOp>();
    target.addLegalOp<mlir::func::CallOp>();
    target.addLegalOp<numba::util::RetainOp>();
    target.addLegalOp<numba::util::WrapAllocatedPointer>();
    target.addLegalOp<numba::util::GetAllocTokenOp>();
    target.addIllegalDialect<numba::util::NumbaUtilDialect>();
    if (failed(applyPartialConversion(op, target, std::move(patterns))))
      signalPassFailure();
  }

private:
  std::function<mlir::LowerToLLVMOptions(mlir::MLIRContext &)> optsGetter;
};

} // namespace

std::unique_ptr<mlir::Pass> numba::createUtilToLLVMPass(
    std::function<mlir::LowerToLLVMOptions(mlir::MLIRContext &)> optsGetter) {
  assert(optsGetter && "invalid optsGetter");
  return std::make_unique<NumbaUtilToLLVMPass>(std::move(optsGetter));
}
