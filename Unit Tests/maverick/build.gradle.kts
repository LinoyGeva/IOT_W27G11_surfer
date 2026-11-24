import java.util.Properties
import java.util.zip.ZipFile

plugins {
    id("com.android.application") version "9.0.1"
}

val secrets = Properties().apply {
    val file = file("SECRETS.local.properties")
    if (file.isFile) file.inputStream().use { load(it) }
}
val githubUser = providers.environmentVariable("GITHUB_ACTOR")
    .orElse(provider { secrets.getProperty("github.user", "") })
val githubToken = providers.environmentVariable("GITHUB_TOKEN")
    .orElse(provider { secrets.getProperty("github.token", "") })

repositories {
    google()
    mavenCentral()
    exclusiveContent {
        forRepository {
            maven {
                url = uri("https://maven.pkg.github.com/everysight-maverick/m1-android-maven")
                credentials {
                    username = githubUser.get()
                    password = githubToken.get()
                }
            }
        }
        filter { includeGroup("com.everysight") }
    }
}

abstract class PrepareSdkKey : DefaultTask() {
    @get:InputFile abstract val key: RegularFileProperty
    @get:OutputDirectory abstract val outputDirectory: DirectoryProperty

    @TaskAction fun copyKey() {
        val source = key.get().asFile
        check(source.length() > 0) { "Empty root glasses_sdk.key" }
        val destination = outputDirectory.get().asFile.apply { mkdirs() }
        source.copyTo(destination.resolve("sdk.key"), overwrite = true)
    }
}
val prepareSdkKey = tasks.register<PrepareSdkKey>("prepareSdkKey") {
    key.set(rootDir.resolve("../../glasses_sdk.key"))
    outputDirectory.set(layout.buildDirectory.dir("generated/sdkAssets"))
}

android {
    namespace = "org.aerovision.maverick"
    compileSdk = 36
    defaultConfig {
        applicationId = "org.aerovision.maverick"
        minSdk = 30
        targetSdk = 36
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
androidComponents.onVariants { variant ->
    variant.sources.assets?.addGeneratedSourceDirectory(prepareSdkKey, PrepareSdkKey::outputDirectory)
}

val maverickSdk by configurations.creating {
    isCanBeConsumed = false
    isTransitive = false
    attributes { attribute(Usage.USAGE_ATTRIBUTE, objects.named(Usage.JAVA_RUNTIME)) }
}
dependencies {
    maverickSdk("com.everysight:evskit:2.6.1")
    maverickSdk("com.everysight:nativeevskit:2.6.1")
    implementation("com.everysight:evskit:2.6.1")
    implementation("com.everysight:nativeevskit:2.6.1")
    androidTestImplementation("androidx.test:runner:1.7.0")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
}

tasks.register("verifySdk") {
    doLast {
        check(githubUser.get().isNotBlank() && githubToken.get().isNotBlank()) {
            "Set GITHUB_ACTOR/GITHUB_TOKEN or fill SECRETS.local.properties (see README.md)."
        }
        val key = rootDir.resolve("../../glasses_sdk.key")
        check(key.isFile && key.length() > 0) { "Missing or empty root glasses_sdk.key" }
        maverickSdk.files.sortedBy { it.name }.forEach { artifact ->
            ZipFile(artifact).use { archive ->
                if (artifact.extension == "aar") {
                    check(archive.getEntry("AndroidManifest.xml") != null) { "Invalid AAR: ${artifact.name}" }
                    check(archive.getEntry("classes.jar") != null) { "Missing SDK classes: ${artifact.name}" }
                    val abis = archive.entries().asSequence()
                        .map { it.name }.filter { it.startsWith("jni/") && it.endsWith(".so") }
                        .map { it.split('/')[1] }.toSortedSet()
                    check(abis.isNotEmpty()) { "No native libraries: ${artifact.name}" }
                    logger.lifecycle("SDK ${artifact.name} abis=${abis.joinToString(",")}")
                } else {
                    check(archive.entries().asSequence().any { it.name.endsWith(".class") }) {
                        "Missing JVM SDK classes: ${artifact.name}"
                    }
                    logger.lifecycle("SDK ${artifact.name} OK")
                }
            }
        }
        logger.lifecycle("SETUP OK: SDK archives available; build and Pi runtime still untested")
    }
}
