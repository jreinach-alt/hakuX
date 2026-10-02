/*
 * Run one vertex shader on the host (lavapipe) and dump what it wrote.
 *
 *   vsrender VS.spv UBO.bin COMPRESSED_MASK SEED OUT.raw
 *
 * 64 points, rasterizer discard, no fragment stage. Every one of the 16
 * attribute locations gets a vertex attribute (seeded values; R32_SINT at a
 * compressed location, R32G32B32A32_SFLOAT elsewhere), so the specialised
 * shader and the uber shader, which declares all sixteen, see the same
 * inputs. The uniform block is set 1 binding 0, filled from UBO.bin; the
 * shader writes its outputs to set 2 binding 0 (vshhost's ubDump), which is
 * OUT.raw.
 *
 * VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json for lavapipe.
 */
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>
#include <dlfcn.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NV 64
#define DUMP_BYTES (NV * 16 * 16)

#define FN(name) static PFN_##name name
FN(vkGetInstanceProcAddr);
FN(vkCreateInstance);
FN(vkEnumeratePhysicalDevices);
FN(vkGetPhysicalDeviceQueueFamilyProperties);
FN(vkGetPhysicalDeviceMemoryProperties);
FN(vkGetPhysicalDeviceFeatures);
FN(vkCreateDevice);
FN(vkGetDeviceQueue);
FN(vkCreateBuffer);
FN(vkGetBufferMemoryRequirements);
FN(vkAllocateMemory);
FN(vkBindBufferMemory);
FN(vkMapMemory);
FN(vkCreateDescriptorSetLayout);
FN(vkCreatePipelineLayout);
FN(vkCreateDescriptorPool);
FN(vkAllocateDescriptorSets);
FN(vkUpdateDescriptorSets);
FN(vkCreateRenderPass);
FN(vkCreateFramebuffer);
FN(vkCreateShaderModule);
FN(vkCreateGraphicsPipelines);
FN(vkCreateCommandPool);
FN(vkAllocateCommandBuffers);
FN(vkBeginCommandBuffer);
FN(vkEndCommandBuffer);
FN(vkCmdBeginRenderPass);
FN(vkCmdEndRenderPass);
FN(vkCmdBindPipeline);
FN(vkCmdBindDescriptorSets);
FN(vkCmdBindVertexBuffers);
FN(vkCmdDraw);
FN(vkQueueSubmit);
FN(vkQueueWaitIdle);

#define CHECK(x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS) { \
    fprintf(stderr, "vsrender: %s failed: %d\n", #x, r_); exit(1); } } while (0)

static VkDevice dev;
static VkPhysicalDevice pdev;

static void *read_file(const char *path, size_t *len)
{
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(1); }
    fseek(f, 0, SEEK_END);
    *len = ftell(f);
    fseek(f, 0, SEEK_SET);
    void *p = malloc(*len + 4);
    if (fread(p, 1, *len, f) != *len) { perror(path); exit(1); }
    fclose(f);
    return p;
}

static uint32_t mem_type(uint32_t bits, VkMemoryPropertyFlags want)
{
    VkPhysicalDeviceMemoryProperties mp;
    vkGetPhysicalDeviceMemoryProperties(pdev, &mp);
    for (uint32_t i = 0; i < mp.memoryTypeCount; i++) {
        if ((bits & (1u << i)) &&
            (mp.memoryTypes[i].propertyFlags & want) == want) {
            return i;
        }
    }
    fprintf(stderr, "vsrender: no memory type\n");
    exit(1);
}

static VkBuffer make_buffer(VkDeviceSize size, VkBufferUsageFlags usage,
                            void **map)
{
    VkBufferCreateInfo bi = { VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO };
    bi.size = size;
    bi.usage = usage;
    VkBuffer b;
    CHECK(vkCreateBuffer(dev, &bi, NULL, &b));
    VkMemoryRequirements mr;
    vkGetBufferMemoryRequirements(dev, b, &mr);
    VkMemoryAllocateInfo ai = { VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO };
    ai.allocationSize = mr.size;
    ai.memoryTypeIndex = mem_type(mr.memoryTypeBits,
                                  VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                                  VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    VkDeviceMemory m;
    CHECK(vkAllocateMemory(dev, &ai, NULL, &m));
    CHECK(vkBindBufferMemory(dev, b, m, 0));
    CHECK(vkMapMemory(dev, m, 0, size, 0, map));
    return b;
}

static uint32_t seed;
static uint32_t rnd(void)
{
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}

int main(int argc, char **argv)
{
    if (argc != 6) {
        fprintf(stderr, "vsrender VS.spv UBO.bin COMPRESSED_MASK SEED OUT.raw\n");
        return 2;
    }
    uint32_t compressed = strtoul(argv[3], NULL, 0);
    seed = strtoul(argv[4], NULL, 0) | 1;

    void *lib = dlopen("libvulkan.so.1", RTLD_NOW);
    if (!lib) { fprintf(stderr, "vsrender: no libvulkan\n"); return 1; }
    vkGetInstanceProcAddr = (PFN_vkGetInstanceProcAddr)dlsym(lib, "vkGetInstanceProcAddr");
#define IFN(name) name = (PFN_##name)vkGetInstanceProcAddr(inst, #name)
    VkInstance inst = VK_NULL_HANDLE;
    IFN(vkCreateInstance);
    VkApplicationInfo app = { VK_STRUCTURE_TYPE_APPLICATION_INFO };
    app.apiVersion = VK_API_VERSION_1_1;
    VkInstanceCreateInfo ici = { VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO };
    ici.pApplicationInfo = &app;
    CHECK(vkCreateInstance(&ici, NULL, &inst));
    IFN(vkEnumeratePhysicalDevices);
    IFN(vkGetPhysicalDeviceQueueFamilyProperties);
    IFN(vkGetPhysicalDeviceMemoryProperties);
    IFN(vkGetPhysicalDeviceFeatures);
    IFN(vkCreateDevice);
    uint32_t n = 1;
    VkResult er = vkEnumeratePhysicalDevices(inst, &n, &pdev);
    if (er != VK_SUCCESS && er != VK_INCOMPLETE) { fprintf(stderr, "vsrender: no device\n"); return 1; }

    VkPhysicalDeviceFeatures feat;
    vkGetPhysicalDeviceFeatures(pdev, &feat);
    VkPhysicalDeviceFeatures want = { 0 };
    want.vertexPipelineStoresAndAtomics = feat.vertexPipelineStoresAndAtomics;
    want.shaderClipDistance = feat.shaderClipDistance;
    float prio = 1.0f;
    VkDeviceQueueCreateInfo qci = { VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO };
    qci.queueFamilyIndex = 0;
    qci.queueCount = 1;
    qci.pQueuePriorities = &prio;
    VkDeviceCreateInfo dci = { VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO };
    dci.queueCreateInfoCount = 1;
    dci.pQueueCreateInfos = &qci;
    dci.pEnabledFeatures = &want;
    CHECK(vkCreateDevice(pdev, &dci, NULL, &dev));
#define DFN(name) name = (PFN_##name)vkGetInstanceProcAddr(inst, #name)
    DFN(vkGetDeviceQueue); DFN(vkCreateBuffer); DFN(vkGetBufferMemoryRequirements);
    DFN(vkAllocateMemory); DFN(vkBindBufferMemory); DFN(vkMapMemory);
    DFN(vkCreateDescriptorSetLayout); DFN(vkCreatePipelineLayout);
    DFN(vkCreateDescriptorPool); DFN(vkAllocateDescriptorSets);
    DFN(vkUpdateDescriptorSets); DFN(vkCreateRenderPass); DFN(vkCreateFramebuffer);
    DFN(vkCreateShaderModule); DFN(vkCreateGraphicsPipelines);
    DFN(vkCreateCommandPool); DFN(vkAllocateCommandBuffers);
    DFN(vkBeginCommandBuffer); DFN(vkEndCommandBuffer); DFN(vkCmdBeginRenderPass);
    DFN(vkCmdEndRenderPass); DFN(vkCmdBindPipeline); DFN(vkCmdBindDescriptorSets);
    DFN(vkCmdBindVertexBuffers); DFN(vkCmdDraw); DFN(vkQueueSubmit);
    DFN(vkQueueWaitIdle);
    VkQueue queue;
    vkGetDeviceQueue(dev, 0, 0, &queue);

    size_t vs_len, ubo_len;
    void *vs = read_file(argv[1], &vs_len);
    void *ubo_data = read_file(argv[2], &ubo_len);

    /* buffers */
    void *ubo_map, *dump_map, *vtx_map;
    VkBuffer ubo = make_buffer(65536, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT, &ubo_map);
    memset(ubo_map, 0, 65536);
    memcpy(ubo_map, ubo_data, ubo_len);
    VkBuffer dump = make_buffer(DUMP_BYTES, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT, &dump_map);
    memset(dump_map, 0xAB, DUMP_BYTES);
    VkBuffer vtx = make_buffer(16 * NV * 16, VK_BUFFER_USAGE_VERTEX_BUFFER_BIT, &vtx_map);
    float *vf = vtx_map;
    for (int a = 0; a < 16; a++) {
        for (int v = 0; v < NV; v++) {
            for (int k = 0; k < 4; k++) {
                uint32_t r = rnd();
                float x = -1.5f + 3.0f * (r & 0xFFFFFF) / (float)0x1000000;
                if (compressed & (1u << a)) {
                    memcpy(&vf[(a * NV + v) * 4 + k], &r, 4);
                } else {
                    vf[(a * NV + v) * 4 + k] = x;
                }
            }
        }
    }

    /* layouts: set 0 empty, set 1 the UBO, set 2 the dump */
    VkDescriptorSetLayout sl[3];
    VkDescriptorSetLayoutCreateInfo lci = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO };
    CHECK(vkCreateDescriptorSetLayout(dev, &lci, NULL, &sl[0]));
    VkDescriptorSetLayoutBinding b1 = { 0, VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1,
                                        VK_SHADER_STAGE_VERTEX_BIT, NULL };
    lci.bindingCount = 1;
    lci.pBindings = &b1;
    CHECK(vkCreateDescriptorSetLayout(dev, &lci, NULL, &sl[1]));
    VkDescriptorSetLayoutBinding b2 = { 0, VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1,
                                        VK_SHADER_STAGE_VERTEX_BIT, NULL };
    lci.pBindings = &b2;
    CHECK(vkCreateDescriptorSetLayout(dev, &lci, NULL, &sl[2]));
    VkPushConstantRange pcr = { VK_SHADER_STAGE_VERTEX_BIT, 16, 256 };
    VkPipelineLayoutCreateInfo plci = { VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO };
    plci.setLayoutCount = 3;
    plci.pSetLayouts = sl;
    plci.pushConstantRangeCount = 1;
    plci.pPushConstantRanges = &pcr;
    VkPipelineLayout pl;
    CHECK(vkCreatePipelineLayout(dev, &plci, NULL, &pl));

    VkDescriptorPoolSize ps[2] = { { VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1 },
                                   { VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1 } };
    VkDescriptorPoolCreateInfo dpci = { VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO };
    dpci.maxSets = 3;
    dpci.poolSizeCount = 2;
    dpci.pPoolSizes = ps;
    VkDescriptorPool dp;
    CHECK(vkCreateDescriptorPool(dev, &dpci, NULL, &dp));
    VkDescriptorSet ds[3];
    VkDescriptorSetAllocateInfo dsai = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO };
    dsai.descriptorPool = dp;
    dsai.descriptorSetCount = 3;
    dsai.pSetLayouts = sl;
    CHECK(vkAllocateDescriptorSets(dev, &dsai, ds));
    VkDescriptorBufferInfo ubi = { ubo, 0, VK_WHOLE_SIZE };
    VkDescriptorBufferInfo dbi = { dump, 0, VK_WHOLE_SIZE };
    VkWriteDescriptorSet w[2] = {
        { VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, ds[1], 0, 0, 1,
          VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, NULL, &ubi, NULL },
        { VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, ds[2], 0, 0, 1,
          VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, NULL, &dbi, NULL },
    };
    vkUpdateDescriptorSets(dev, 2, w, 0, NULL);

    VkRenderPassCreateInfo rpci = { VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO };
    VkSubpassDescription sub = { 0 };
    sub.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    rpci.subpassCount = 1;
    rpci.pSubpasses = &sub;
    VkRenderPass rp;
    CHECK(vkCreateRenderPass(dev, &rpci, NULL, &rp));
    VkFramebufferCreateInfo fci = { VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO };
    fci.renderPass = rp;
    fci.width = 1;
    fci.height = 1;
    fci.layers = 1;
    VkFramebuffer fb;
    CHECK(vkCreateFramebuffer(dev, &fci, NULL, &fb));

    VkShaderModuleCreateInfo smci = { VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO };
    smci.codeSize = vs_len;
    smci.pCode = vs;
    VkShaderModule sm;
    CHECK(vkCreateShaderModule(dev, &smci, NULL, &sm));
    VkPipelineShaderStageCreateInfo st = { VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO };
    st.stage = VK_SHADER_STAGE_VERTEX_BIT;
    st.module = sm;
    st.pName = "main";

    VkVertexInputBindingDescription vb[16];
    VkVertexInputAttributeDescription va[16];
    for (int a = 0; a < 16; a++) {
        vb[a] = (VkVertexInputBindingDescription){ a, 16, VK_VERTEX_INPUT_RATE_VERTEX };
        va[a] = (VkVertexInputAttributeDescription){
            a, a, (compressed & (1u << a)) ? VK_FORMAT_R32_SINT
                                           : VK_FORMAT_R32G32B32A32_SFLOAT, 0 };
    }
    VkPipelineVertexInputStateCreateInfo vis = { VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO };
    vis.vertexBindingDescriptionCount = 16;
    vis.pVertexBindingDescriptions = vb;
    vis.vertexAttributeDescriptionCount = 16;
    vis.pVertexAttributeDescriptions = va;
    VkPipelineInputAssemblyStateCreateInfo ia = { VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO };
    ia.topology = VK_PRIMITIVE_TOPOLOGY_POINT_LIST;
    VkPipelineRasterizationStateCreateInfo rs = { VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO };
    rs.rasterizerDiscardEnable = VK_TRUE;
    rs.lineWidth = 1.0f;
    VkGraphicsPipelineCreateInfo gci = { VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO };
    gci.stageCount = 1;
    gci.pStages = &st;
    gci.pVertexInputState = &vis;
    gci.pInputAssemblyState = &ia;
    gci.pRasterizationState = &rs;
    gci.layout = pl;
    gci.renderPass = rp;
    VkPipeline pipe;
    CHECK(vkCreateGraphicsPipelines(dev, VK_NULL_HANDLE, 1, &gci, NULL, &pipe));

    VkCommandPoolCreateInfo cpci = { VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO };
    VkCommandPool pool;
    CHECK(vkCreateCommandPool(dev, &cpci, NULL, &pool));
    VkCommandBufferAllocateInfo cbai = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO };
    cbai.commandPool = pool;
    cbai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cbai.commandBufferCount = 1;
    VkCommandBuffer cb;
    CHECK(vkAllocateCommandBuffers(dev, &cbai, &cb));
    VkCommandBufferBeginInfo cbbi = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };
    CHECK(vkBeginCommandBuffer(cb, &cbbi));
    VkRenderPassBeginInfo rpbi = { VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO };
    rpbi.renderPass = rp;
    rpbi.framebuffer = fb;
    rpbi.renderArea.extent.width = 1;
    rpbi.renderArea.extent.height = 1;
    vkCmdBeginRenderPass(cb, &rpbi, VK_SUBPASS_CONTENTS_INLINE);
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_GRAPHICS, pipe);
    vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_GRAPHICS, pl, 0, 3, ds, 0, NULL);
    VkBuffer bufs[16];
    VkDeviceSize offs[16];
    for (int a = 0; a < 16; a++) {
        bufs[a] = vtx;
        offs[a] = (VkDeviceSize)a * NV * 16;
    }
    vkCmdBindVertexBuffers(cb, 0, 16, bufs, offs);
    vkCmdDraw(cb, NV, 1, 0, 0);
    vkCmdEndRenderPass(cb);
    CHECK(vkEndCommandBuffer(cb));
    VkSubmitInfo si = { VK_STRUCTURE_TYPE_SUBMIT_INFO };
    si.commandBufferCount = 1;
    si.pCommandBuffers = &cb;
    CHECK(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE));
    CHECK(vkQueueWaitIdle(queue));

    FILE *f = fopen(argv[5], "wb");
    fwrite(dump_map, 1, DUMP_BYTES, f);
    fclose(f);
    return 0;
}
