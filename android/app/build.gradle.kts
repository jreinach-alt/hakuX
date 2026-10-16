import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
  id("com.android.application")
  id("org.jetbrains.kotlin.android")
}

val keystorePropertiesFile = rootProject.file("key.properties")
val keystoreProperties = Properties()
val hasKeystoreProperties = keystorePropertiesFile.exists()

if (hasKeystoreProperties) {
  keystorePropertiesFile.inputStream().use { keystoreProperties.load(it) }
}

val hasReleaseKeystore = hasKeystoreProperties &&
  listOf("storeFile", "storePassword", "keyAlias", "keyPassword").all {
    !keystoreProperties.getProperty(it).isNullOrBlank()
  }

// <base>-<MMDD>-<shortsha>[-perflog][-dirty] of the commit actually being
// built, computed by docs/testing/version_stamp.sh so the dispatcher's build
// (in its own detached worktree), owner_build.sh and this Gradle build all
// agree on one definition. Run against rootProject's parent, the repo root:
// in a dispatcher or owner_build.sh build that is the private worktree
// checked out at the requested ref, never the host's own checkout, so the
// stamp names the commit being built rather than whatever the host last had
// open (#433).
fun stampedVersionName(): String {
  val repoRoot = rootProject.projectDir.parentFile
  val script = repoRoot.resolve("docs/testing/version_stamp.sh")
  val variant = if (project.hasProperty("perflog")) "perflog" else ""
  return try {
    val proc = ProcessBuilder(listOf("bash", script.absolutePath, repoRoot.absolutePath, variant))
      .redirectErrorStream(true)
      .start()
    val out = proc.inputStream.bufferedReader().readText().trim()
    if (proc.waitFor() == 0 && out.isNotEmpty()) out else "0.5.0-unknown"
  } catch (e: Exception) {
    "0.5.0-unknown"
  }
}

// -PversionedRelease=<X.Y.Z[-suffix]> marks THIS build as the one versioned
// release artifact, as opposed to a nightly, an owner build or a dispatcher/
// working debug build -- every one of which runs plain assembleRelease or
// assembleDebug with this property unset (#433). Unset is the default this
// whole repo builds under, so unset must mean "Debug Capture is on", not the
// other way around: a build type can't make this distinction (nightlies and
// owner builds are both assembleRelease -- docs/testing/nightly_build.sh,
// docs/testing/owner_build.sh), so it has to be this explicit flag, passed
// only by docs/testing/release_build.sh.
//
// When set: versionName becomes exactly this string (the stamped
// <base>-<MMDD>-<sha> is for builds nobody tagged) and Debug Capture
// defaults OFF. When unset: versionName is unchanged and Debug Capture
// defaults ON (before 0.5.0 it defaulted off in every build, and showed only
// where Settings > Debug Tools had been switched on). Settings > Debug Tools still overrides
// either default, so a contributor running a release build can switch it
// back on.
val versionedRelease: String? = (project.findProperty("versionedRelease") as String?)?.trim()?.ifEmpty { null }
if (versionedRelease != null) {
  val versionPattern = Regex("^[0-9]+\\.[0-9]+\\.[0-9]+(-[A-Za-z0-9.]+)?\$")
  if (!versionPattern.matches(versionedRelease)) {
    error(
      "versionedRelease='$versionedRelease' is not a version (want X.Y.Z or " +
        "X.Y.Z-suffix); docs/testing/release_build.sh is the normal caller"
    )
  }
}
val debugToolsDefault = versionedRelease == null

android {
  namespace = "com.rfandango.haku_x"
  compileSdk = 36
  buildToolsVersion = "36.1.0"
  ndkVersion = "29.0.14206865"

  defaultConfig {
    applicationId = "com.jreinach.hakux"
    // 33 (raised from 29 for the signing-key rotation, #433) is well above the
    // native-ELF-TLS floor: 29 is the first API with native ELF TLS, below
    // which every __thread access (tcg_ctx, current_cpu) is a call to
    // __emutls_get_address, and minSdk also sets ANDROID_PLATFORM, which the
    // glib cross build reads (#427). The owner confirmed no pre-13 handheld
    // has the hardware to run this emulator, so the floor can move freely.
    minSdk = 33
    targetSdk = 36

    versionCode = 9
    versionName = versionedRelease ?: stampedVersionName()

    // The checkable marker on the artifact itself: release_build.sh verifies
    // this resource with aapt2 after the build rather than trusting that the
    // property it passed in actually took effect. PauseMenuOverlay's "Debug
    // Capture" button reads debug_tools via MainActivity/SettingsActivity's
    // `resources.getBoolean(R.bool.debug_tools_default)` default -- a stored
    // preference always wins, so Settings > Debug Tools still turns this on
    // in a versioned release.
    resValue("bool", "debug_tools_default", debugToolsDefault.toString())

    ndk {
      abiFilters += listOf("arm64-v8a")
    }

    externalNativeBuild {
      cmake {
        arguments += listOf(
          "-DXEMU_ANDROID_BUILD_ID=3",
          "-DXEMU_ENABLE_XISO_CONVERTER=ON",
          "-DCMAKE_C_FLAGS_DEBUG=-O2 -g1",
          "-DCMAKE_CXX_FLAGS_DEBUG=-O2 -g1"
        )
        // Diagnostic build: ./gradlew assembleDebug -Pperflog=true
        // Compiles in the nv2a frame-phase profiler, which is off by default
        // because its instrumentation perturbs the timings it reports.
        if (project.hasProperty("perflog")) {
          arguments += listOf("-DHAKUX_PERF_LOG=ON")
        }
        cppFlags += listOf("-std=c++17", "-fexceptions", "-frtti")
      }
    }
  }

  signingConfigs {
    if (hasReleaseKeystore) {
      create("release") {
        storeFile = file(keystoreProperties.getProperty("storeFile"))
        storePassword = keystoreProperties.getProperty("storePassword")
        keyAlias = keystoreProperties.getProperty("keyAlias")
        keyPassword = keystoreProperties.getProperty("keyPassword")
      }
    }
  }

  buildTypes {
    debug {
      // Distinct id and label so a debug build installs alongside the release
      // instead of contending for the same package.  Two installs sharing a
      // name and icon are indistinguishable in the launcher, and settings
      // changed in one silently do not apply to the other.
      applicationIdSuffix = ".debug"
      resValue("string", "app_name", "hakuX (test builds)")
      ndk {
        debugSymbolLevel = "NONE"
      }
      externalNativeBuild {
        cmake {
          arguments += listOf(
            "-DCMAKE_BUILD_TYPE=Release"
          )
        }
      }
    }
    // A second debug install, for the Thor's second screen. Two emulators on
    // one device need two packages: MainActivity always runs in the
    // package's one ":xemu" process, and xemu is one instance per process.
    // A separate id also gives it its own prefs, HDD image and SAF grant.
    create("debug2") {
      initWith(getByName("debug"))
      applicationIdSuffix = ".debug2"
      resValue("string", "app_name", "hakuX (debug 2)")
      matchingFallbacks += listOf("debug")
    }
    release {
      resValue("string", "app_name", "hakuX (fork)")
      externalNativeBuild {
        cmake {
          arguments += listOf(
            "-DCMAKE_BUILD_TYPE=Release"
          )
        }
      }
      isMinifyEnabled = false
      proguardFiles(
        getDefaultProguardFile("proguard-android-optimize.txt"),
        "proguard-rules.pro"
      )
      if (hasReleaseKeystore) {
        signingConfig = signingConfigs.getByName("release")
      }
    }
  }

  externalNativeBuild {
    cmake {
      path = file("src/main/cpp/CMakeLists.txt")
      version = "3.30.3"
    }
  }

  packaging {
    resources.excludes += setOf(
      "**/*.md",
      "META-INF/LICENSE*",
      "META-INF/NOTICE*"
    )
    jniLibs.useLegacyPackaging = true
    jniLibs.keepDebugSymbols += setOf("**/*.so")
  }

  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
  }

}

dependencies {
  testImplementation("junit:junit:4.13.2")

  implementation("androidx.core:core-ktx:1.15.0")
  implementation("androidx.appcompat:appcompat:1.7.0")
  implementation("androidx.constraintlayout:constraintlayout:2.1.4")
  implementation("androidx.documentfile:documentfile:1.0.1")
  implementation("io.coil-kt:coil:2.7.0")
  implementation("com.google.android.material:material:1.14.0-alpha07")
  implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
}

kotlin {
  compilerOptions {
    jvmTarget.set(JvmTarget.JVM_21)
  }
}
