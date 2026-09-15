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

android {
  namespace = "com.rfandango.haku_x"
  compileSdk = 36
  buildToolsVersion = "36.1.0"
  ndkVersion = "29.0.14206865"

  defaultConfig {
    applicationId = "com.jreinach.hakux"
    minSdk = 26
    targetSdk = 36

    versionCode = 7
    versionName = "0.4.0-j1"

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
      resValue("string", "app_name", "hakuX (debug)")
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
