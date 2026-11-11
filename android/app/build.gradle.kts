plugins { id("com.android.application") }

android {
    namespace = "com.dexget.companion"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.dexget.companion"
        minSdk = 29
        targetSdk = 35
        versionCode = 9
        versionName = "1.2.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
}

dependencies {
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
}
