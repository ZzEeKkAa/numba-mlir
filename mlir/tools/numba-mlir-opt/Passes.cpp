// SPDX-FileCopyrightText: 2022 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#include <mlir/IR/PatternMatch.h>
#include <mlir/Pass/Pass.h>
#include <mlir/Pass/PassManager.h>
#include <mlir/Pass/PassRegistry.h>
#include <mlir/Transforms/GreedyPatternRewriteDriver.h>

#include <mlir/Dialect/Func/IR/FuncOps.h>
#include <mlir/Dialect/GPU/IR/GPUDialect.h>
#include <mlir/Dialect/GPU/Transforms/Passes.h>
#include <mlir/Dialect/SCF/IR/SCF.h>

#include "numba/Conversion/CfgToScf.hpp"
#include "numba/Conversion/GpuRuntimeToLlvm.hpp"
#include "numba/Conversion/GpuToGpuRuntime.hpp"
#include "numba/Conversion/NtensorToLinalg.hpp"
#include "numba/Conversion/NtensorToMemref.hpp"
#include "numba/Conversion/SCFToAffine/SCFToAffine.h"
#include "numba/Dialect/gpu_runtime/Transforms/MakeBarriersUniform.hpp"
#include "numba/Dialect/ntensor/Transforms/CopyRemoval.hpp"
#include "numba/Dialect/ntensor/Transforms/PropagateEnvironment.hpp"
#include "numba/Dialect/ntensor/Transforms/ResolveArrayOps.hpp"
#include "numba/Transforms/CanonicalizeReductions.hpp"
#include "numba/Transforms/ExpandTuple.hpp"
#include "numba/Transforms/FuncTransforms.hpp"
#include "numba/Transforms/MakeSignless.hpp"
#include "numba/Transforms/MemoryRewrites.hpp"
#include "numba/Transforms/PromoteToParallel.hpp"
#include "numba/Transforms/ShapeIntegerRangePropagation.hpp"

// Passes registration.

static mlir::PassPipelineRegistration<>
    ParallelLoopToGpu("parallel-loop-to-gpu", "Maps scf parallel loop to gpu",
                      [](mlir::OpPassManager &pm) {
                        pm.addNestedPass<mlir::func::FuncOp>(
                            gpu_runtime::createParallelLoopGPUMappingPass());
                      });

static mlir::PassPipelineRegistration<>
    InsertGpuAlloc("insert-gpu-alloc", "Converts memref alloc to gpu alloc",
                   [](mlir::OpPassManager &pm) {
                     pm.addNestedPass<mlir::func::FuncOp>(
                         gpu_runtime::createInsertGPUAllocsPass());
                   });

static mlir::PassPipelineRegistration<>
    UnstrideMemrefPass("unstride-memref", "Used to flatten 2D to 1D",
                       [](mlir::OpPassManager &pm) {
                         pm.addNestedPass<mlir::func::FuncOp>(
                             mlir::createGpuDecomposeMemrefsPass());
                       });

static mlir::PassPipelineRegistration<>
    AbiAttrsPass("set-spirv-abi-attrs", "Create AbiAttrs Pass",
                 [](mlir::OpPassManager &pm) {
                   pm.addNestedPass<mlir::gpu::GPUModuleOp>(
                       gpu_runtime::createAbiAttrsPass());
                 });

static mlir::PassPipelineRegistration<> SetSpirvCapabalities(
    "set-spirv-capablilities", "Sets spirv capablilities",
    [](mlir::OpPassManager &pm) {
      pm.addPass(gpu_runtime::createSetSPIRVCapabilitiesPass());
    });

static mlir::PassPipelineRegistration<>
    GpuToSpirv("gpux-to-spirv", "Converts Gpu to spirv module",
               [](mlir::OpPassManager &pm) {
                 pm.addPass(gpu_runtime::createGPUToSpirvPass());
               });

static mlir::PassPipelineRegistration<>
    SerializeSpirv("serialize-spirv", "Serializes the spir-v binary",
                   [](mlir::OpPassManager &pm) {
                     pm.addPass(gpu_runtime::createSerializeSPIRVPass());
                   });

static mlir::PassPipelineRegistration<> GpuToGpuRuntime(
    "gpu-to-gpux", "Converts Gpu ops to gpux", [](mlir::OpPassManager &pm) {
      pm.addNestedPass<mlir::func::FuncOp>(gpu_runtime::createGPUExPass());
    });

static mlir::PassPipelineRegistration<>
    GpuToLlvm("convert-gpu-to-llvm",
              "Converts Gpu runtime dialect to llvm runtime calls",
              [](mlir::OpPassManager &pm) {
                pm.addPass(gpu_runtime::createGPUToLLVMPass());
              });

static mlir::PassPipelineRegistration<> scfToAffineReg(
    "scf-to-affine", "Converts SCF parallel struct into Affine parallel",
    [](mlir::OpPassManager &pm) {
      pm.addNestedPass<mlir::func::FuncOp>(mlir::createSCFToAffinePass());
    });

static mlir::PassPipelineRegistration<> cfgToScf(
    "cfg-to-scf", "Convert function from CFG form to SCF ops",
    [](mlir::OpPassManager &pm) {
      pm.addNestedPass<mlir::func::FuncOp>(numba::createCFGToSCFPass());
    });

static mlir::PassPipelineRegistration<>
    expandTuple("expand-tuple", "Expand tuple into individual elements",
                [](mlir::OpPassManager &pm) {
                  pm.addPass(numba::createExpandTuplePass());
                });

static mlir::PassPipelineRegistration<> ntensorResolveArrayOps(
    "ntensor-resolve-array-ops", "Resolve ntensor array ops into primitive ops",
    [](mlir::OpPassManager &pm) {
      pm.addPass(numba::ntensor::createResolveArrayOpsPass());
    });

static mlir::PassPipelineRegistration<> ntensorPropagateEnv(
    "ntensor-propagate-env", "Propagate ntensor environment",
    [](mlir::OpPassManager &pm) {
      pm.addPass(numba::ntensor::createPropagateEnvironmentPass());
    });

static mlir::PassPipelineRegistration<>
    ntensorCopyRemoval("ntensor-copy-removal",
                       "This pass tries to remove redundant `ntensor.copy` ops",
                       [](mlir::OpPassManager &pm) {
                         pm.addPass(numba::ntensor::createCopyRemovalPass());
                       });

static mlir::PassPipelineRegistration<>
    ntensorAliasAnalysis("ntensor-alias-analysis",
                         "Run alias analysis on ntensor ops",
                         [](mlir::OpPassManager &pm) {
                           pm.addPass(numba::createNtensorAliasAnalysisPass());
                         });

static mlir::PassPipelineRegistration<>
    ntensorToMemref("ntensor-to-memref", "Convert ntensor array ops to memref",
                    [](mlir::OpPassManager &pm) {
                      pm.addPass(numba::createNtensorToMemrefPass());
                    });

static mlir::PassPipelineRegistration<>
    ntensorToLinalg("ntensor-to-linalg", "Convert ntensor array ops to linalg",
                    [](mlir::OpPassManager &pm) {
                      pm.addPass(numba::createNtensorToLinalgPass());
                    });

static mlir::PassPipelineRegistration<> makeSignless(
    "numba-make-signless",
    "Convert types of various signedness to corresponding signless type",
    [](mlir::OpPassManager &pm) {
      pm.addPass(numba::createMakeSignlessPass());
    });

static mlir::PassPipelineRegistration<> makeBarriersUniform(
    "gpux-make-barriers-uniform",
    "Adapt gpu barriers to non-uniform control flow",
    [](mlir::OpPassManager &pm) {
      pm.addPass(gpu_runtime::createMakeBarriersUniformPass());
    });

static mlir::PassPipelineRegistration<> tileParallelLoopsGPU(
    "gpux-tile-parallel-loops", "Naively tile parallel loops for gpu",
    [](mlir::OpPassManager &pm) {
      pm.addPass(gpu_runtime::createTileParallelLoopsForGPUPass());
    });

static mlir::PassPipelineRegistration<> memoryOpts(
    "numba-memory-opts", "Apply memory optimizations",
    [](mlir::OpPassManager &pm) { pm.addPass(numba::createMemoryOptPass()); });

static mlir::PassPipelineRegistration<> canonicalizeReductions(
    "numba-canonicalize-reductions",
    "Tries to promote loads/stores in scf.for to loop-carried variables",
    [](mlir::OpPassManager &pm) {
      pm.addPass(numba::createCanonicalizeReductionsPass());
    });

static mlir::PassPipelineRegistration<> insertGPUGlobalReduce(
    "gpux-insert-global-reduce",
    "Update scf.parallel loops with reductions to use "
    "gpu_runtime.global_reduce",
    [](mlir::OpPassManager &pm) {
      pm.addPass(gpu_runtime::createInsertGPUGlobalReducePass());
    });

static mlir::PassPipelineRegistration<>
    promoteToParallel("numba-promote-to-parallel",
                      "Promotes scf.for to scf.parallel",
                      [](mlir::OpPassManager &pm) {
                        pm.addPass(numba::createPromoteToParallelPass());
                      });

static mlir::PassPipelineRegistration<> shapeIntegerRangePropagation(
    "numba-shape-int-range-opts", "Shape integer range optimizations",
    [](mlir::OpPassManager &pm) {
      pm.addPass(numba::createShapeIntegerRangePropagationPass());
    });

static mlir::PassPipelineRegistration<>
    funcRemoveUnusedArgs("numba-remove-unused-args",
                         "Remove unused functions arguments",
                         [](mlir::OpPassManager &pm) {
                           pm.addPass(numba::createRemoveUnusedArgsPass());
                         });

static mlir::PassPipelineRegistration<>
    sortLoopsForGPU("numba-sort-loops-for-gpu",
                    "Rearrange loop for more optimal order for GPU",
                    [](mlir::OpPassManager &pm) {
                      pm.addPass(gpu_runtime::createSortParallelLoopsForGPU());
                    });
