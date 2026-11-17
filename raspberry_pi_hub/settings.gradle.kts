import java.util.Properties

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

// Local credentials live in SECRETS.local.properties (ignored by Git).
// See SECRETS.example.properties for the expected keys.
val secrets = Properties().apply {
    val file = settingsDir.resolve("SECRETS.local.properties")
    if (file.isFile) file.inputStream().use { load(it) }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // Everysight Maverick SDK (com.everysight:evskit, nativeevskit).
        // GitHub Packages requires a personal token with the read:packages scope.
        maven {
            url = uri("https://maven.pkg.github.com/everysight-maverick/m1-android-maven")
            credentials {
                username = secrets.getProperty("github.user")?.takeIf { it.isNotBlank() }
                    ?: System.getenv("GITHUB_ACTOR")
                password = secrets.getProperty("github.packages_token")?.takeIf { it.isNotBlank() }
                    ?: System.getenv("GITHUB_TOKEN")
            }
            content { includeGroup("com.everysight") }
        }
    }
}

rootProject.name = "aerovision-hub"
