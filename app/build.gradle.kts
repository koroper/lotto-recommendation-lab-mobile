plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

// Explicit opt-in for a device-update APK. Ordinary CI debug builds never require secrets.
val lottoDeviceUpdate = providers.gradleProperty("lottoDeviceUpdate").orNull == "true"
val lottoPreview = providers.gradleProperty("lottoPreview").orNull == "true"
require(!(lottoDeviceUpdate && lottoPreview)) {
    "lottoDeviceUpdate and lottoPreview are mutually exclusive."
}

android {
    namespace = "com.lotto.lab"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.lotto.lab"
        minSdk = 26
        targetSdk = 36
        versionCode = 3
        versionName = "1.2-history-fix"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    signingConfigs {
        getByName("debug") {
            if (lottoDeviceUpdate) {
                // Private key is deliberately NOT in Git. Never generate a replacement
                // signing key when preparing an update for an installed phone.
                val projectKeystore = rootProject.file("debug.keystore")
                require(projectKeystore.isFile) {
                    "Cannot build device-update APK: private debug.keystore is missing from the project root."
                }
                storeFile = projectKeystore
                storePassword = providers.environmentVariable("LOTTO_KEYSTORE_PASSWORD").orNull ?: "android"
                keyAlias = providers.environmentVariable("LOTTO_KEY_ALIAS").orNull ?: "androiddebugkey"
                keyPassword = providers.environmentVariable("LOTTO_KEY_PASSWORD").orNull ?: "android"
            }
        }
    }

    buildTypes {
        getByName("debug") {
            // AI Studio streaming emulator runs a standalone test app.
            // Never ship this variant as an update to com.lotto.lab.
            if (lottoPreview) applicationIdSuffix = ".preview"
        }
    }

    buildFeatures {
        compose = true
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

chaquopy {
    defaultConfig {
        version = "3.13"
    }
}

dependencies {
    // Pin the last stable pre-Compose-1.12 line so stable Android SDK 36 is sufficient.
    implementation("androidx.compose.ui:ui:1.9.5")
    implementation("androidx.compose.ui:ui-tooling-preview:1.9.5")
    implementation("androidx.compose.foundation:foundation:1.9.5")
    implementation("androidx.compose.material3:material3:1.4.0")

    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")

    debugImplementation("androidx.compose.ui:ui-tooling:1.9.5")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20231013")
}
