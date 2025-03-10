// RUN: numba-mlir-opt --gpux-tile-parallel-loops --split-input-file %s | FileCheck %s

// CHECK-LABEL: check1D
// CHECK-SAME: (%[[MEM1:.*]]: memref<?xf64>, %[[MEM2:.*]]: memref<?xf64>)
// CHECK: %[[C1:.*]] = arith.constant 1 : index
// CHECK: %[[C0:.*]] = arith.constant 0 : index
// CHECK: %[[DIM1:.*]] = memref.dim %[[MEM1]], %[[C0]] : memref<?xf64>
// CHECK: numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false>
// CHECK: %[[B:.*]]:3 = gpu_runtime.suggest_block_size, %[[DIM1]], %[[C1]], %[[C1]] -> index, index, index
// CHECK: %[[G1:.*]] = arith.ceildivui %[[DIM1]], %[[B]]#0 : index
// CHECK: scf.parallel
// CHECK-SAME: (%[[ARG1:.*]], %[[ARG2:.*]], %[[ARG3:.*]], %[[ARG4:.*]], %[[ARG5:.*]], %[[ARG6:.*]]) =
// CHECK-SAME: (%[[C0]], %[[C0]], %[[C0]], %[[C0]], %[[C0]], %[[C0]]) to
// CHECK-SAME: (%[[G1]], %[[C1]], %[[C1]], %[[B]]#0, %[[C1]], %[[C1]]) step
// CHECK-SAME: (%[[C1]], %[[C1]], %[[C1]], %[[C1]], %[[C1]], %[[C1]])
// CHECK: %[[IDX1:.*]] = arith.muli %[[ARG1]], %[[B]]#0 : index
// CHECK: %[[IDX2:.*]] = arith.addi %[[IDX1]], %[[ARG4]] : index
// CHECK: %[[IN1:.*]] = arith.cmpi slt, %[[IDX2]], %[[DIM1]] : index
// CHECK: scf.if %[[IN1]] {
// CHECK-NOT: }
// CHECK: %[[VAL:.*]] = memref.load %[[MEM1]][%[[IDX2]]] : memref<?xf64>
// CHECK: memref.store %[[VAL]], %[[MEM2]][%[[IDX2]]] : memref<?xf64>
// CHECK: {mapping = [#gpu.loop_dim_map<processor = block_x, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = block_y, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = block_z, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_x, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_y, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_z, map = (d0) -> (d0), bound = (d0) -> (d0)>]}
// CHECK: return
func.func @check1D(%arg0: memref<?xf64>, %arg1: memref<?xf64>) {
  %c1 = arith.constant 1 : index
  %c0 = arith.constant 0 : index
  %0 = memref.dim %arg0, %c0 : memref<?xf64>
  numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false> {
    scf.parallel (%arg4) = (%c0) to (%0) step (%c1) {
      %2 = memref.load %arg0[%arg4] : memref<?xf64>
      memref.store %2, %arg1[%arg4] : memref<?xf64>
      scf.yield
    }
  }
  return
}

// -----

// CHECK-LABEL: check3D
// CHECK-SAME: (%[[MEM1:.*]]: memref<?x?x?xf64>, %[[MEM2:.*]]: memref<?x?x?xf64>)
// CHECK: %[[C2:.*]] = arith.constant 2 : index
// CHECK: %[[C1:.*]] = arith.constant 1 : index
// CHECK: %[[C0:.*]] = arith.constant 0 : index
// CHECK: %[[DIM1:.*]] = memref.dim %[[MEM1]], %[[C0]] : memref<?x?x?xf64>
// CHECK: %[[DIM2:.*]] = memref.dim %[[MEM1]], %[[C1]] : memref<?x?x?xf64>
// CHECK: %[[DIM3:.*]] = memref.dim %[[MEM1]], %[[C2]] : memref<?x?x?xf64>
// CHECK: numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false>
// CHECK: %[[B:.*]]:3 = gpu_runtime.suggest_block_size, %[[DIM1]], %[[DIM2]], %[[DIM3]] -> index, index, index
// CHECK: %[[G1:.*]] = arith.ceildivui %[[DIM1]], %[[B]]#0 : index
// CHECK: %[[G2:.*]] = arith.ceildivui %[[DIM2]], %[[B]]#1 : index
// CHECK: %[[G3:.*]] = arith.ceildivui %[[DIM3]], %[[B]]#2 : index
// CHECK: scf.parallel
// CHECK-SAME: (%[[ARG1:.*]], %[[ARG2:.*]], %[[ARG3:.*]], %[[ARG4:.*]], %[[ARG5:.*]], %[[ARG6:.*]]) =
// CHECK-SAME: (%[[C0]], %[[C0]], %[[C0]], %[[C0]], %[[C0]], %[[C0]]) to
// CHECK-SAME: (%[[G1]], %[[G2]], %[[G3]], %[[B]]#0, %[[B]]#1, %[[B]]#2) step
// CHECK-SAME: (%[[C1]], %[[C1]], %[[C1]], %[[C1]], %[[C1]], %[[C1]])
// CHECK: %[[IDX1:.*]] = arith.muli %[[ARG1]], %[[B]]#0 : index
// CHECK: %[[IDX2:.*]] = arith.addi %[[IDX1]], %[[ARG4]] : index
// CHECK: %[[IN1:.*]] = arith.cmpi slt, %[[IDX2]], %[[DIM1]] : index
// CHECK: %[[IDX3:.*]] = arith.muli %[[ARG2]], %[[B]]#1 : index
// CHECK: %[[IDX4:.*]] = arith.addi %[[IDX3]], %[[ARG5]] : index
// CHECK: %[[IN2:.*]] = arith.cmpi slt, %[[IDX4]], %[[DIM2]] : index
// CHECK: %[[IN3:.*]] = arith.andi %[[IN1]], %[[IN2]] : i1
// CHECK: %[[IDX5:.*]] = arith.muli %[[ARG3]], %[[B]]#2 : index
// CHECK: %[[IDX6:.*]] = arith.addi %[[IDX5]], %[[ARG6]] : index
// CHECK: %[[IN4:.*]] = arith.cmpi slt, %[[IDX6]], %[[DIM3]] : index
// CHECK: %[[IN5:.*]] = arith.andi %[[IN3]], %[[IN4]] : i1
// CHECK: scf.if %[[IN5]] {
// CHECK-NOT: }
// CHECK: %[[VAL:.*]] = memref.load %[[MEM1]][%[[IDX2]], %[[IDX4]], %[[IDX6]]] : memref<?x?x?xf64>
// CHECK: memref.store %[[VAL]], %[[MEM2]][%[[IDX2]], %[[IDX4]], %[[IDX6]]] : memref<?x?x?xf64>
// CHECK: {mapping = [#gpu.loop_dim_map<processor = block_x, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = block_y, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = block_z, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_x, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_y, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_z, map = (d0) -> (d0), bound = (d0) -> (d0)>]}
// CHECK: return
func.func @check3D(%arg0: memref<?x?x?xf64>, %arg1: memref<?x?x?xf64>) {
  %c2 = arith.constant 2 : index
  %c1 = arith.constant 1 : index
  %c0 = arith.constant 0 : index
  %0 = memref.dim %arg0, %c0 : memref<?x?x?xf64>
  %1 = memref.dim %arg0, %c1 : memref<?x?x?xf64>
  %2 = memref.dim %arg0, %c2 : memref<?x?x?xf64>
  numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false> {
    scf.parallel (%arg4, %arg5, %arg6) = (%c0, %c0, %c0) to (%0, %1, %2) step (%c1, %c1, %c1) {
      %3 = memref.load %arg0[%arg4, %arg5, %arg6] : memref<?x?x?xf64>
      memref.store %3, %arg1[%arg4, %arg5, %arg6] : memref<?x?x?xf64>
      scf.yield
    }
  }
  return
}

// -----

// CHECK-LABEL: check4D
// CHECK-SAME: (%[[MEM1:.*]]: memref<?x?x?x?xf64>, %[[MEM2:.*]]: memref<?x?x?x?xf64>)
// CHECK: %[[C3:.*]] = arith.constant 3 : index
// CHECK: %[[C2:.*]] = arith.constant 2 : index
// CHECK: %[[C1:.*]] = arith.constant 1 : index
// CHECK: %[[C0:.*]] = arith.constant 0 : index
// CHECK: %[[DIM1:.*]] = memref.dim %[[MEM1]], %[[C0]] : memref<?x?x?x?xf64>
// CHECK: %[[DIM2:.*]] = memref.dim %[[MEM1]], %[[C1]] : memref<?x?x?x?xf64>
// CHECK: %[[DIM3:.*]] = memref.dim %[[MEM1]], %[[C2]] : memref<?x?x?x?xf64>
// CHECK: %[[DIM4:.*]] = memref.dim %[[MEM1]], %[[C3]] : memref<?x?x?x?xf64>
// CHECK: numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false>
// CHECK: %[[B:.*]]:3 = gpu_runtime.suggest_block_size, %[[DIM1]], %[[DIM2]], %[[DIM3]] -> index, index, index
// CHECK: %[[G1:.*]] = arith.ceildivui %[[DIM1]], %[[B]]#0 : index
// CHECK: %[[G2:.*]] = arith.ceildivui %[[DIM2]], %[[B]]#1 : index
// CHECK: %[[G3:.*]] = arith.ceildivui %[[DIM3]], %[[B]]#2 : index
// CHECK: scf.parallel
// CHECK-SAME: (%[[ARG1:.*]], %[[ARG2:.*]], %[[ARG3:.*]], %[[ARG4:.*]], %[[ARG5:.*]], %[[ARG6:.*]], %[[ARG7:.*]]) =
// CHECK-SAME: (%[[C0]], %[[C0]], %[[C0]], %[[C0]], %[[C0]], %[[C0]], %[[C0]]) to
// CHECK-SAME: (%[[G1]], %[[G2]], %[[G3]], %[[B]]#0, %[[B]]#1, %[[B]]#2, %[[DIM4]]) step
// CHECK-SAME: (%[[C1]], %[[C1]], %[[C1]], %[[C1]], %[[C1]], %[[C1]], %[[C1]])
// CHECK: %[[IDX1:.*]] = arith.muli %[[ARG1]], %[[B]]#0 : index
// CHECK: %[[IDX2:.*]] = arith.addi %[[IDX1]], %[[ARG4]] : index
// CHECK: %[[IN1:.*]] = arith.cmpi slt, %[[IDX2]], %[[DIM1]] : index
// CHECK: %[[IDX3:.*]] = arith.muli %[[ARG2]], %[[B]]#1 : index
// CHECK: %[[IDX4:.*]] = arith.addi %[[IDX3]], %[[ARG5]] : index
// CHECK: %[[IN2:.*]] = arith.cmpi slt, %[[IDX4]], %[[DIM2]] : index
// CHECK: %[[IN3:.*]] = arith.andi %[[IN1]], %[[IN2]] : i1
// CHECK: %[[IDX5:.*]] = arith.muli %[[ARG3]], %[[B]]#2 : index
// CHECK: %[[IDX6:.*]] = arith.addi %[[IDX5]], %[[ARG6]] : index
// CHECK: %[[IN4:.*]] = arith.cmpi slt, %[[IDX6]], %[[DIM3]] : index
// CHECK: %[[IN5:.*]] = arith.andi %[[IN3]], %[[IN4]] : i1
// CHECK: scf.if %[[IN5]] {
// CHECK-NOT: }
// CHECK: %[[VAL:.*]] = memref.load %[[MEM1]][%[[IDX2]], %[[IDX4]], %[[IDX6]], %[[ARG7]]] : memref<?x?x?x?xf64>
// CHECK: memref.store %[[VAL]], %[[MEM2]][%[[IDX2]], %[[IDX4]], %[[IDX6]], %[[ARG7]]] : memref<?x?x?x?xf64>
// CHECK: {mapping = [#gpu.loop_dim_map<processor = block_x, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = block_y, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = block_z, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_x, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_y, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_z, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = sequential, map = (d0) -> (d0), bound = (d0) -> (d0)>]}
// CHECK: return
func.func @check4D(%arg0: memref<?x?x?x?xf64>, %arg1: memref<?x?x?x?xf64>) {
  %c3 = arith.constant 3 : index
  %c2 = arith.constant 2 : index
  %c1 = arith.constant 1 : index
  %c0 = arith.constant 0 : index
  %0 = memref.dim %arg0, %c0 : memref<?x?x?x?xf64>
  %1 = memref.dim %arg0, %c1 : memref<?x?x?x?xf64>
  %2 = memref.dim %arg0, %c2 : memref<?x?x?x?xf64>
  %3 = memref.dim %arg0, %c3 : memref<?x?x?x?xf64>
  numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false> {
    scf.parallel (%arg4, %arg5, %arg6, %arg7) = (%c0, %c0, %c0, %c0) to (%0, %1, %2, %3) step (%c1, %c1, %c1, %c1) {
      %4 = memref.load %arg0[%arg4, %arg5, %arg6, %arg7] : memref<?x?x?x?xf64>
      memref.store %4, %arg1[%arg4, %arg5, %arg6, %arg7] : memref<?x?x?x?xf64>
      scf.yield
    }
  }
  return
}

// -----

// CHECK-LABEL: check1DReduction
// CHECK-SAME: (%[[MEM1:.*]]: memref<?xf64>, %[[MEM2:.*]]: memref<?xf64>, %[[INIT:.*]]: f64)
// CHECK: %[[NEUTRAL:.*]] = arith.constant 1.000000e+00 : f64
// CHECK: %[[C1:.*]] = arith.constant 1 : index
// CHECK: %[[C0:.*]] = arith.constant 0 : index
// CHECK: %[[DIM1:.*]] = memref.dim %[[MEM1]], %[[C0]] : memref<?xf64>
// CHECK: %[[RES1:.*]] = numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false> -> f64
// CHECK: %[[B:.*]]:3 = gpu_runtime.suggest_block_size, %[[DIM1]], %[[C1]], %[[C1]] -> index, index, index
// CHECK: %[[G1:.*]] = arith.ceildivui %[[DIM1]], %[[B]]#0 : index
// CHECK: %[[RES2:.*]] = scf.parallel
// CHECK-SAME: (%[[ARG1:.*]], %[[ARG2:.*]], %[[ARG3:.*]], %[[ARG4:.*]], %[[ARG5:.*]], %[[ARG6:.*]]) =
// CHECK-SAME: (%[[C0]], %[[C0]], %[[C0]], %[[C0]], %[[C0]], %[[C0]]) to
// CHECK-SAME: (%[[G1]], %[[C1]], %[[C1]], %[[B]]#0, %[[C1]], %[[C1]]) step
// CHECK-SAME: (%[[C1]], %[[C1]], %[[C1]], %[[C1]], %[[C1]], %[[C1]]) init
// CHECK-SAME: (%[[INIT]])
// CHECK: %[[IDX1:.*]] = arith.muli %[[ARG1]], %[[B]]#0 : index
// CHECK: %[[IDX2:.*]] = arith.addi %[[IDX1]], %[[ARG4]] : index
// CHECK: %[[IN1:.*]] = arith.cmpi slt, %[[IDX2]], %[[DIM1]] : index
// CHECK: %[[IFRES:.*]] = scf.if %[[IN1]] -> (f64) {
// CHECK: %[[VAL:.*]] = memref.load %[[MEM1]][%[[IDX2]]] : memref<?xf64>
// CHECK: memref.store %[[VAL]], %[[MEM2]][%[[IDX2]]] : memref<?xf64>
// CHECK: scf.yield %[[VAL]] : f64
// CHECK: } else {
// CHECK: scf.yield %[[NEUTRAL]] : f64
// CHECK: }
// CHECK: scf.reduce(%[[IFRES]]) : f64 {
// CHECK: ^bb0(%[[LHS:.*]]: f64, %[[RHS:.*]]: f64):
// CHECK: %[[REDUCE_RES:.*]] = arith.mulf %[[LHS]], %[[RHS]] : f64
// CHECK: scf.reduce.return %[[REDUCE_RES]] : f64
// CHECK: }
// CHECK: scf.yield
// CHECK: {mapping = [#gpu.loop_dim_map<processor = block_x, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = block_y, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = block_z, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_x, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_y, map = (d0) -> (d0), bound = (d0) -> (d0)>, #gpu.loop_dim_map<processor = thread_z, map = (d0) -> (d0), bound = (d0) -> (d0)>]}
// CHECK: return %[[RES1]] : f64
func.func @check1DReduction(%arg0: memref<?xf64>, %arg1: memref<?xf64>, %arg2: f64) -> f64 {
  %c1 = arith.constant 1 : index
  %c0 = arith.constant 0 : index
  %0 = memref.dim %arg0, %c0 : memref<?xf64>
  %1 = numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false> -> f64 {
    %2 = scf.parallel (%arg4) = (%c0) to (%0) step (%c1) init(%arg2) -> f64 {
      %3 = memref.load %arg0[%arg4] : memref<?xf64>
      memref.store %3, %arg1[%arg4] : memref<?xf64>
      scf.reduce(%3) : f64 {
      ^bb0(%lhs: f64, %rhs: f64):
        %4 = arith.mulf %lhs, %rhs : f64
        scf.reduce.return %4 : f64
      }
      scf.yield
    }
    numba_util.env_region_yield %2: f64
  }
  return %1 : f64
}
