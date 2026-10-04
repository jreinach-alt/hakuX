/*
 * gplharness: VK_EXT_graphics_pipeline_library on host Turnip, for the #569
 * addendum's design 2 (P5): the fragment (uber)shader as a prebuilt fragment
 * library, linked per vertex library.
 *
 *   gplharness <icd.so> <manifest> <reps>
 *
 * Same ICD loading, drm-shim, layout and fixed state as turnipcost569's
 * vkharness.c (whose pipeline this reproduces). Per manifest line
 * (<name> <vert.spv> <frag.spv> [<geom.spv>]) and rep, it times on this
 * thread's CPU clock:
 *
 *   mono      the monolithic vkCreateGraphicsPipelines (the baseline)
 *   vi, pr, fs, fo
 *             the four libraries: vertex input interface, pre-rasterization
 *             (VS [+GS]), fragment shader, fragment output interface
 *   link      a fast link of the four (no LINK_TIME_OPTIMIZATION)
 *   pr_r, fs_r
 *             the pre-raster and fragment libraries again, with
 *             RETAIN_LINK_TIME_OPTIMIZATION_INFO (what an optimised link needs)
 *   lto       a link of vi + pr_r + fs_r + fo with LINK_TIME_OPTIMIZATION
 *
 * Output TSV: name rep mono vi pr fs fo link pr_r fs_r lto  (ms)
 * Run with VK_ENABLE_PIPELINE_CACHE=false MESA_SHADER_CACHE_DISABLE=true.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>

#define CHECK(x) do { VkResult _r = (x); if (_r != VK_SUCCESS) { \
    fprintf(stderr, "%s:%d %s -> %d\n", __FILE__, __LINE__, #x, _r); exit(1); } } while (0)

typedef struct { uint32_t *w; size_t n; } Spv;

static Spv load_spv(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) { perror(path); exit(1); }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    Spv s = { malloc(sz), sz / 4 };
    if (fread(s.w, 1, sz, f) != (size_t)sz) { perror(path); exit(1); }
    fclose(f);
    return s;
}

static void reflect_vs(Spv s, uint32_t *loc_mask, int *has_push)
{
    enum { MAXID = 1 << 16 };
    static int32_t loc[MAXID];
    for (int i = 0; i < MAXID; i++) loc[i] = -1;
    *loc_mask = 0;
    *has_push = 0;
    for (size_t i = 5; i < s.n;) {
        uint32_t op = s.w[i] & 0xffff, len = s.w[i] >> 16;
        if (len == 0) break;
        if (op == 71 && s.w[i + 2] == 30 && s.w[i + 1] < MAXID) {
            loc[s.w[i + 1]] = s.w[i + 3];
        } else if (op == 59) {
            uint32_t id = s.w[i + 2], sc = s.w[i + 3];
            if (sc == 1 && id < MAXID && loc[id] >= 0) *loc_mask |= 1u << loc[id];
            if (sc == 9) *has_push = 1;
        }
        i += len;
    }
}

static double cpu_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts);
    return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

static PFN_vkCreateGraphicsPipelines CreateGP;
static PFN_vkDestroyPipeline DestroyP;
static VkDevice dev;

static VkPipeline make(const VkGraphicsPipelineCreateInfo *ci, double *ms)
{
    VkPipeline p;
    double c0 = cpu_ms();
    VkResult r = CreateGP(dev, VK_NULL_HANDLE, 1, ci, NULL, &p);
    *ms = cpu_ms() - c0;
    if (r != VK_SUCCESS) { fprintf(stderr, "vkCreateGraphicsPipelines -> %d\n", r); exit(1); }
    return p;
}

int main(int argc, char **argv)
{
    if (argc < 4) {
        fprintf(stderr, "usage: %s icd.so manifest reps\n", argv[0]);
        return 2;
    }
    void *icd = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!icd) { fprintf(stderr, "%s\n", dlerror()); return 1; }
    VkResult (*nego)(uint32_t *) =
        (VkResult (*)(uint32_t *))dlsym(icd, "vk_icdNegotiateLoaderICDInterfaceVersion");
    if (nego) { uint32_t v = 5; nego(&v); }
    PFN_vkGetInstanceProcAddr gipa =
        (PFN_vkGetInstanceProcAddr)dlsym(icd, "vk_icdGetInstanceProcAddr");
    int reps = atoi(argv[3]);

#define IPA(inst, name) PFN_##name name = (PFN_##name)gipa(inst, #name)
    IPA(NULL, vkCreateInstance);
    VkApplicationInfo app = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
                              .apiVersion = VK_API_VERSION_1_3 };
    VkInstanceCreateInfo ici = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                                 .pApplicationInfo = &app };
    VkInstance inst;
    CHECK(vkCreateInstance(&ici, NULL, &inst));
    IPA(inst, vkEnumeratePhysicalDevices);
    IPA(inst, vkGetPhysicalDeviceProperties2);
    IPA(inst, vkGetPhysicalDeviceFeatures2);
    IPA(inst, vkEnumerateDeviceExtensionProperties);
    IPA(inst, vkCreateDevice);
    IPA(inst, vkGetDeviceProcAddr);
    uint32_t npd = 1;
    VkPhysicalDevice pd;
    CHECK(vkEnumeratePhysicalDevices(inst, &npd, &pd));

    uint32_t next = 0;
    vkEnumerateDeviceExtensionProperties(pd, NULL, &next, NULL);
    VkExtensionProperties *exts = calloc(next, sizeof(*exts));
    vkEnumerateDeviceExtensionProperties(pd, NULL, &next, exts);
    int has_gpl = 0, has_pl = 0;
    for (uint32_t i = 0; i < next; i++) {
        if (!strcmp(exts[i].extensionName, VK_EXT_GRAPHICS_PIPELINE_LIBRARY_EXTENSION_NAME)) has_gpl = 1;
        if (!strcmp(exts[i].extensionName, VK_KHR_PIPELINE_LIBRARY_EXTENSION_NAME)) has_pl = 1;
    }
    VkPhysicalDeviceGraphicsPipelineLibraryPropertiesEXT gplp = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_GRAPHICS_PIPELINE_LIBRARY_PROPERTIES_EXT };
    VkPhysicalDeviceProperties2 p2 = { .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,
                                       .pNext = &gplp };
    vkGetPhysicalDeviceProperties2(pd, &p2);
    VkPhysicalDeviceGraphicsPipelineLibraryFeaturesEXT gplf = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_GRAPHICS_PIPELINE_LIBRARY_FEATURES_EXT };
    VkPhysicalDeviceFeatures2 f2 = { .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,
                                     .pNext = &gplf };
    vkGetPhysicalDeviceFeatures2(pd, &f2);
    fprintf(stderr, "device: %s driver 0x%x; GPL ext %d, pipeline_library %d, feature %d, "
            "fastLinking %d, independentInterpolationDecoration %d\n",
            p2.properties.deviceName, p2.properties.driverVersion, has_gpl, has_pl,
            gplf.graphicsPipelineLibrary, gplp.graphicsPipelineLibraryFastLinking,
            gplp.graphicsPipelineLibraryIndependentInterpolationDecoration);
    if (!has_gpl || !gplf.graphicsPipelineLibrary) {
        fprintf(stderr, "no graphics pipeline library\n");
        return 3;
    }

    float prio = 1.0f;
    VkDeviceQueueCreateInfo qci = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
                                    .queueFamilyIndex = 0, .queueCount = 1,
                                    .pQueuePriorities = &prio };
    VkPhysicalDeviceGraphicsPipelineLibraryFeaturesEXT gpl_on = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_GRAPHICS_PIPELINE_LIBRARY_FEATURES_EXT,
        .graphicsPipelineLibrary = VK_TRUE };
    VkPhysicalDeviceFeatures2 fon = { .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,
                                      .pNext = &gpl_on };
    fon.features = (VkPhysicalDeviceFeatures){ .geometryShader = VK_TRUE,
                                               .shaderTessellationAndGeometryPointSize = VK_TRUE,
                                               .fillModeNonSolid = VK_TRUE,
                                               .wideLines = VK_TRUE,
                                               .largePoints = VK_TRUE,
                                               .depthClamp = VK_TRUE };
    const char *dext[] = { VK_KHR_PIPELINE_LIBRARY_EXTENSION_NAME,
                           VK_EXT_GRAPHICS_PIPELINE_LIBRARY_EXTENSION_NAME };
    VkDeviceCreateInfo dci = { .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .pNext = &fon,
                               .queueCreateInfoCount = 1, .pQueueCreateInfos = &qci,
                               .enabledExtensionCount = 2, .ppEnabledExtensionNames = dext };
    CHECK(vkCreateDevice(pd, &dci, NULL, &dev));

#define DPA(name) PFN_##name name = (PFN_##name)vkGetDeviceProcAddr(dev, #name)
    DPA(vkCreateShaderModule);
    DPA(vkDestroyShaderModule);
    DPA(vkCreateDescriptorSetLayout);
    DPA(vkCreatePipelineLayout);
    DPA(vkDestroyPipelineLayout);
    DPA(vkCreateRenderPass);
    DPA(vkCreateGraphicsPipelines);
    DPA(vkDestroyPipeline);
    CreateGP = vkCreateGraphicsPipelines;
    DestroyP = vkDestroyPipeline;

    VkDescriptorSetLayoutBinding tb[4], ub[2];
    for (int i = 0; i < 4; i++) {
        tb[i] = (VkDescriptorSetLayoutBinding){ .binding = i,
            .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,
            .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_ALL_GRAPHICS };
    }
    for (int i = 0; i < 2; i++) {
        ub[i] = (VkDescriptorSetLayoutBinding){ .binding = i,
            .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
            .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_ALL_GRAPHICS };
    }
    VkDescriptorSetLayout sl[2];
    VkDescriptorSetLayoutCreateInfo dl0 = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
                                            .bindingCount = 4, .pBindings = tb };
    VkDescriptorSetLayoutCreateInfo dl1 = { .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
                                            .bindingCount = 2, .pBindings = ub };
    CHECK(vkCreateDescriptorSetLayout(dev, &dl0, NULL, &sl[0]));
    CHECK(vkCreateDescriptorSetLayout(dev, &dl1, NULL, &sl[1]));

    VkAttachmentDescription att[2] = {
        { .format = VK_FORMAT_R8G8B8A8_UNORM, .samples = VK_SAMPLE_COUNT_1_BIT,
          .loadOp = VK_ATTACHMENT_LOAD_OP_LOAD, .storeOp = VK_ATTACHMENT_STORE_OP_STORE,
          .stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE,
          .stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE,
          .initialLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
          .finalLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL },
        { .format = VK_FORMAT_D24_UNORM_S8_UINT, .samples = VK_SAMPLE_COUNT_1_BIT,
          .loadOp = VK_ATTACHMENT_LOAD_OP_LOAD, .storeOp = VK_ATTACHMENT_STORE_OP_STORE,
          .stencilLoadOp = VK_ATTACHMENT_LOAD_OP_LOAD,
          .stencilStoreOp = VK_ATTACHMENT_STORE_OP_STORE,
          .initialLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL,
          .finalLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL },
    };
    VkAttachmentReference cref = { 0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL };
    VkAttachmentReference dref = { 1, VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL };
    VkSubpassDescription sp = { .pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS,
                                .colorAttachmentCount = 1, .pColorAttachments = &cref,
                                .pDepthStencilAttachment = &dref };
    VkRenderPassCreateInfo rpci = { .sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,
                                    .attachmentCount = 2, .pAttachments = att,
                                    .subpassCount = 1, .pSubpasses = &sp };
    VkRenderPass rp;
    CHECK(vkCreateRenderPass(dev, &rpci, NULL, &rp));

    FILE *mf = fopen(argv[2], "r");
    if (!mf) { perror(argv[2]); return 1; }
    printf("name\trep\tmono\tvi\tpr\tfs\tfo\tlink\tpr_r\tfs_r\tlto\n");
    char line[4096];
    for (int rep = 0; rep < reps; rep++) {
    rewind(mf);
    while (fgets(line, sizeof(line), mf)) {
        char name[512], vp[1024], fp[1024], gp[1024];
        gp[0] = 0;
        if (line[0] == '#' ||
            sscanf(line, "%511s %1023s %1023s %1023s", name, vp, fp, gp) < 3) {
            continue;
        }
        Spv vs = load_spv(vp), fsv = load_spv(fp), gs = { 0 };
        if (gp[0]) gs = load_spv(gp);
        uint32_t loc_mask; int has_push;
        reflect_vs(vs, &loc_mask, &has_push);
        VkPushConstantRange pcr[2] = {
            { VK_SHADER_STAGE_GEOMETRY_BIT, 0, 16 },
            { VK_SHADER_STAGE_VERTEX_BIT, 16, 16 * 16 },
        };
        /* One layout for every library: GPL's independent-sets rule is not
         * needed when all libraries share the same full layout. */
        VkPipelineLayoutCreateInfo plci = { .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
                                            .setLayoutCount = 2, .pSetLayouts = sl,
                                            .pushConstantRangeCount = has_push ? 2 : 1,
                                            .pPushConstantRanges = pcr };
        VkPipelineLayout layout;
        CHECK(vkCreatePipelineLayout(dev, &plci, NULL, &layout));

        VkVertexInputBindingDescription vib[16];
        VkVertexInputAttributeDescription via[16];
        uint32_t nattr = 0;
        for (uint32_t l = 0; l < 16; l++) {
            if (!(loc_mask & (1u << l))) continue;
            vib[nattr] = (VkVertexInputBindingDescription){ nattr, 16, VK_VERTEX_INPUT_RATE_VERTEX };
            via[nattr] = (VkVertexInputAttributeDescription){ l, nattr, VK_FORMAT_R32G32B32A32_SFLOAT, 0 };
            nattr++;
        }
        VkShaderModule mods[3] = { 0 };
        Spv *srcs[3] = { &vs, &fsv, gs.w ? &gs : NULL };
        for (int i = 0; i < 3; i++) {
            if (!srcs[i]) continue;
            VkShaderModuleCreateInfo smci = { .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
                                              .codeSize = srcs[i]->n * 4, .pCode = srcs[i]->w };
            CHECK(vkCreateShaderModule(dev, &smci, NULL, &mods[i]));
        }
        VkPipelineShaderStageCreateInfo st_vs = { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            .stage = VK_SHADER_STAGE_VERTEX_BIT, .module = mods[0], .pName = "main" };
        VkPipelineShaderStageCreateInfo st_fs = { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            .stage = VK_SHADER_STAGE_FRAGMENT_BIT, .module = mods[1], .pName = "main" };
        VkPipelineShaderStageCreateInfo st_gs = { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            .stage = VK_SHADER_STAGE_GEOMETRY_BIT, .module = mods[2], .pName = "main" };
        VkPipelineShaderStageCreateInfo all[3] = { st_vs, st_fs, st_gs };
        VkPipelineShaderStageCreateInfo pre[2] = { st_vs, st_gs };
        int ngs = gs.w ? 1 : 0;

        VkPipelineVertexInputStateCreateInfo vi = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
            .vertexBindingDescriptionCount = nattr, .pVertexBindingDescriptions = vib,
            .vertexAttributeDescriptionCount = nattr, .pVertexAttributeDescriptions = via };
        VkPipelineInputAssemblyStateCreateInfo ia = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
            .topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST };
        VkPipelineViewportStateCreateInfo vps = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
            .viewportCount = 1, .scissorCount = 1 };
        VkPipelineRasterizationStateCreateInfo rs = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,
            .polygonMode = VK_POLYGON_MODE_FILL, .cullMode = VK_CULL_MODE_NONE,
            .frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE, .lineWidth = 1.0f };
        VkPipelineMultisampleStateCreateInfo ms = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
            .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT };
        VkPipelineDepthStencilStateCreateInfo ds = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO,
            .depthTestEnable = VK_TRUE, .depthWriteEnable = VK_TRUE,
            .depthCompareOp = VK_COMPARE_OP_LESS_OR_EQUAL };
        VkPipelineColorBlendAttachmentState cba = {
            .blendEnable = VK_TRUE,
            .srcColorBlendFactor = VK_BLEND_FACTOR_SRC_ALPHA,
            .dstColorBlendFactor = VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA,
            .colorBlendOp = VK_BLEND_OP_ADD,
            .srcAlphaBlendFactor = VK_BLEND_FACTOR_ONE,
            .dstAlphaBlendFactor = VK_BLEND_FACTOR_ZERO,
            .alphaBlendOp = VK_BLEND_OP_ADD, .colorWriteMask = 0xf };
        VkPipelineColorBlendStateCreateInfo cb = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
            .attachmentCount = 1, .pAttachments = &cba };
        VkDynamicState dyn[] = { VK_DYNAMIC_STATE_VIEWPORT, VK_DYNAMIC_STATE_SCISSOR,
                                 VK_DYNAMIC_STATE_LINE_WIDTH };
        VkPipelineDynamicStateCreateInfo dy = {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,
            .dynamicStateCount = 3, .pDynamicStates = dyn };

        double t[9];
        /* mono */
        VkGraphicsPipelineCreateInfo mono = {
            .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
            .stageCount = 2 + ngs, .pStages = all, .pVertexInputState = &vi,
            .pInputAssemblyState = &ia, .pViewportState = &vps,
            .pRasterizationState = &rs, .pMultisampleState = &ms,
            .pDepthStencilState = &ds, .pColorBlendState = &cb,
            .pDynamicState = &dy, .layout = layout, .renderPass = rp };
        VkPipeline pm = make(&mono, &t[0]);

        /* the four libraries, created twice: plain, then RETAIN */
        VkPipeline lib[2][4];
        for (int k = 0; k < 2; k++) {
            VkPipelineCreateFlags fl = VK_PIPELINE_CREATE_LIBRARY_BIT_KHR |
                (k ? VK_PIPELINE_CREATE_RETAIN_LINK_TIME_OPTIMIZATION_INFO_BIT_EXT : 0);
            VkGraphicsPipelineLibraryFlagsEXT parts[4] = {
                VK_GRAPHICS_PIPELINE_LIBRARY_VERTEX_INPUT_INTERFACE_BIT_EXT,
                VK_GRAPHICS_PIPELINE_LIBRARY_PRE_RASTERIZATION_SHADERS_BIT_EXT,
                VK_GRAPHICS_PIPELINE_LIBRARY_FRAGMENT_SHADER_BIT_EXT,
                VK_GRAPHICS_PIPELINE_LIBRARY_FRAGMENT_OUTPUT_INTERFACE_BIT_EXT };
            for (int p = 0; p < 4; p++) {
                if (k && (p == 0 || p == 3)) { lib[1][p] = lib[0][p]; continue; }
                VkGraphicsPipelineLibraryCreateInfoEXT gl = {
                    .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_LIBRARY_CREATE_INFO_EXT,
                    .flags = parts[p] };
                VkGraphicsPipelineCreateInfo ci = {
                    .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, .pNext = &gl,
                    .flags = fl, .layout = layout, .renderPass = rp };
                if (p == 0) {
                    ci.pVertexInputState = &vi;
                    ci.pInputAssemblyState = &ia;
                } else if (p == 1) {
                    ci.stageCount = 1 + ngs;
                    ci.pStages = pre;
                    ci.pViewportState = &vps;
                    ci.pRasterizationState = &rs;
                    ci.pDynamicState = &dy;
                } else if (p == 2) {
                    ci.stageCount = 1;
                    ci.pStages = &st_fs;
                    ci.pMultisampleState = &ms;
                    ci.pDepthStencilState = &ds;
                    ci.pDynamicState = &dy;
                } else {
                    ci.pMultisampleState = &ms;
                    ci.pColorBlendState = &cb;
                    ci.pDynamicState = &dy;
                }
                double ms_;
                lib[k][p] = make(&ci, &ms_);
                if (k == 0) t[1 + p] = ms_;
                else t[5 + (p == 1 ? 1 : 2)] = ms_;
            }
        }
        /* fast link, then LTO link */
        VkPipeline pl[2];
        for (int k = 0; k < 2; k++) {
            VkPipelineLibraryCreateInfoKHR li = {
                .sType = VK_STRUCTURE_TYPE_PIPELINE_LIBRARY_CREATE_INFO_KHR,
                .libraryCount = 4, .pLibraries = lib[k] };
            VkGraphicsPipelineCreateInfo ci = {
                .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, .pNext = &li,
                .flags = k ? VK_PIPELINE_CREATE_LINK_TIME_OPTIMIZATION_BIT_EXT : 0,
                .layout = layout, .renderPass = rp };
            double ms_;
            pl[k] = make(&ci, &ms_);
            if (k == 0) t[5] = ms_;
            else t[8] = ms_;
        }
        printf("%s\t%d\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\n", name, rep,
               t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8]);
        fflush(stdout);
        DestroyP(dev, pm, NULL);
        DestroyP(dev, pl[0], NULL);
        DestroyP(dev, pl[1], NULL);
        for (int p = 0; p < 4; p++) {
            DestroyP(dev, lib[0][p], NULL);
            if (p == 1 || p == 2) DestroyP(dev, lib[1][p], NULL);
        }
        for (int i = 0; i < 3; i++) {
            if (mods[i]) vkDestroyShaderModule(dev, mods[i], NULL);
        }
        vkDestroyPipelineLayout(dev, layout, NULL);
        free(vs.w); free(fsv.w); free(gs.w);
    }
    }
    return 0;
}
