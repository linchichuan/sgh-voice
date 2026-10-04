// This manifest is a release record, not proof supplied by the browser.
// tests/test_windows_download.py also checks the actual installer bytes and
// the acceptance record before the site may advertise an available release.
function validatedWindowsRelease(manifest) {
    if (!manifest || manifest.schemaVersion !== 1 || manifest.status !== "available") return null;
    if (manifest.architecture !== "x64" || manifest.installerScope !== "per-user"
        || manifest.signing !== "unsigned") return null;
    if (typeof manifest.version !== "string"
        || !/^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$/.test(manifest.version)) return null;
    if (typeof manifest.fileName !== "string"
        || !/^SGHVoice-Windows-[A-Za-z0-9._-]+\.exe$/.test(manifest.fileName)) return null;
    if (!Number.isSafeInteger(manifest.sizeBytes) || manifest.sizeBytes <= 0) return null;
    if (typeof manifest.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(manifest.sha256)) return null;
    const build = manifest.build;
    const acceptance = manifest.acceptance;
    if (build?.status !== "passed" || build.platform !== "windows"
        || typeof build.commit !== "string" || !/^[a-f0-9]{40}$/.test(build.commit)) return null;
    if (acceptance?.status !== "passed" || acceptance.platform !== "windows"
        || acceptance.sha256 !== manifest.sha256
        || typeof acceptance.record !== "string"
        || !/^docs\/windows-acceptance-[A-Za-z0-9._-]+\.md$/.test(acceptance.record)) return null;
    return Object.freeze({
        version: manifest.version,
        fileName: manifest.fileName,
        sizeBytes: manifest.sizeBytes,
        sha256: manifest.sha256,
        // Only our own downloads directory can be used. Never trust a URL in JSON.
        href: "/downloads/" + manifest.fileName,
    });
}

const windowsDownloadButton = document.getElementById("windowsDownloadButton");
let windowsRelease = null;

function renderWindowsRelease() {
    if (!windowsDownloadButton) return;
    const available = Boolean(windowsRelease);
    const copy = window.SGH_I18N || {};
    const translateWindows = (key, fallback) => copy["download.windows." + key] || fallback;
    windowsDownloadButton.disabled = !available;
    windowsDownloadButton.classList.toggle("disabled", !available);
    windowsDownloadButton.setAttribute("aria-disabled", String(!available));
    windowsDownloadButton.querySelector("span").textContent = available
        ? translateWindows("ctaReady", "下載 Windows 安裝程式（.exe）")
        : translateWindows("ctaPending", "Windows 正式版尚未開放");
    document.getElementById("windowsReleaseBadge").textContent = available
        ? translateWindows("badgeReady", "WINDOWS · 已驗收")
        : translateWindows("badgePending", "WINDOWS · 開發中");
    document.getElementById("windowsReleaseStatus").textContent = available
        ? translateWindows("ready", "此版本已完成 Windows 安裝、錄音與貼字驗收。安裝程式未簽章；若 Windows 封鎖，請停止安裝並聯絡我們。")
        : translateWindows("pending", "Windows 測試版已可下載；正式版仍待實體錄音、一般使用者安裝與目標貼字驗收。");
    const metadata = document.getElementById("windowsReleaseMetadata");
    metadata.hidden = !available;
    if (available) {
        document.getElementById("windowsReleaseVersion").textContent = windowsRelease.version;
        document.getElementById("windowsReleaseSize").textContent = (windowsRelease.sizeBytes / 1048576).toFixed(1) + " MiB";
        document.getElementById("windowsReleaseHash").textContent = windowsRelease.sha256;
    }
}

async function loadWindowsRelease() {
    try {
        const response = await fetch("/downloads/windows-release.json", { cache: "no-store" });
        windowsRelease = response.ok ? validatedWindowsRelease(await response.json()) : null;
    } catch {
        windowsRelease = null;
    }
    renderWindowsRelease();
}

if (windowsDownloadButton) {
    windowsDownloadButton.addEventListener("click", () => {
        if (!windowsRelease || windowsDownloadButton.disabled) return;
        window.location.assign(windowsRelease.href);
    });
    window.addEventListener("sgh:languagechange", renderWindowsRelease);
    renderWindowsRelease();
    loadWindowsRelease();
}
