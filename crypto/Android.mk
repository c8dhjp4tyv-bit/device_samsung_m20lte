LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)
LOCAL_MODULE := m20lte-crypto-ready
LOCAL_MODULE_TAGS := optional
LOCAL_SRC_FILES := crypto_ready.cpp
LOCAL_MULTILIB := 64
LOCAL_CPPFLAGS := -Wall -Wextra -Werror
LOCAL_SHARED_LIBRARIES := \
    android.hardware.gatekeeper@1.0 \
    android.hardware.keymaster@3.0 \
    libbinder_ndk \
    libhidlbase \
    libutils \
    liblog
include $(BUILD_EXECUTABLE)
