cmake_minimum_required(VERSION 3.22)
project(Werkzeug C)
get_filename_component(REPO_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../.." ABSOLUTE)
set(ZIRAN "${REPO_ROOT}/scripts/ziran.sh")
if(DEFINED ENV{WERK_ZIRAN_COMMAND} AND NOT "$ENV{WERK_ZIRAN_COMMAND}" STREQUAL "")
    get_filename_component(ZIRAN "$ENV{WERK_ZIRAN_COMMAND}" ABSOLUTE BASE_DIR "${REPO_ROOT}")
endif()
set(GENERATED "${CMAKE_BINARY_DIR}/ziran")
set(DEFINES --define ANDROID_BUILD)
if(ANDROID_ABI STREQUAL "arm64-v8a")
    list(APPEND DEFINES --define __aarch64__)
elseif(ANDROID_ABI STREQUAL "armeabi-v7a")
    list(APPEND DEFINES --define __arm__)
elseif(ANDROID_ABI STREQUAL "x86_64")
    list(APPEND DEFINES --define __x86_64__)
elseif(ANDROID_ABI STREQUAL "x86")
    list(APPEND DEFINES --define __i386__)
else()
    message(FATAL_ERROR "Unsupported Android ABI: ${ANDROID_ABI}")
endif()
set(LOCK_FLAGS --locked)
if(EXISTS "${REPO_ROOT}/ziran.local.toml")
    set(LOCK_FLAGS)
endif()
# Plain Gradle builds resolve the same packages as Make. F-Droid needs no
# source patches or machine-specific environment variables in its recipe.
function(werk_package variable package suffix)
    if(NOT "$ENV{${variable}}" STREQUAL "")
        set(path "$ENV{${variable}}")
    else()
        execute_process(COMMAND "${ZIRAN}" pkg path "${package}" ${LOCK_FLAGS}
            WORKING_DIRECTORY "${REPO_ROOT}" OUTPUT_VARIABLE path
            OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
        string(APPEND path "${suffix}")
    endif()
    set(${variable} "${path}" CACHE PATH "Locked ${package} source" FORCE)
endfunction()
werk_package(KRYON_DIR kryon "")
werk_package(ZIRAN_ROOT ziran "")
werk_package(RAYLIB_DIR raylib "/src")
werk_package(LIBOQS_DIR liboqs "")
werk_package(MONOCYPHER_DIR monocypher "")
werk_package(WORKBOOK_DIR workbook "")
file(GLOB_RECURSE SOURCE_INPUTS CONFIGURE_DEPENDS
    "${REPO_ROOT}/src/*.zi" "${WORKBOOK_DIR}/src/*.zi" "${KRYON_DIR}/src/*.zi" "${ZIRAN_ROOT}/std/*.zi")
list(APPEND SOURCE_INPUTS "${REPO_ROOT}/ziran.toml" "${REPO_ROOT}/ziran.lock")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${SOURCE_INPUTS})
execute_process(COMMAND "${ZIRAN}" build --project ${LOCK_FLAGS} ${DEFINES}
    # Native linker callbacks are reached through raylib, outside Zi's entry
    # graph. Keep them as the shared Android source generator does.
    --target=c --no-main -o "${GENERATED}" src/android_main.zi
    WORKING_DIRECTORY "${REPO_ROOT}" COMMAND_ERROR_IS_FATAL ANY)
file(GLOB GENERATED_SOURCES CONFIGURE_DEPENDS "${GENERATED}/*.c")
# Kryon's Android glue compiles its thread configurator with the same zi2c.
foreach(candidate "${ZIRAN_ROOT}/build/bin/zi2c" "${REPO_ROOT}/build/ziran-bootstrap/build/bin/zi2c")
    if(NOT ZI2C_BIN AND EXISTS "${candidate}")
        set(ZI2C_BIN "${candidate}")
    endif()
endforeach()
include("${KRYON_DIR}/cmake/KryonAndroid.cmake")
kryon_android_raylib("${RAYLIB_DIR}")
# The portable runtime that runs the app bundles, built from the locked Ziran
# for this ABI.
set(BUNDLE_RUNTIME_DIR "${CMAKE_BINARY_DIR}/bundle-runtime")
execute_process(COMMAND make -C "${ZIRAN_ROOT}" BOOTSTRAP=1 "BUILD_DIR=${BUNDLE_RUNTIME_DIR}"
    "CC=${CMAKE_C_COMPILER} --target=${CMAKE_C_COMPILER_TARGET} --sysroot=${CMAKE_SYSROOT}"
    "AR=${CMAKE_AR}" "OBJCOPY=${CMAKE_OBJCOPY}" "CFLAGS=-O2 -fPIC"
    "FRAMEFLAGS=-Wframe-larger-than=16384" "${BUNDLE_RUNTIME_DIR}/libziran.a"
    COMMAND_ERROR_IS_FATAL ANY)
# Account sync: liboqs for ML-DSA-44 account keys, Monocypher for the rest.
set(OQS_BUILD_ONLY_LIB ON CACHE BOOL "" FORCE)
set(OQS_USE_OPENSSL OFF CACHE BOOL "" FORCE)
set(OQS_MINIMAL_BUILD "SIG_ml_dsa_44" CACHE STRING "" FORCE)
set(OQS_DIST_BUILD OFF CACHE BOOL "" FORCE)
set(OQS_OPT_TARGET generic CACHE STRING "" FORCE)
foreach(oqs_x86_feature
        ADX AES AVX AVX2 AVX512 AVX512BW AVX512DQ AVX512F
        BMI1 BMI2 FMA PCLMULQDQ POPCNT SSE SSE2 SSE3 VPCLMULQDQ)
    set(OQS_USE_${oqs_x86_feature}_INSTRUCTIONS OFF CACHE BOOL "" FORCE)
endforeach()
add_subdirectory("${LIBOQS_DIR}" "${CMAKE_BINARY_DIR}/liboqs")
add_library(main SHARED ${GENERATED_SOURCES}
    "${MONOCYPHER_DIR}/src/monocypher.c" "${MONOCYPHER_DIR}/src/optional/monocypher-ed25519.c")
target_include_directories(main PRIVATE "${GENERATED}" "${ZIRAN_ROOT}/include"
    "${MONOCYPHER_DIR}/src" "${MONOCYPHER_DIR}/src/optional")
target_link_libraries(main oqs)
kryon_android_app(main)
target_link_libraries(main "${BUNDLE_RUNTIME_DIR}/libziran.a")
target_link_options(main PRIVATE -Wl,--wrap=pthread_attr_init)
# Linker build IDs include debug-path differences even after stripping. The
# installed code is identical; omit this note for reproducible signed APKs.
# https://f-droid.org/docs/Reproducible_Builds/#ndk-build-id
target_link_options(main PRIVATE -Wl,--build-id=none)
# Werkzeug has no handwritten native sources; every app translation unit above is
# generated from .zi for this ABI. raylib and the NDK own native_app_glue.
