// Recovery readiness check only: never create, upgrade, or delete a key.
#include <android/binder_auto_utils.h>
#include <android/binder_manager.h>
#include <android/hardware/gatekeeper/1.0/IGatekeeper.h>
#include <android/hardware/keymaster/3.0/IKeymasterDevice.h>
#include <cstdio>

int main() {
    using android::hardware::gatekeeper::V1_0::IGatekeeper;
    using android::hardware::keymaster::V3_0::IKeymasterDevice;
    // init.svc=running only proves fork/exec, not successful HAL registration.
    auto km = IKeymasterDevice::tryGetService("default");
    auto gk = IGatekeeper::tryGetService("default");
    ndk::SpAIBinder ks(AServiceManager_checkService(
            "android.system.keystore2.IKeystoreService/default"));
    std::fprintf(stderr, "registered: keymaster3=%d gatekeeper1=%d keystore2=%d\n",
                 km != nullptr, gk != nullptr, ks.get() != nullptr);
    return km != nullptr && gk != nullptr && ks.get() != nullptr ? 0 : 1;
}
