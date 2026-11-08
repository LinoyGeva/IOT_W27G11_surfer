# Android hub

Implement the hub in `main/` and each device in its named sibling folder. See [Architecture](../Documentation/ARCHITECTURE.md) for responsibilities.

When initializing the Android project, configure Gradle [source sets](https://developer.android.com/build/build-variants#change-default-source-set-configurations) to use these folders instead of creating a deep `app/src/main/java/...` hierarchy. Build files, manifest and resources can be introduced here with the project. Source-set configuration has not been created or tested yet.

Add verified build, install and test commands after initialization on the Pi.
