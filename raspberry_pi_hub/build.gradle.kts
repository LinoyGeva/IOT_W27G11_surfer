plugins {
    id("com.android.application") version "9.0.1"
}

android {
    namespace = "org.aerovision.hub"
    compileSdk = 36
    defaultConfig {
        applicationId = "org.aerovision.hub"
        minSdk = 31
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }
    sourceSets {
        getByName("main") {
            manifest.srcFile("main/AndroidManifest.xml")
            kotlin.directories.clear()
            kotlin.directories.addAll(listOf("main", "garmin_hrm", "vakaros_atlas", "maverick"))
            res.directories.clear()
            res.directories.add("main/res")
        }
        getByName("test") {
            kotlin.directories.clear()
            kotlin.directories.add("tests")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}
kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}
dependencies {
    testImplementation("junit:junit:4.13.2")
}
