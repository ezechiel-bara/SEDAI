import com.android.build.gradle.LibraryExtension

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}

subprojects {
    project.evaluationDependsOn(":app")
}

// Force compileSdk = 34 on all Android library submodules (e.g. 'printing')
// so that android:attr/lStar (introduced in API 31) is available at build time.
subprojects {
    plugins.whenPluginAdded {
        if (this is com.android.build.gradle.LibraryPlugin) {
            extensions.configure<LibraryExtension> {
                compileSdk = 34
            }
        }
    }
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
