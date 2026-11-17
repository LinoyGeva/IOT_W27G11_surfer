import java.util.Properties
import org.jetbrains.kotlin.gradle.dsl.JvmTarget

// Single-module Android application. Sources stay in the flat device folders
// (main/, maverick/, ...) instead of app/src/main/java/... — see README.md.
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.jetbrains.kotlin.android)
}

val secrets = Properties().apply {
    val file = rootDir.resolve("SECRETS.local.properties")
    if (file.isFile) file.inputStream().use { load(it) }
}

android {
    namespace = "com.aerovision.hub"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.aerovision.hub"
        // Maverick SDK samples target minSdk 30 (Android 11).
        minSdk = 30
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }

    sourceSets {
        getByName("main") {
            manifest.srcFile("main/AndroidManifest.xml")
            java.srcDirs("main/kotlin", "maverick/kotlin")
            res.srcDirs("main/res")
        }
        getByName("test") {
            java.srcDirs("maverick/test")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

// --- Maverick API key -------------------------------------------------------
// The SDK reads `sdk.key` from the APK assets. The key file stays outside Git;
// SECRETS.local.properties points to it via `maverick.api_key_file`. Without it
// the app still builds, and reports "API key missing" at runtime.
abstract class BundleMaverickKey : DefaultTask() {
    @get:InputFile
    @get:Optional
    @get:PathSensitive(PathSensitivity.NONE)
    abstract val keyFile: RegularFileProperty

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    @TaskAction
    fun bundle() {
        val out = outputDir.get().asFile
        out.deleteRecursively()
        out.mkdirs()
        val source = keyFile.orNull?.asFile
        if (source != null) {
            source.copyTo(out.resolve("sdk.key"), overwrite = true)
        } else {
            logger.warn("Maverick API key not configured: set maverick.api_key_file in SECRETS.local.properties.")
        }
    }
}

val bundleMaverickKey = tasks.register<BundleMaverickKey>("bundleMaverickKey") {
    val path = secrets.getProperty("maverick.api_key_file")?.trim().orEmpty()
    val file = if (path.isEmpty()) null else rootDir.resolve(path)
    if (file != null && file.isFile) {
        keyFile.set(file)
    } else if (file != null) {
        logger.warn("Maverick API key file not found: $file")
    }
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(bundleMaverickKey, BundleMaverickKey::outputDir)
    }
}

dependencies {
    implementation(libs.evskit)
    implementation(libs.nativeevskit)

    testImplementation(libs.junit)
}
