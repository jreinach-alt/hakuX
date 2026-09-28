/*
 * vkharness: time Turnip's pipeline compile on the host.
 *
 *   vkharness <icd.so> <manifest> <reps> [samples.bin]
 *
 * Loads the ICD directly (no loader) and, through the freedreno noop drm-shim
 * (LD_PRELOAD, FD_GPU_ID=740), compiles one graphics pipeline per manifest
 * line, <reps> times each, with no pipeline cache. Manifest lines:
 *
 *   <name> <vert.spv> <frag.spv> [<geom.spv>]
 *
 * The pipeline layout is hakuX's (vk/draw.c:2727-2764, vk/shaders.c:100-180):
 * set 0 = four combined image samplers, set 1 = two UBOs, push constants
 * 16 B at 0 for the geometry stage and, if the vertex shader declares a push
 * block, a vertex range after it. The vertex inputs are read from the SPIR-V.
 *
 * Output, one TSV row per compile (cpu_ms is this thread's CPU time; the
 * fb_* columns are VkPipelineCreationFeedback's durations):
 *   name rep wall_ms cpu_ms fb_pipeline_ms fb_vs_ms fb_fs_ms fb_gs_ms
 *
 * With [samples.bin], a SIGPROF sampler (ITIMER_PROF, 200 us) records the
 * call chain of every sample taken inside vkCreateGraphicsPipelines, as
 * return addresses relative to the ICD's load base. prof.py symbolizes them.
 *
 * Run with VK_ENABLE_PIPELINE_CACHE=false MESA_SHADER_CACHE_DISABLE=true so
 * every rep is a cold compile (vk_pipeline_cache.c:661, the device's
 * mem_cache otherwise returns the first rep's result).
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <execinfo.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>
#include <link.h>

#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>

#define CHECK(x) do { VkResult _r = (x); if (_r != VK_SUCCESS) { \
    fprintf(stderr, "%s:%d %s -> %d\n", __FILE__, __LINE__, #x, _r); exit(1); } } while (0)

static PFN_vkGetInstanceProcAddr gipa;
static PFN_vkGetDeviceProcAddr gdpa;

/* ---- sampler ------------------------------------------------------------ */
#define MAX_DEPTH 96
#define MAX_SAMPLES 400000
static void **sbuf;          /* MAX_SAMPLES * (MAX_DEPTH + 1): [n, frames...] */
static volatile size_t nsamples;
static volatile int sampling;
static volatile int cur_pipeline;   /* manifest line index, tagged on each sample */

static void on_prof(int sig, siginfo_t *si, void *uc)
{
    (void)sig; (void)si; (void)uc;
    if (!sampling || nsamples >= MAX_SAMPLES) {
        return;
    }
    void **slot = &sbuf[nsamples * (MAX_DEPTH + 1)];
    int n = backtrace(slot + 1, MAX_DEPTH);
    slot[0] = (void *)(((intptr_t)cur_pipeline << 32) | n);
    nsamples++;
}

static void start_sampler(void)
{
    sbuf = calloc((size_t)MAX_SAMPLES * (MAX_DEPTH + 1), sizeof(void *));
    void *warm[4];
    backtrace(warm, 4);  /* load libgcc's unwinder outside the handler */
    struct sigaction sa = { .sa_sigaction = on_prof, .sa_flags = SA_SIGINFO | SA_RESTART };
    sigemptyset(&sa.sa_mask);
    sigaction(SIGPROF, &sa, NULL);
    struct itimerval it = { { 0, 200 }, { 0, 200 } };
    setitimer(ITIMER_PROF, &it, NULL);
}

/* ---- SPIR-V ------------------------------------------------------------- */
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

/* Input locations of a vertex shader, and whether it has a push block. */
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
        if (op == 71 /* OpDecorate */ && s.w[i + 2] == 30 /* Location */ &&
            s.w[i + 1] < MAXID) {
            loc[s.w[i + 1]] = s.w[i + 3];
        } else if (op == 59 /* OpVariable */) {
            uint32_t id = s.w[i + 2], sc = s.w[i + 3];
            if (sc == 1 /* Input */ && id < MAXID && loc[id] >= 0) {
                *loc_mask |= 1u << loc[id];
            }
            if (sc == 9 /* PushConstant */) {
                *has_push = 1;
            }
        }
        i += len;
    }
}

static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

/* This thread's CPU time: what the compile cost, minus time preempted. */
static double cpu_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_THREAD_CPUTIME_ID, &ts);
    return ts.tv_sec * 1e3 + ts.tv_nsec / 1e6;
}

static uintptr_t icd_base;
static int find_base(struct dl_phdr_info *info, size_t size, void *data)
{
    (void)size;
    if (info->dlpi_name && strstr(info->dlpi_name, (const char *)data)) {
        icd_base = info->dlpi_addr;
        return 1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 4) {
        fprintf(stderr, "usage: %s icd.so manifest reps [samples.bin]\n", argv[0]);
        return 2;
    }
    void *icd = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!icd) { fprintf(stderr, "%s\n", dlerror()); return 1; }
    VkResult (*nego)(uint32_t *) =
        (VkResult (*)(uint32_t *))dlsym(icd, "vk_icdNegotiateLoaderICDInterfaceVersion");
    if (nego) { uint32_t v = 5; nego(&v); }
    gipa = (PFN_vkGetInstanceProcAddr)dlsym(icd, "vk_icdGetInstanceProcAddr");
    const char *base = strrchr(argv[1], '/');
    dl_iterate_phdr(find_base, (void *)(base ? base + 1 : argv[1]));
    int reps = atoi(argv[3]);
    const char *sample_path = argc > 4 ? argv[4] : NULL;

#define IPA(inst, name) PFN_##name name = (PFN_##name)gipa(inst, #name)
    IPA(NULL, vkCreateInstance);
    VkApplicationInfo app = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
                              .apiVersion = VK_API_VERSION_1_3 };
    VkInstanceCreateInfo ici = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                                 .pApplicationInfo = &app };
    VkInstance inst;
    CHECK(vkCreateInstance(&ici, NULL, &inst));
    IPA(inst, vkEnumeratePhysicalDevices);
    IPA(inst, vkGetPhysicalDeviceProperties);
    IPA(inst, vkCreateDevice);
    IPA(inst, vkGetDeviceProcAddr);
    gdpa = vkGetDeviceProcAddr;
    uint32_t npd = 1;
    VkPhysicalDevice pd;
    CHECK(vkEnumeratePhysicalDevices(inst, &npd, &pd));
    VkPhysicalDeviceProperties props;
    vkGetPhysicalDeviceProperties(pd, &props);
    fprintf(stderr, "device: %s driver 0x%x\n", props.deviceName, props.driverVersion);

    float prio = 1.0f;
    VkDeviceQueueCreateInfo qci = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
                                    .queueFamilyIndex = 0, .queueCount = 1,
                                    .pQueuePriorities = &prio };
    VkPhysicalDeviceFeatures feats = { .geometryShader = VK_TRUE,
                                       .shaderTessellationAndGeometryPointSize = VK_TRUE,
                                       .fillModeNonSolid = VK_TRUE,
                                       .wideLines = VK_TRUE,
                                       .largePoints = VK_TRUE,
                                       .depthClamp = VK_TRUE };
    VkDeviceCreateInfo dci = { .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
                               .queueCreateInfoCount = 1, .pQueueCreateInfos = &qci,
                               .pEnabledFeatures = &feats };
    VkDevice dev;
    CHECK(vkCreateDevice(pd, &dci, NULL, &dev));

#define DPA(name) PFN_##name name = (PFN_##name)gdpa(dev, #name)
    DPA(vkCreateShaderModule);
    DPA(vkDestroyShaderModule);
    DPA(vkCreateDescriptorSetLayout);
    DPA(vkCreatePipelineLayout);
    DPA(vkDestroyPipelineLayout);
    DPA(vkCreateRenderPass);
    DPA(vkCreateGraphicsPipelines);
    DPA(vkDestroyPipeline);

    /* set 0: textures; set 1: UBOs */
    VkDescriptorSetLayoutBinding tb[4];
    for (int i = 0; i < 4; i++) {
        tb[i] = (VkDescriptorSetLayoutBinding){
            .binding = i, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,
            .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_ALL_GRAPHICS };
    }
    VkDescriptorSetLayoutBinding ub[2];
    for (int i = 0; i < 2; i++) {
        ub[i] = (VkDescriptorSetLayoutBinding){
            .binding = i, .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
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
    if (sample_path) {
        start_sampler();
    }
    printf("name\trep\twall_ms\tcpu_ms\tfb_pipeline_ms\tfb_vs_ms\tfb_fs_ms\tfb_gs_ms\n");
    char line[4096];
    /* Reps are the OUTER loop: rep r of every pipeline runs before rep r+1 of
     * any, so a variant pair placed on adjacent lines is measured under the
     * same machine load. */
    for (int rep = 0; rep < reps; rep++) {
    rewind(mf);
    int pipeline_idx = -1;
    while (fgets(line, sizeof(line), mf)) {
        char name[512], vp[1024], fp[1024], gp[1024];
        gp[0] = 0;
        if (line[0] == '#' ||
            sscanf(line, "%511s %1023s %1023s %1023s", name, vp, fp, gp) < 3) {
            continue;
        }
        cur_pipeline = ++pipeline_idx;
        Spv vs = load_spv(vp), fs = load_spv(fp), gs = { 0 };
        if (gp[0]) gs = load_spv(gp);
        uint32_t loc_mask; int has_push;
        reflect_vs(vs, &loc_mask, &has_push);

        VkPushConstantRange pcr[2] = {
            { VK_SHADER_STAGE_GEOMETRY_BIT, 0, 16 },
            { VK_SHADER_STAGE_VERTEX_BIT, 16, 16 * 16 },
        };
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

        {
            VkShaderModule mods[3] = { 0 };
            Spv *srcs[3] = { &vs, &fs, gs.w ? &gs : NULL };
            VkShaderStageFlagBits stg[3] = { VK_SHADER_STAGE_VERTEX_BIT,
                                             VK_SHADER_STAGE_FRAGMENT_BIT,
                                             VK_SHADER_STAGE_GEOMETRY_BIT };
            VkPipelineShaderStageCreateInfo ss[3];
            int nst = 0;
            for (int i = 0; i < 3; i++) {
                if (!srcs[i]) continue;
                VkShaderModuleCreateInfo smci = { .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
                                                  .codeSize = srcs[i]->n * 4, .pCode = srcs[i]->w };
                CHECK(vkCreateShaderModule(dev, &smci, NULL, &mods[i]));
                ss[nst++] = (VkPipelineShaderStageCreateInfo){
                    .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                    .stage = stg[i], .module = mods[i], .pName = "main" };
            }
            VkPipelineVertexInputStateCreateInfo vi = {
                .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO,
                .vertexBindingDescriptionCount = nattr, .pVertexBindingDescriptions = vib,
                .vertexAttributeDescriptionCount = nattr, .pVertexAttributeDescriptions = via };
            VkPipelineInputAssemblyStateCreateInfo ia = {
                .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
                /* the geometry stage's input primitive, named in the manifest */
                .topology = strstr(name, "+gadj") ? VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST_WITH_ADJACENCY
                          : strstr(name, "+glines") ? VK_PRIMITIVE_TOPOLOGY_LINE_LIST
                          : VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST };
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
            VkPipelineCreationFeedback fb_pipe = { 0 }, fb_st[3] = { 0 };
            VkPipelineCreationFeedbackCreateInfo fbci = {
                .sType = VK_STRUCTURE_TYPE_PIPELINE_CREATION_FEEDBACK_CREATE_INFO,
                .pPipelineCreationFeedback = &fb_pipe,
                .pipelineStageCreationFeedbackCount = nst,
                .pPipelineStageCreationFeedbacks = fb_st };
            VkGraphicsPipelineCreateInfo gpci = {
                .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO, .pNext = &fbci,
                .stageCount = nst, .pStages = ss, .pVertexInputState = &vi,
                .pInputAssemblyState = &ia, .pViewportState = &vps,
                .pRasterizationState = &rs, .pMultisampleState = &ms,
                .pDepthStencilState = &ds, .pColorBlendState = &cb,
                .pDynamicState = &dy, .layout = layout, .renderPass = rp };
            VkPipeline pipe;
            double t0 = now_ms(), c0 = cpu_ms();
            sampling = sample_path != NULL;
            VkResult r = vkCreateGraphicsPipelines(dev, VK_NULL_HANDLE, 1, &gpci, NULL, &pipe);
            sampling = 0;
            double t1 = now_ms(), c1 = cpu_ms();
            if (r != VK_SUCCESS) {
                fprintf(stderr, "%s: vkCreateGraphicsPipelines -> %d\n", name, r);
                exit(1);
            }
            double gsms = gs.w ? fb_st[2].duration / 1e6 : 0.0;
            printf("%s\t%d\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\t%.3f\n", name, rep, t1 - t0,
                   c1 - c0, fb_pipe.duration / 1e6, fb_st[0].duration / 1e6,
                   fb_st[1].duration / 1e6, gsms);
            fflush(stdout);
            vkDestroyPipeline(dev, pipe, NULL);
            for (int i = 0; i < 3; i++) {
                if (mods[i]) vkDestroyShaderModule(dev, mods[i], NULL);
            }
        }
        vkDestroyPipelineLayout(dev, layout, NULL);
        free(vs.w); free(fs.w); free(gs.w);
    }
    }

    if (sample_path) {
        struct itimerval off = { { 0, 0 }, { 0, 0 } };
        setitimer(ITIMER_PROF, &off, NULL);
        FILE *sf = fopen(sample_path, "wb");
        uint64_t hdr[2] = { icd_base, nsamples };
        fwrite(hdr, sizeof(hdr), 1, sf);
        for (size_t i = 0; i < nsamples; i++) {
            void **slot = &sbuf[i * (MAX_DEPTH + 1)];
            uint64_t tag = (uint64_t)(intptr_t)slot[0];
            uint64_t n = tag & 0xffffffff;
            fwrite(&tag, 8, 1, sf);
            for (uint64_t k = 0; k < n; k++) {
                uint64_t a = (uint64_t)(uintptr_t)slot[1 + k];
                fwrite(&a, 8, 1, sf);
            }
        }
        fclose(sf);
        fprintf(stderr, "samples: %zu -> %s (icd base 0x%lx)\n", (size_t)nsamples,
                sample_path, (unsigned long)icd_base);
    }
    return 0;
}
