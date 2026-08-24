// 應用層級 build.gradle.kts — SGH Voice 語音輸入法
import java.security.KeyStore
import java.security.MessageDigest
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

val localSigningProperties = Properties().apply {
    val propertiesFile = rootProject.file("keystore.properties")
    if (propertiesFile.isFile) {
        propertiesFile.inputStream().use { load(it) }
    }
}

fun releaseSetting(propertyName: String, environmentName: String): String? =
    providers.environmentVariable(environmentName).orNull
        ?.trim()
        ?.takeIf(String::isNotEmpty)
        ?: providers.gradleProperty(propertyName).orNull
            ?.trim()
            ?.takeIf(String::isNotEmpty)
        ?: localSigningProperties.getProperty(propertyName)
            ?.trim()
            ?.takeIf(String::isNotEmpty)

val releaseStoreFilePath = releaseSetting(
    "sghVoice.releaseStoreFile",
    "SGH_RELEASE_STORE_FILE"
)
val releaseStorePassword = releaseSetting(
    "sghVoice.releaseStorePassword",
    "SGH_RELEASE_STORE_PASSWORD"
)
val releaseKeyAlias = releaseSetting(
    "sghVoice.releaseKeyAlias",
    "SGH_RELEASE_KEY_ALIAS"
)
val releaseKeyPassword = releaseSetting(
    "sghVoice.releaseKeyPassword",
    "SGH_RELEASE_KEY_PASSWORD"
)
val releaseCertificateSha256 = releaseSetting(
    "sghVoice.releaseCertificateSha256",
    "SGH_RELEASE_CERT_SHA256"
)
val releaseSigningConfigured = listOf(
    releaseStoreFilePath,
    releaseStorePassword,
    releaseKeyAlias,
    releaseKeyPassword,
    releaseCertificateSha256
).all { !it.isNullOrBlank() }

android {
    namespace = "com.shingihou.sghvoice"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.shingihou.sghvoice"
        minSdk = 26
        targetSdk = 36
        versionCode = 23
        versionName = "2.7.3"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    signingConfigs {
        if (releaseSigningConfigured) {
            create("release") {
                storeFile = rootProject.file(requireNotNull(releaseStoreFilePath))
                storePassword = requireNotNull(releaseStorePassword)
                keyAlias = requireNotNull(releaseKeyAlias)
                keyPassword = requireNotNull(releaseKeyPassword)
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            if (releaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("release")
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

val verifyReleaseSigningConfig by tasks.registering {
    group = "verification"
    description = "Fails closed unless release signing and certificate verification inputs exist."

    doLast {
        val missingInputs = buildList {
            if (releaseStoreFilePath.isNullOrBlank()) add("SGH_RELEASE_STORE_FILE")
            if (releaseStorePassword.isNullOrBlank()) add("SGH_RELEASE_STORE_PASSWORD")
            if (releaseKeyAlias.isNullOrBlank()) add("SGH_RELEASE_KEY_ALIAS")
            if (releaseKeyPassword.isNullOrBlank()) add("SGH_RELEASE_KEY_PASSWORD")
            if (releaseCertificateSha256.isNullOrBlank()) add("SGH_RELEASE_CERT_SHA256")
        }
        if (missingInputs.isNotEmpty()) {
            throw GradleException(
                "Release signing configuration is incomplete. Missing environment variables " +
                    "or matching untracked keystore.properties entries: " +
                    missingInputs.joinToString(", ")
            )
        }

        val configuredStoreFile = rootProject.file(requireNotNull(releaseStoreFilePath))
        if (!configuredStoreFile.isFile) {
            throw GradleException("Configured release keystore does not exist or is not a file.")
        }

        val normalizedFingerprint = requireNotNull(releaseCertificateSha256)
            .filter(Char::isLetterOrDigit)
            .uppercase()
        if (!normalizedFingerprint.matches(Regex("[0-9A-F]{64}"))) {
            throw GradleException("Release certificate SHA-256 must contain exactly 64 hexadecimal characters.")
        }

        val actualFingerprint = try {
            val keyStore = KeyStore.getInstance(
                configuredStoreFile,
                requireNotNull(releaseStorePassword).toCharArray()
            )
            val configuredAlias = requireNotNull(releaseKeyAlias)
            if (!keyStore.isKeyEntry(configuredAlias)) {
                throw GradleException("Configured release alias is not a private-key entry.")
            }
            val certificate = keyStore.getCertificate(configuredAlias)
                ?: throw GradleException("Configured release alias has no certificate.")
            MessageDigest.getInstance("SHA-256")
                .digest(certificate.encoded)
                .joinToString("") { byte -> "%02X".format(byte) }
        } catch (error: GradleException) {
            throw error
        } catch (_: Exception) {
            throw GradleException(
                "Unable to verify the configured release keystore and alias."
            )
        }
        if (actualFingerprint != normalizedFingerprint) {
            throw GradleException(
                "Configured release signer does not match the expected certificate fingerprint."
            )
        }
    }
}

tasks.matching { it.name == "preReleaseBuild" }.configureEach {
    dependsOn(verifyReleaseSigningConfig)
}

dependencies {
    // Android 核心
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")

    // Jetpack Compose
    val composeBom = platform("androidx.compose:compose-bom:2024.01.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation("androidx.navigation:navigation-compose:2.7.6")
    debugImplementation("androidx.compose.ui:ui-tooling")

    // 網路請求 — OkHttp
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // JSON 解析
    implementation("org.json:json:20231013")

    // 繁體中文轉換 — OpenCC
    implementation("com.github.houbb:opencc4j:1.8.0")

    // 加密儲存 — API 金鑰安全保存
    implementation("androidx.security:security-crypto:1.1.0-alpha06")

    // 協程
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")

    // 測試依賴
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.mockito:mockito-core:5.8.0")
    testImplementation("org.mockito.kotlin:mockito-kotlin:5.2.1")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
}
