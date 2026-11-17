# Rules required by the Maverick SDK when minification is enabled
# (from https://everysight.github.io/maverick_docs/libraries-api/android/).
-keepattributes InnerClasses

-keep class io.jsonwebtoken.** { *; }
-keepnames class io.jsonwebtoken.* { *; }
-keepnames interface io.jsonwebtoken.* { *; }

-keep class com.google.gson.reflect.TypeToken
-keep class * extends com.google.gson.reflect.TypeToken
-keep public class * implements java.lang.reflect.Type
