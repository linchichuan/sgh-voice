# SGH Voice ProGuard 規則

# 保留 OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }

# 保留 OpenCC4J
-keep class com.github.houbb.opencc4j.** { *; }

# 保留 EncryptedSharedPreferences
-keep class androidx.security.crypto.** { *; }

# 保留 Kotlin 協程
-keepnames class kotlinx.coroutines.** { *; }

# 保留應用類別
-keep class com.shingihou.sghvoice.** { *; }
