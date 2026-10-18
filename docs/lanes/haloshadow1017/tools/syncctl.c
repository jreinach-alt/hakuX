/*
 * Positive control for L5 (#1038): does the validation layer, loaded the way l5.sh loads it
 * (VK_LAYER_PATH, VK_LAYER_SETTINGS_PATH, VkValidationFeaturesEXT with sync on, lavapipe),
 * report a synchronization hazard at all? Two vkCmdFillBuffer on one range with no barrier
 * between them is a WRITE_AFTER_WRITE hazard; the layer must print SYNC-HAZARD-WRITE-AFTER-WRITE.
 *
 * `syncctl core` is L6's control (core validation): one fill at dstOffset 2, which is not a
 * multiple of 4. The layer must print VUID-vkCmdFillBuffer-dstOffset-00025.
 *
 *   cc -I$NX/root/usr/include syncctl.c -o syncctl -L$NX/root/usr/lib/x86_64-linux-gnu -l:libvulkan.so.1
 */
#include <stdio.h>
#include <string.h>
#include <vulkan/vulkan.h>

static VKAPI_ATTR VkBool32 VKAPI_CALL cb(VkDebugUtilsMessageSeverityFlagBitsEXT sev,
                                         VkDebugUtilsMessageTypeFlagsEXT type,
                                         const VkDebugUtilsMessengerCallbackDataEXT *d, void *u)
{
    printf("[vk] %s\n", d->pMessage);
    return VK_FALSE;
}

#define CK(x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS) { printf("FAIL %s = %d\n", #x, r_); return 1; } } while (0)

int main(int argc, char **argv)
{
    int core = argc > 1 && !strcmp(argv[1], "core");
    const char *layers[] = { "VK_LAYER_KHRONOS_validation" };
    const char *exts[] = { VK_EXT_DEBUG_UTILS_EXTENSION_NAME };
    VkValidationFeatureEnableEXT en[] = { VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT };
    VkValidationFeaturesEXT vf = { .sType = VK_STRUCTURE_TYPE_VALIDATION_FEATURES_EXT,
                                   .enabledValidationFeatureCount = 1,
                                   .pEnabledValidationFeatures = en };
    VkApplicationInfo ai = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion = VK_API_VERSION_1_1 };
    VkInstanceCreateInfo ici = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pNext = &vf,
                                 .pApplicationInfo = &ai, .enabledLayerCount = 1,
                                 .ppEnabledLayerNames = layers, .enabledExtensionCount = 1,
                                 .ppEnabledExtensionNames = exts };
    VkInstance inst;
    CK(vkCreateInstance(&ici, NULL, &inst));
    PFN_vkCreateDebugUtilsMessengerEXT cdm =
        (PFN_vkCreateDebugUtilsMessengerEXT)vkGetInstanceProcAddr(inst, "vkCreateDebugUtilsMessengerEXT");
    VkDebugUtilsMessengerCreateInfoEXT mi = {
        .sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT,
        .messageSeverity = VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT |
                           VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT,
        .messageType = VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT |
                       VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT |
                       VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT,
        .pfnUserCallback = cb };
    VkDebugUtilsMessengerEXT m;
    CK(cdm(inst, &mi, NULL, &m));

    uint32_t n = 1;
    VkPhysicalDevice pd;
    vkEnumeratePhysicalDevices(inst, &n, &pd);
    float prio = 1;
    VkDeviceQueueCreateInfo qi = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
                                   .queueFamilyIndex = 0, .queueCount = 1, .pQueuePriorities = &prio };
    VkDeviceCreateInfo dci = { .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
                               .queueCreateInfoCount = 1, .pQueueCreateInfos = &qi };
    VkDevice dev;
    CK(vkCreateDevice(pd, &dci, NULL, &dev));

    VkBufferCreateInfo bi = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = 4096,
                              .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT };
    VkBuffer buf;
    CK(vkCreateBuffer(dev, &bi, NULL, &buf));
    VkMemoryRequirements mr;
    vkGetBufferMemoryRequirements(dev, buf, &mr);
    uint32_t mt = 0;
    while (!(mr.memoryTypeBits & (1u << mt))) mt++;
    VkMemoryAllocateInfo mai = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
                                 .allocationSize = mr.size, .memoryTypeIndex = mt };
    VkDeviceMemory mem;
    CK(vkAllocateMemory(dev, &mai, NULL, &mem));
    CK(vkBindBufferMemory(dev, buf, mem, 0));

    VkCommandPoolCreateInfo pci = { .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO };
    VkCommandPool pool;
    CK(vkCreateCommandPool(dev, &pci, NULL, &pool));
    VkCommandBufferAllocateInfo cai = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
                                        .commandPool = pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
                                        .commandBufferCount = 1 };
    VkCommandBuffer cmd;
    CK(vkAllocateCommandBuffers(dev, &cai, &cmd));
    VkCommandBufferBeginInfo cbi = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };
    CK(vkBeginCommandBuffer(cmd, &cbi));
    if (core) {
        printf("recording one fill at dstOffset 2\n");
        fflush(stdout);
        vkCmdFillBuffer(cmd, buf, 2, 256, 1);
    } else {
        printf("recording two fills with no barrier\n");
        fflush(stdout);
        vkCmdFillBuffer(cmd, buf, 0, 256, 1);
        vkCmdFillBuffer(cmd, buf, 0, 256, 2);
    }
    CK(vkEndCommandBuffer(cmd));
    printf("done\n");
    return 0;
}
