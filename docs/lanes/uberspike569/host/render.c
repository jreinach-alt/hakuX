/*
 * Render one fragment shader on the host (lavapipe) and dump the target.
 *
 *   render VS.spv FS.spv UBO.bin TEXKINDS OUT.raw
 *
 * TEXKINDS is four characters, one per sampler binding 0..3 in set 0:
 * '2' sampler2D, 'c' samplerCube, 'u' usampler2D, '3' sampler3D, '-' unused.
 * The fragment shader's uniform block is set 1 binding 1, filled from
 * UBO.bin verbatim. The target is 64x64 RGBA32F, cleared to -7 so a
 * discarded fragment reads as the clear; OUT.raw is its bytes.
 *
 * Textures, samplers and geometry are fixed (seeded), so two runs that differ
 * only in FS.spv and UBO.bin differ only in what those shaders compute: the
 * #569 P6 render check draws each specialised shader and its ubershader this
 * way and compares the bytes (render_check.py).
 *
 * Vulkan via the system loader; point it at lavapipe with
 * VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json.
 */
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>
#include <dlfcn.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define W 64
#define H 64
#define TEX 16

#define FN(name) static PFN_##name name
FN(vkGetInstanceProcAddr);
FN(vkCreateInstance);
FN(vkEnumeratePhysicalDevices);
FN(vkGetPhysicalDeviceQueueFamilyProperties);
FN(vkGetPhysicalDeviceMemoryProperties);
FN(vkCreateDevice);
FN(vkGetDeviceQueue);
FN(vkCreateImage);
FN(vkGetImageMemoryRequirements);
FN(vkAllocateMemory);
FN(vkBindImageMemory);
FN(vkCreateImageView);
FN(vkCreateBuffer);
FN(vkGetBufferMemoryRequirements);
FN(vkBindBufferMemory);
FN(vkMapMemory);
FN(vkCreateSampler);
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
FN(vkCmdPipelineBarrier);
FN(vkCmdCopyBufferToImage);
FN(vkCmdCopyImageToBuffer);
FN(vkCmdBeginRenderPass);
FN(vkCmdEndRenderPass);
FN(vkCmdBindPipeline);
FN(vkCmdBindDescriptorSets);
FN(vkCmdDraw);
FN(vkQueueSubmit);
FN(vkQueueWaitIdle);

#define CHECK(x) do { VkResult r_ = (x); if (r_ != VK_SUCCESS) { \
    fprintf(stderr, "render: %s failed: %d\n", #x, r_); exit(1); } } while (0)

static VkDevice dev;
static VkPhysicalDevice pdev;
static VkQueue queue;
static VkCommandPool pool;

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
    fprintf(stderr, "render: no memory type\n");
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

static VkCommandBuffer begin_cmd(void)
{
    VkCommandBufferAllocateInfo ai = {
        VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO };
    ai.commandPool = pool;
    ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    ai.commandBufferCount = 1;
    VkCommandBuffer cb;
    CHECK(vkAllocateCommandBuffers(dev, &ai, &cb));
    VkCommandBufferBeginInfo bi = {
        VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };
    CHECK(vkBeginCommandBuffer(cb, &bi));
    return cb;
}

static void submit(VkCommandBuffer cb)
{
    CHECK(vkEndCommandBuffer(cb));
    VkSubmitInfo si = { VK_STRUCTURE_TYPE_SUBMIT_INFO };
    si.commandBufferCount = 1;
    si.pCommandBuffers = &cb;
    CHECK(vkQueueSubmit(queue, 1, &si, VK_NULL_HANDLE));
    CHECK(vkQueueWaitIdle(queue));
}

static void barrier(VkCommandBuffer cb, VkImage img, uint32_t layers,
                    VkImageLayout from, VkImageLayout to)
{
    VkImageMemoryBarrier b = { VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER };
    b.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;
    b.dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;
    b.oldLayout = from;
    b.newLayout = to;
    b.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    b.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    b.image = img;
    b.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    b.subresourceRange.levelCount = 1;
    b.subresourceRange.layerCount = layers;
    vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                         VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 0, NULL, 0,
                         NULL, 1, &b);
}

static uint32_t seed = 0x569u;
static uint32_t rnd(void)
{
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}

/* One texture of a kind, filled with seeded bytes, in SHADER_READ layout. */
static VkImageView make_texture(char kind, VkSampler *sampler)
{
    VkImageCreateInfo ii = { VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO };
    VkImageViewCreateInfo vi = { VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO };
    uint32_t layers = 1, depth = 1;
    ii.imageType = VK_IMAGE_TYPE_2D;
    vi.viewType = VK_IMAGE_VIEW_TYPE_2D;
    ii.format = VK_FORMAT_R8G8B8A8_UNORM;
    bool linear = true;
    switch (kind) {
    case 'c':
        layers = 6;
        ii.flags = VK_IMAGE_CREATE_CUBE_COMPATIBLE_BIT;
        vi.viewType = VK_IMAGE_VIEW_TYPE_CUBE;
        break;
    case 'u':
        ii.format = VK_FORMAT_R32_UINT;
        linear = false;
        break;
    case '3':
        ii.imageType = VK_IMAGE_TYPE_3D;
        vi.viewType = VK_IMAGE_VIEW_TYPE_3D;
        depth = TEX;
        break;
    default:
        break;
    }
    ii.extent = (VkExtent3D){ TEX, TEX, depth };
    ii.mipLevels = 1;
    ii.arrayLayers = layers;
    ii.samples = VK_SAMPLE_COUNT_1_BIT;
    ii.tiling = VK_IMAGE_TILING_OPTIMAL;
    ii.usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    VkImage img;
    CHECK(vkCreateImage(dev, &ii, NULL, &img));
    VkMemoryRequirements mr;
    vkGetImageMemoryRequirements(dev, img, &mr);
    VkMemoryAllocateInfo ai = { VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO };
    ai.allocationSize = mr.size;
    ai.memoryTypeIndex = mem_type(mr.memoryTypeBits, 0);
    VkDeviceMemory m;
    CHECK(vkAllocateMemory(dev, &ai, NULL, &m));
    CHECK(vkBindImageMemory(dev, img, m, 0));

    size_t bytes = (size_t)TEX * TEX * depth * layers * 4;
    void *map;
    VkBuffer stage = make_buffer(bytes, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, &map);
    for (size_t i = 0; i < bytes; i++) {
        ((uint8_t *)map)[i] = rnd() >> 7;
    }
    VkCommandBuffer cb = begin_cmd();
    barrier(cb, img, layers, VK_IMAGE_LAYOUT_UNDEFINED,
            VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    VkBufferImageCopy c = { 0 };
    c.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    c.imageSubresource.layerCount = layers;
    c.imageExtent = ii.extent;
    vkCmdCopyBufferToImage(cb, stage, img,
                           VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &c);
    barrier(cb, img, layers, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
            VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
    submit(cb);

    vi.image = img;
    vi.format = ii.format;
    vi.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    vi.subresourceRange.levelCount = 1;
    vi.subresourceRange.layerCount = layers;
    VkImageView view;
    CHECK(vkCreateImageView(dev, &vi, NULL, &view));

    VkSamplerCreateInfo si = { VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO };
    si.magFilter = si.minFilter = linear ? VK_FILTER_LINEAR : VK_FILTER_NEAREST;
    si.addressModeU = si.addressModeV = si.addressModeW =
        VK_SAMPLER_ADDRESS_MODE_REPEAT;
    si.maxLod = 0.0f;
    CHECK(vkCreateSampler(dev, &si, NULL, sampler));
    return view;
}

static VkShaderModule load_module(const char *path)
{
    size_t len;
    void *code = read_file(path, &len);
    VkShaderModuleCreateInfo ci = { VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO };
    ci.codeSize = len;
    ci.pCode = code;
    VkShaderModule m;
    CHECK(vkCreateShaderModule(dev, &ci, NULL, &m));
    return m;
}

int main(int argc, char **argv)
{
    if (argc != 6 || strlen(argv[4]) != 4) {
        fprintf(stderr, "usage: render VS.spv FS.spv UBO.bin TEXKINDS OUT.raw\n");
        return 2;
    }

    void *lib = dlopen("libvulkan.so.1", RTLD_NOW);
    if (!lib) { fprintf(stderr, "render: %s\n", dlerror()); return 1; }
    vkGetInstanceProcAddr = (PFN_vkGetInstanceProcAddr)dlsym(lib, "vkGetInstanceProcAddr");
#define GI(name) name = (PFN_##name)vkGetInstanceProcAddr(inst, #name)
    VkInstance inst = VK_NULL_HANDLE;
    GI(vkCreateInstance);
    VkApplicationInfo app = { VK_STRUCTURE_TYPE_APPLICATION_INFO };
    app.apiVersion = VK_API_VERSION_1_1;
    VkInstanceCreateInfo ici = { VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO };
    ici.pApplicationInfo = &app;
    CHECK(vkCreateInstance(&ici, NULL, &inst));
    GI(vkEnumeratePhysicalDevices); GI(vkGetPhysicalDeviceQueueFamilyProperties);
    GI(vkGetPhysicalDeviceMemoryProperties); GI(vkCreateDevice);
    GI(vkGetDeviceQueue); GI(vkCreateImage); GI(vkGetImageMemoryRequirements);
    GI(vkAllocateMemory); GI(vkBindImageMemory); GI(vkCreateImageView);
    GI(vkCreateBuffer); GI(vkGetBufferMemoryRequirements); GI(vkBindBufferMemory);
    GI(vkMapMemory); GI(vkCreateSampler); GI(vkCreateDescriptorSetLayout);
    GI(vkCreatePipelineLayout); GI(vkCreateDescriptorPool);
    GI(vkAllocateDescriptorSets); GI(vkUpdateDescriptorSets);
    GI(vkCreateRenderPass); GI(vkCreateFramebuffer); GI(vkCreateShaderModule);
    GI(vkCreateGraphicsPipelines); GI(vkCreateCommandPool);
    GI(vkAllocateCommandBuffers); GI(vkBeginCommandBuffer);
    GI(vkEndCommandBuffer); GI(vkCmdPipelineBarrier); GI(vkCmdCopyBufferToImage);
    GI(vkCmdCopyImageToBuffer); GI(vkCmdBeginRenderPass); GI(vkCmdEndRenderPass);
    GI(vkCmdBindPipeline); GI(vkCmdBindDescriptorSets); GI(vkCmdDraw);
    GI(vkQueueSubmit); GI(vkQueueWaitIdle);

    uint32_t n = 1;
    CHECK(vkEnumeratePhysicalDevices(inst, &n, &pdev));
    VkQueueFamilyProperties qf[8];
    uint32_t nq = 8;
    vkGetPhysicalDeviceQueueFamilyProperties(pdev, &nq, qf);
    uint32_t qi = 0;
    while (qi < nq && !(qf[qi].queueFlags & VK_QUEUE_GRAPHICS_BIT)) qi++;
    float prio = 1.0f;
    VkDeviceQueueCreateInfo qci = { VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO };
    qci.queueFamilyIndex = qi;
    qci.queueCount = 1;
    qci.pQueuePriorities = &prio;
    VkDeviceCreateInfo dci = { VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO };
    dci.queueCreateInfoCount = 1;
    dci.pQueueCreateInfos = &qci;
    CHECK(vkCreateDevice(pdev, &dci, NULL, &dev));
    vkGetDeviceQueue(dev, qi, 0, &queue);

    VkCommandPoolCreateInfo pci = { VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO };
    pci.queueFamilyIndex = qi;
    CHECK(vkCreateCommandPool(dev, &pci, NULL, &pool));

    /* Textures: the same seeded content for a given TEXKINDS. */
    VkDescriptorImageInfo img_info[4];
    for (int i = 0; i < 4; i++) {
        char k = argv[4][i] == '-' ? '2' : argv[4][i];
        img_info[i].imageView = make_texture(k, &img_info[i].sampler);
        img_info[i].imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    }

    size_t ubo_len;
    void *ubo_data = read_file(argv[3], &ubo_len);
    void *ubo_map;
    VkBuffer ubo = make_buffer(4096, VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT, &ubo_map);
    memset(ubo_map, 0, 4096);
    memcpy(ubo_map, ubo_data, ubo_len);

    VkDescriptorSetLayoutBinding b0[4];
    for (int i = 0; i < 4; i++) {
        b0[i] = (VkDescriptorSetLayoutBinding){
            i, VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1,
            VK_SHADER_STAGE_FRAGMENT_BIT, NULL };
    }
    VkDescriptorSetLayoutBinding b1 = {
        1, VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1, VK_SHADER_STAGE_FRAGMENT_BIT,
        NULL };
    VkDescriptorSetLayout dsl[2];
    VkDescriptorSetLayoutCreateInfo dli = {
        VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO };
    dli.bindingCount = 4;
    dli.pBindings = b0;
    CHECK(vkCreateDescriptorSetLayout(dev, &dli, NULL, &dsl[0]));
    dli.bindingCount = 1;
    dli.pBindings = &b1;
    CHECK(vkCreateDescriptorSetLayout(dev, &dli, NULL, &dsl[1]));

    VkPipelineLayoutCreateInfo pli = {
        VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO };
    pli.setLayoutCount = 2;
    pli.pSetLayouts = dsl;
    VkPipelineLayout layout;
    CHECK(vkCreatePipelineLayout(dev, &pli, NULL, &layout));

    VkDescriptorPoolSize ps[2] = {
        { VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 4 },
        { VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1 },
    };
    VkDescriptorPoolCreateInfo dpi = { VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO };
    dpi.maxSets = 2;
    dpi.poolSizeCount = 2;
    dpi.pPoolSizes = ps;
    VkDescriptorPool dpool;
    CHECK(vkCreateDescriptorPool(dev, &dpi, NULL, &dpool));
    VkDescriptorSetAllocateInfo dsa = {
        VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO };
    dsa.descriptorPool = dpool;
    dsa.descriptorSetCount = 2;
    dsa.pSetLayouts = dsl;
    VkDescriptorSet sets[2];
    CHECK(vkAllocateDescriptorSets(dev, &dsa, sets));
    VkDescriptorBufferInfo ubi = { ubo, 0, 4096 };
    VkWriteDescriptorSet wr[2] = {
        { VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, sets[0], 0, 0, 4,
          VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, img_info, NULL, NULL },
        { VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, NULL, sets[1], 1, 0, 1,
          VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, NULL, &ubi, NULL },
    };
    vkUpdateDescriptorSets(dev, 2, wr, 0, NULL);

    /* Target */
    VkImageCreateInfo ti = { VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO };
    ti.imageType = VK_IMAGE_TYPE_2D;
    ti.format = VK_FORMAT_R32G32B32A32_SFLOAT;
    ti.extent = (VkExtent3D){ W, H, 1 };
    ti.mipLevels = ti.arrayLayers = 1;
    ti.samples = VK_SAMPLE_COUNT_1_BIT;
    ti.tiling = VK_IMAGE_TILING_OPTIMAL;
    ti.usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT |
               VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
    VkImage target;
    CHECK(vkCreateImage(dev, &ti, NULL, &target));
    VkMemoryRequirements mr;
    vkGetImageMemoryRequirements(dev, target, &mr);
    VkMemoryAllocateInfo mai = { VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO };
    mai.allocationSize = mr.size;
    mai.memoryTypeIndex = mem_type(mr.memoryTypeBits, 0);
    VkDeviceMemory tm;
    CHECK(vkAllocateMemory(dev, &mai, NULL, &tm));
    CHECK(vkBindImageMemory(dev, target, tm, 0));
    VkImageViewCreateInfo tvi = { VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO };
    tvi.image = target;
    tvi.viewType = VK_IMAGE_VIEW_TYPE_2D;
    tvi.format = ti.format;
    tvi.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    tvi.subresourceRange.levelCount = tvi.subresourceRange.layerCount = 1;
    VkImageView tview;
    CHECK(vkCreateImageView(dev, &tvi, NULL, &tview));

    VkAttachmentDescription ad = { 0 };
    ad.format = ti.format;
    ad.samples = VK_SAMPLE_COUNT_1_BIT;
    ad.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
    ad.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    ad.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    ad.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    ad.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    ad.finalLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    VkAttachmentReference ar = { 0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL };
    VkSubpassDescription sd = { 0 };
    sd.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
    sd.colorAttachmentCount = 1;
    sd.pColorAttachments = &ar;
    VkRenderPassCreateInfo rpi = { VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO };
    rpi.attachmentCount = 1;
    rpi.pAttachments = &ad;
    rpi.subpassCount = 1;
    rpi.pSubpasses = &sd;
    VkRenderPass rp;
    CHECK(vkCreateRenderPass(dev, &rpi, NULL, &rp));
    VkFramebufferCreateInfo fbi = { VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO };
    fbi.renderPass = rp;
    fbi.attachmentCount = 1;
    fbi.pAttachments = &tview;
    fbi.width = W;
    fbi.height = H;
    fbi.layers = 1;
    VkFramebuffer fb;
    CHECK(vkCreateFramebuffer(dev, &fbi, NULL, &fb));

    /* Pipeline */
    VkPipelineShaderStageCreateInfo st[2] = {
        { VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0,
          VK_SHADER_STAGE_VERTEX_BIT, load_module(argv[1]), "main", NULL },
        { VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, NULL, 0,
          VK_SHADER_STAGE_FRAGMENT_BIT, load_module(argv[2]), "main", NULL },
    };
    VkPipelineVertexInputStateCreateInfo vis = {
        VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO };
    VkPipelineInputAssemblyStateCreateInfo ias = {
        VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO };
    ias.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    VkViewport vp = { 0, 0, W, H, 0, 1 };
    VkRect2D sc = { { 0, 0 }, { W, H } };
    VkPipelineViewportStateCreateInfo vps = {
        VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO };
    vps.viewportCount = vps.scissorCount = 1;
    vps.pViewports = &vp;
    vps.pScissors = &sc;
    VkPipelineRasterizationStateCreateInfo rs = {
        VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO };
    rs.polygonMode = VK_POLYGON_MODE_FILL;
    rs.cullMode = VK_CULL_MODE_NONE;
    rs.lineWidth = 1.0f;
    VkPipelineMultisampleStateCreateInfo ms = {
        VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO };
    ms.rasterizationSamples = VK_SAMPLE_COUNT_1_BIT;
    VkPipelineColorBlendAttachmentState cba = { 0 };
    cba.colorWriteMask = 0xF;
    VkPipelineColorBlendStateCreateInfo cbs = {
        VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO };
    cbs.attachmentCount = 1;
    cbs.pAttachments = &cba;
    VkGraphicsPipelineCreateInfo gpi = {
        VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO };
    gpi.stageCount = 2;
    gpi.pStages = st;
    gpi.pVertexInputState = &vis;
    gpi.pInputAssemblyState = &ias;
    gpi.pViewportState = &vps;
    gpi.pRasterizationState = &rs;
    gpi.pMultisampleState = &ms;
    gpi.pColorBlendState = &cbs;
    gpi.layout = layout;
    gpi.renderPass = rp;
    VkPipeline pipe;
    CHECK(vkCreateGraphicsPipelines(dev, VK_NULL_HANDLE, 1, &gpi, NULL, &pipe));

    void *rb_map;
    VkBuffer rb = make_buffer(W * H * 16, VK_BUFFER_USAGE_TRANSFER_DST_BIT,
                              &rb_map);
    VkCommandBuffer cb = begin_cmd();
    VkClearValue cv = { .color = { .float32 = { -7, -7, -7, -7 } } };
    VkRenderPassBeginInfo rbi = { VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO };
    rbi.renderPass = rp;
    rbi.framebuffer = fb;
    rbi.renderArea = sc;
    rbi.clearValueCount = 1;
    rbi.pClearValues = &cv;
    vkCmdBeginRenderPass(cb, &rbi, VK_SUBPASS_CONTENTS_INLINE);
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_GRAPHICS, pipe);
    vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_GRAPHICS, layout, 0, 2,
                            sets, 0, NULL);
    vkCmdDraw(cb, 3, 1, 0, 0);
    vkCmdEndRenderPass(cb);
    VkBufferImageCopy c = { 0 };
    c.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    c.imageSubresource.layerCount = 1;
    c.imageExtent = ti.extent;
    vkCmdCopyImageToBuffer(cb, target, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                           rb, 1, &c);
    submit(cb);

    FILE *f = fopen(argv[5], "wb");
    if (!f || fwrite(rb_map, 1, W * H * 16, f) != W * H * 16) {
        perror(argv[5]);
        return 1;
    }
    fclose(f);
    return 0;
}
