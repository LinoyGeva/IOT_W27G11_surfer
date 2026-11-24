import java.util.Properties
import java.util.zip.ZipFile

val secrets = Properties().apply {
    val file = file("SECRETS.local.properties")
    if (file.isFile) file.inputStream().use { load(it) }
}
val githubUser = providers.environmentVariable("GITHUB_ACTOR")
    .orElse(provider { secrets.getProperty("github.user", "") })
val githubToken = providers.environmentVariable("GITHUB_TOKEN")
    .orElse(provider { secrets.getProperty("github.token", "") })

repositories {
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

val maverickSdk by configurations.creating {
    isCanBeConsumed = false
    isTransitive = false
    attributes { attribute(Usage.USAGE_ATTRIBUTE, objects.named(Usage.JAVA_RUNTIME)) }
}
dependencies {
    maverickSdk("com.everysight:evskit:2.6.1")
    maverickSdk("com.everysight:nativeevskit:2.6.1")
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
