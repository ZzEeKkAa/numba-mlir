// RUN: numba-mlir-opt --insert-gpu-alloc -split-input-file %s | FileCheck %s

// CHECK-LABEL: func @addt
// CHECK-SAME: (%[[ARG1:.*]]: memref<2x5xf32>, %[[ARG2:.*]]: memref<2x5xf32>)
func.func @addt(%arg0: memref<2x5xf32>, %arg1: memref<2x5xf32>) -> memref<2x5xf32> {
  %c0 = arith.constant 0 : index
  %c2 = arith.constant 2 : index
  %c1 = arith.constant 1 : index
  %c5 = arith.constant 5 : index
  // CHECK: %[[MEMREF0:.*]] = gpu.alloc host_shared () : memref<2x5xf32>
  // CHECK: memref.copy %[[ARG2]], %[[MEMREF0]] : memref<2x5xf32> to memref<2x5xf32>
  // CHECK: %[[MEMREF1:.*]] = gpu.alloc host_shared () : memref<2x5xf32>
  // CHECK: memref.copy %[[ARG1]], %[[MEMREF1]] : memref<2x5xf32> to memref<2x5xf32>

  %0 = memref.alloc() {alignment = 128 : i64} : memref<2x5xf32>
  // CHECK:  %[[MEMREF2:.*]] = gpu.alloc host_shared () : memref<2x5xf32>

  %c1_0 = arith.constant 1 : index
  %1 = affine.apply affine_map<(d0)[s0, s1] -> ((d0 - s0) ceildiv s1)>(%c2)[%c0, %c1]
  %2 = affine.apply affine_map<(d0)[s0, s1] -> ((d0 - s0) ceildiv s1)>(%c5)[%c0, %c1]
  gpu.launch blocks(%arg2, %arg3, %arg4) in (%arg8 = %1, %arg9 = %2, %arg10 = %c1_0) threads(%arg5, %arg6, %arg7) in (%arg11 = %c1_0, %arg12 = %c1_0, %arg13 = %c1_0) {
    // CHECK: %[[IDX1:.*]] = affine.apply #map1(%{{.*}})[%{{.*}}, %{{.*}}]
    %3 = affine.apply affine_map<(d0)[s0, s1] -> (d0 * s0 + s1)>(%arg2)[%c1, %c0]
    // CHECK: %[[IDX2:.*]] = affine.apply #map1(%{{.*}})[%{{.*}}, %{{.*}}]
    %4 = affine.apply affine_map<(d0)[s0, s1] -> (d0 * s0 + s1)>(%arg3)[%c1, %c0]
    // CHECK: %[[VAL1:.*]] = memref.load %[[MEMREF1]][%[[IDX1]], %[[IDX2]]] : memref<2x5xf32>
    %5 = memref.load %arg0[%3, %4] : memref<2x5xf32>
    // CHECK: %[[VAL2:.*]] = memref.load %[[MEMREF0]][%[[IDX1]], %[[IDX2]]] : memref<2x5xf32>
    %6 = memref.load %arg1[%3, %4] : memref<2x5xf32>
    // CHECK: %[[RES:.*]] = arith.addf %[[VAL1]], %[[VAL2]] : f32
    %7 = arith.addf %5, %6 : f32
    // CHECK: memref.store %[[RES]], %[[MEMREF2]][%[[IDX1]], %[[IDX2]]] : memref<2x5xf32>
    memref.store %7, %0[%3, %4] : memref<2x5xf32>
    gpu.terminator
  } {SCFToGPU_visited}
  return %0 : memref<2x5xf32>
}

// -----

// CHECK-LABEL: func @addt
// CHECK-SAME: (%[[ARG1:.*]]: memref<2x5xf32, strided<[?, ?], offset: ?>>, %[[ARG2:.*]]: memref<2x5xf32, strided<[?, ?], offset: ?>>)
func.func @addt(%arg0: memref<2x5xf32, strided<[?, ?], offset: ?>>, %arg1: memref<2x5xf32, strided<[?, ?], offset: ?>>) -> memref<2x5xf32> {
  %c0 = arith.constant 0 : index
  %c2 = arith.constant 2 : index
  %c1 = arith.constant 1 : index
  %c5 = arith.constant 5 : index
  // CHECK: %[[MEMREF0:.*]] = gpu.alloc host_shared () : memref<2x5xf32>
  // CHECK: %[[CAST0:.*]] = memref.cast %[[MEMREF0]] : memref<2x5xf32> to memref<2x5xf32, strided<[?, ?], offset: ?>>
  // CHECK: memref.copy %[[ARG2]], %[[CAST0]] : memref<2x5xf32, strided<[?, ?], offset: ?>> to memref<2x5xf32, strided<[?, ?], offset: ?>>
  // CHECK: %[[MEMREF1:.*]] = gpu.alloc host_shared () : memref<2x5xf32>
  // CHECK: %[[CAST1:.*]] = memref.cast %[[MEMREF1]] : memref<2x5xf32> to memref<2x5xf32, strided<[?, ?], offset: ?>>
  // CHECK: memref.copy %[[ARG1]], %[[CAST1]] : memref<2x5xf32, strided<[?, ?], offset: ?>> to memref<2x5xf32, strided<[?, ?], offset: ?>>

  %0 = memref.alloc() {alignment = 128 : i64} : memref<2x5xf32>
  // CHECK:  %[[MEMREF2:.*]] = gpu.alloc host_shared () : memref<2x5xf32>

  %c1_0 = arith.constant 1 : index
  %1 = affine.apply affine_map<(d0)[s0, s1] -> ((d0 - s0) ceildiv s1)>(%c2)[%c0, %c1]
  %2 = affine.apply affine_map<(d0)[s0, s1] -> ((d0 - s0) ceildiv s1)>(%c5)[%c0, %c1]
  gpu.launch blocks(%arg2, %arg3, %arg4) in (%arg8 = %1, %arg9 = %2, %arg10 = %c1_0) threads(%arg5, %arg6, %arg7) in (%arg11 = %c1_0, %arg12 = %c1_0, %arg13 = %c1_0) {
    // CHECK: %[[IDX1:.*]] = affine.apply #map1(%{{.*}})[%{{.*}}, %{{.*}}]
    %3 = affine.apply affine_map<(d0)[s0, s1] -> (d0 * s0 + s1)>(%arg2)[%c1, %c0]
    // CHECK: %[[IDX2:.*]] = affine.apply #map1(%{{.*}})[%{{.*}}, %{{.*}}]
    %4 = affine.apply affine_map<(d0)[s0, s1] -> (d0 * s0 + s1)>(%arg3)[%c1, %c0]
    // CHECK: %[[VAL1:.*]] = memref.load %[[CAST1]][%[[IDX1]], %[[IDX2]]] : memref<2x5xf32, strided<[?, ?], offset: ?>>
    %5 = memref.load %arg0[%3, %4] : memref<2x5xf32, strided<[?, ?], offset: ?>>
    // CHECK: %[[VAL2:.*]] = memref.load %[[CAST0]][%[[IDX1]], %[[IDX2]]] : memref<2x5xf32, strided<[?, ?], offset: ?>>
    %6 = memref.load %arg1[%3, %4] : memref<2x5xf32, strided<[?, ?], offset: ?>>
    // CHECK: %[[RES:.*]] = arith.addf %[[VAL1]], %[[VAL2]] : f32
    %7 = arith.addf %5, %6 : f32
    // CHECK: memref.store %[[RES]], %[[MEMREF2]][%[[IDX1]], %[[IDX2]]] : memref<2x5xf32>
    memref.store %7, %0[%3, %4] : memref<2x5xf32>
    gpu.terminator
  } {SCFToGPU_visited}
  return %0 : memref<2x5xf32>
}


// -----

// CHECK-LABEL: func @addt
// CHECK-SAME: (%[[ARG1:.*]]: memref<2x5xf32>, %[[ARG2:.*]]: memref<2x5xf32>)
func.func @addt(%arg0: memref<2x5xf32>, %arg1: memref<2x5xf32>) -> memref<2x5xf32> {
  %c0 = arith.constant 0 : index
  %c2 = arith.constant 2 : index
  %c1 = arith.constant 1 : index
  %c5 = arith.constant 5 : index
  // CHECK: %[[RES0:.*]] = numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false> -> memref<2x5xf32>
  // CHECK: %[[MEMREF0:.*]] = gpu.alloc host_shared () : memref<2x5xf32>
  // CHECK: memref.copy %[[ARG2]], %[[MEMREF0]] : memref<2x5xf32> to memref<2x5xf32>
  // CHECK: numba_util.env_region_yield %[[MEMREF0]] : memref<2x5xf32>

  // CHECK: %[[RES1:.*]] = numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false> -> memref<2x5xf32>
  // CHECK: %[[MEMREF1:.*]] = gpu.alloc host_shared () : memref<2x5xf32>
  // CHECK: memref.copy %[[ARG1]], %[[MEMREF1]] : memref<2x5xf32> to memref<2x5xf32>
  // CHECK: numba_util.env_region_yield %[[MEMREF1]] : memref<2x5xf32>

  %0 = memref.alloc() {alignment = 128 : i64} : memref<2x5xf32>
  // CHECK: %[[RES2:.*]] = numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false> -> memref<2x5xf32>
  // CHECK:  %[[MEMREF2:.*]] = gpu.alloc host_shared () : memref<2x5xf32>
  // CHECK: numba_util.env_region_yield %[[MEMREF2]] : memref<2x5xf32>

  %c1_0 = arith.constant 1 : index
  %1 = affine.apply affine_map<(d0)[s0, s1] -> ((d0 - s0) ceildiv s1)>(%c2)[%c0, %c1]
  %2 = affine.apply affine_map<(d0)[s0, s1] -> ((d0 - s0) ceildiv s1)>(%c5)[%c0, %c1]

  numba_util.env_region #gpu_runtime.region_desc<device = "test", spirv_major_version = 1, spirv_minor_version = 1, has_fp16 = true, has_fp64 = false> {
    gpu.launch blocks(%arg2, %arg3, %arg4) in (%arg8 = %1, %arg9 = %2, %arg10 = %c1_0) threads(%arg5, %arg6, %arg7) in (%arg11 = %c1_0, %arg12 = %c1_0, %arg13 = %c1_0) {
      // CHECK: %[[IDX1:.*]] = affine.apply #map1(%{{.*}})[%{{.*}}, %{{.*}}]
      %3 = affine.apply affine_map<(d0)[s0, s1] -> (d0 * s0 + s1)>(%arg2)[%c1, %c0]
      // CHECK: %[[IDX2:.*]] = affine.apply #map1(%{{.*}})[%{{.*}}, %{{.*}}]
      %4 = affine.apply affine_map<(d0)[s0, s1] -> (d0 * s0 + s1)>(%arg3)[%c1, %c0]
      // CHECK: %[[VAL1:.*]] = memref.load %[[RES1]][%[[IDX1]], %[[IDX2]]] : memref<2x5xf32>
      %5 = memref.load %arg0[%3, %4] : memref<2x5xf32>
      // CHECK: %[[VAL2:.*]] = memref.load %[[RES0]][%[[IDX1]], %[[IDX2]]] : memref<2x5xf32>
      %6 = memref.load %arg1[%3, %4] : memref<2x5xf32>
      // CHECK: %[[RES:.*]] = arith.addf %[[VAL1]], %[[VAL2]] : f32
      %7 = arith.addf %5, %6 : f32
      // CHECK: memref.store %[[RES]], %[[RES2]][%[[IDX1]], %[[IDX2]]] : memref<2x5xf32>
      memref.store %7, %0[%3, %4] : memref<2x5xf32>
      gpu.terminator
    } {SCFToGPU_visited}
  }
  return %0 : memref<2x5xf32>
}
