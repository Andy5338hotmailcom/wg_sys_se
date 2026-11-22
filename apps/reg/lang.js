// 注册表编辑器语言资源文件。
// 页面里只留 key，文案集中在这里；运行时按 localStorage 的 wg_lang 取。
// en-us 的文案取自英文仓库 en-us/apps/reg 页面原有英文，不是我另写的。
// en-xa 暂时直接沿用英文，后面手写成伪本地化再改这一块。
window.WG_LANG = window.WG_LANG || {};

window.WG_LANG["zh-cn"] = {
    regTitle: "🧪 软件注册表编辑器",
    regSubtitle: "保存后桌面壁纸立即生效。",

    themeTitle: "🎨 系统主题颜色 (WG_color)",
    themeOptBlack: "黑色主题 (b)",
    themeOptWhite: "白色主题 (w)",
    themeTip: "值为 b（黑色主题）或 w（白色主题），保存后桌面和开始菜单立即切换。",

    wallpaperTitle: "🖼️ 桌面壁纸 (WG_desktop_wallpaper)",
    wallpaperIntervalLabel: "切换间隔 (WG_desktop_wallpaper_time，秒)",
    wallpaperTip: "单张壁纸沿用原格式；多张壁纸用逗号分隔，例如：./wallpaper/a.jpg, ./wallpaper/b.jpg。多张时按间隔轮播，只有一张时不切换。默认间隔为 60 秒，保存后立即生效。",

    appListTitle: "📱 自定义应用列表 (app_list)",
    appListTip: '格式：[{"id":"test","name":"测试","icon":"ico.svg","path":"test.html"}]',

    pinnedTitle: "📌 开始菜单固定应用 (fixedApps)",
    pinnedTip: '格式：["appstore","settings"]',

    taskbarTitle: "📎 任务栏固定应用 (fixedTaskbarApps)",
    taskbarTip: '格式：["wgver","settings"] 仅存储应用id',

    desktopTitle: "🖥️ 桌面图标应用 (desktopIcons)",
    desktopTip: '格式：["appstore","settings"]',

    langTitle: "🌐 系统语言 (wg_lang)",
    langTip: "值为 zh-cn（简体中文）、en-us（英文）或 en-xa（en-XA 伪本地化，暂时显示中文），保存后重启桌面生效。",
    langOptZh: "简体中文 (zh-cn)",
    langOptEn: "English (en-us)",
    langOptXa: "en-XA（伪本地化测试）",

    btnSave: "💾 保存",
    btnLoad: "📂 读取",
    btnReset: "↩️ 恢复默认",
    btnClear: "🗑️ 清空",

    themeInvalidTitle: "主题设置无效",
    themeInvalidCodeMsg: "WG_color值无效，请选择 b 或 w 后保存。",
    themeInvalidValueMsg: "主题颜色值只能是 b 或 w。",

    wallpaperInvalidTitle: "壁纸设置无效",
    wpEmptyMsg: "壁纸路径不能为空。",
    wpIntervalMsg: "壁纸切换间隔必须是大于或等于 1 的整数秒。",
    wpNoneMsg: "请至少填写一个壁纸路径。",

    jsonErrorTitle: "JSON 错误",
    saveOkTitle: "保存成功",
    wpSavedMsg: "壁纸设置已保存。",
    appListSavedMsg: "应用列表已保存。",
    pinnedSavedMsg: "开始菜单固定应用已保存。",
    taskbarSavedMsg: "任务栏固定应用已保存。",
    desktopSavedMsg: "桌面图标应用已保存。",
    langSavedMsg: "语言设置已保存，重启桌面后生效。",

    clearAppListTitle: "清空应用列表",
    clearAppListMsg: "确定清空？",
    clearPinnedTitle: "清空固定应用",
    clearPinnedMsg: "确定清空？",
    clearTaskbarTitle: "清空任务栏固定应用",
    clearTaskbarMsg: "确定清空？",
    clearDesktopTitle: "清空桌面图标",
    clearDesktopMsg: "确定清空？",

    langInvalidTitle: "语言设置无效",
    langInvalidMsg: "wg_lang 只能是 zh-cn、en-us 或 en-xa。",
    taskbarTimeTitle: "🕒 任务栏时钟 (wg_taskbar_time)",
    taskbarTimeOptSeconds: "显示秒",
    taskbarTimeOptNoSeconds: "不显示秒",
    taskbarTimeTip: "1 显示秒，0 不显示秒；其他值按显示秒处理。保存后立即生效。",
    taskbarTimeSavedMsg: "任务栏时钟设置已保存。"
};

window.WG_LANG["en-us"] = {
    regTitle: "🧪 Software Registry Editor",
    regSubtitle: "Desktop wallpaper changes take effect immediately after saving.",

    themeTitle: "🎨 System theme (WG_color)",
    themeOptBlack: "Dark theme (b)",
    themeOptWhite: "Light theme (w)",
    themeTip: "Use b for the dark theme or w for the light theme. The desktop and Start menu update immediately after saving.",

    wallpaperTitle: "🖼️ Desktop wallpaper (WG_desktop_wallpaper)",
    wallpaperIntervalLabel: "Slideshow interval (WG_desktop_wallpaper_time, seconds)",
    wallpaperTip: "Enter a single wallpaper path or separate multiple paths with commas, for example: ./wallpaper/a.jpg, ./wallpaper/b.jpg. Multiple wallpapers rotate at the selected interval; a single wallpaper does not rotate. The default interval is 60 seconds. Changes take effect immediately after saving.",

    appListTitle: "📱 Custom app list (app_list)",
    appListTip: 'Format: [{"id":"test","name":"Example","icon":"ico.svg","path":"test.html"}]',

    pinnedTitle: "📌 Start menu pinned apps (fixedApps)",
    pinnedTip: 'Format: ["doc","setting"]',

    taskbarTitle: "📎 Taskbar pinned apps (fixedTaskbarApps)",
    taskbarTip: 'Format: ["wgver","setting"]. Only app IDs are stored.',

    desktopTitle: "🖥️ Desktop icons (desktopIcons)",
    desktopTip: 'Format: ["doc","setting"]',

    langTitle: "🌐 System language (wg_lang)",
    langTip: "Value is zh-cn (Simplified Chinese), en-us (English) or en-xa (en-XA pseudo-locale).",
    langOptZh: "Simplified Chinese (zh-cn)",
    langOptEn: "English (en-us)",
    langOptXa: "en-XA (pseudo-locale)",

    btnSave: "💾 Save",
    btnLoad: "📂 Load",
    btnReset: "↩️ Restore defaults",
    btnClear: "🗑️ Clear",

    themeInvalidTitle: "Invalid theme",
    themeInvalidCodeMsg: "Invalid WG_color value. Select b or w and save.",
    themeInvalidValueMsg: "The theme value must be b or w.",

    wallpaperInvalidTitle: "Invalid wallpaper",
    wpEmptyMsg: "The wallpaper path cannot be empty.",
    wpIntervalMsg: "The wallpaper interval must be a whole number of at least 1 second.",
    wpNoneMsg: "Enter at least one wallpaper path.",

    jsonErrorTitle: "JSON error",
    saveOkTitle: "Saved",
    wpSavedMsg: "✅ Saved successfully!",
    appListSavedMsg: "✅ Saved successfully!",
    pinnedSavedMsg: "✅ Saved successfully!",
    taskbarSavedMsg: "✅ Saved successfully!",
    desktopSavedMsg: "✅ Saved successfully!",
    langSavedMsg: "✅ Saved successfully!",

    clearAppListTitle: "Clear",
    clearAppListMsg: "Are you sure you want to clear this?",
    clearPinnedTitle: "Clear",
    clearPinnedMsg: "Are you sure you want to clear this?",
    clearTaskbarTitle: "Clear",
    clearTaskbarMsg: "Are you sure you want to clear this?",
    clearDesktopTitle: "Clear",
    clearDesktopMsg: "Are you sure you want to clear this?",

    langInvalidTitle: "Invalid language",
    langInvalidMsg: "wg_lang must be zh-cn, en-us or en-xa.",
    taskbarTimeTitle: "🕒 Taskbar clock (wg_taskbar_time)",
    taskbarTimeOptSeconds: "Show seconds",
    taskbarTimeOptNoSeconds: "Hide seconds",
    taskbarTimeTip: "1 shows seconds, 0 hides them; any other value is treated as 1. Takes effect immediately after saving.",
    taskbarTimeSavedMsg: "Taskbar clock setting saved."
};

window.WG_LANG["en-xa"] = {
    regTitle: "[regTitle][🧪 Șōƒτώἆяэ Яéģïšţґŷ Эðīŧöѓ]",
    regSubtitle: "[regSubtitle][Ðèśκŧóp ẁãĺłƥ𐓙pêя ḉнǻñǵėș ţẳƙέ ėƒfêĉŧ íṁmědǐᾂťēļỳ ᾱƒţέя șầνίлꞡ.]",

    themeTitle: "[themeTitle][🎨 Şyšţê₥ тнэṁę (ẄǴ_ćøłōґ)]",
    themeOptBlack: "[themeOptBlack][Ðắѓκ тħè₥ε (ᶀ)]",
    themeOptWhite: "[themeOptWhite][Ŀĭğħт țĥэмe (ẃ)]",
    themeTip: "[themeTip][Ūƨē ᵬ ƒōѓ ţĥэ ðǡѓƙ тĥ℮мĕ øг ŵ ƒõґ тђэ ŀįꞡнţ ţнέṁέ. Ťħĕ ďēşκтŏρ ᾶή₫ Șτᶏґť мęňǚ ǘpđấţe îmṁэ₫ΐḁțэļỳ ᾷƒţëř ŝấνìηᶃ.]",

    wallpaperTitle: "[wallpaperTitle][🖼️ Ðēşƙτôp щẚŀľpἂƥêř (ẀĜ_₫êƨƙтôφ_шɑļℓpᾃφęř)]",
    wallpaperIntervalLabel: "[wallpaperIntervalLabel][Şļĭďêšħöш ïňтėŗνǎĺ (ẄꞠ_ðéŝκŧõp_ẁἂļľƥȃφęя_ťįmέ, şēꞓòŉďƨ)]",
    wallpaperTip: "[wallpaperTip][Ěňтéř ᾲ šίήĝłę ẃᾴłľƥẩpεг ƥ𐓚τĥ øŗ ƨêφᾂѓäțэ ₥ΰļτǐρŀέ pⱥτђș ẁıтħ ĉőм₥ắƨ, fòѓ ėxā₥φŀè: ./шᾶľľpᾃφěŗ/ä.jφǧ, ./ẃᾂļℓφᾷpěѓ/ḃ.jpᶃ. Mǔłŧΐρĺĕ ŵᾶŀļpảpēřś яõŧặțë ἁț ťнè șĕļeƈţěδ ïиŧeяνȃľ; ἆ ŝıňḡľĕ ωⱥļłφȃρēř đŏεș иøț řǿţǻτε. Țħê ďзfᾴųľт ìήтėґνậŀ ıș 60 ƨ℮ƈõňďš. Ĉнǟпǵêŝ ťầƙe ēfƒεꞔт ιm₥ēđıẚтέℓγ ⱥƒтeѓ śǻνίńğ.]",

    appListTitle: "[appListTitle][📱 Ćцśтôm ạρφ ļΐšț (ᾶƥp_ℓĭśτ)]",
    appListTip: '[appListTip][Föяmᾱţ: [{"īď":"ťēśţ","иấмě":"Σ×ẫṁρļ℮","įḉōи":"ιςǿ.šνǥ","ƥ𐓚ŧĥ":"ťèşț.ĥŧṁľ"}]]',

    pinnedTitle: "[pinnedTitle][📌 Šťẫяτ ṁéйú φίπńεd ἂρpș (ƒíẋęďÄφpš)]",
    pinnedTip: '[pinnedTip][₣ōѓ₥ǎţ: ["đôḉ","šěтτïήᶃ"]]',

    taskbarTitle: "[taskbarTitle][📎 Ţāŝκɓᾷř pιňñĕ₫ ᾂφpš (fįxзðŢắșƙḅαгΛƥφș)]",
    taskbarTip: '[taskbarTip][Fǿѓ₥ăţ: ["ωǵνэг","śэτŧίηǧ"]. Ôήľỳ ǻƥp ĪÐƨ àřė śтσѓē₫.]',

    desktopTitle: "[desktopTitle][🖥️ Ðēșκτŏφ ıĉòŉŝ (δзšƙťöpÎçóиş)]",
    desktopTip: '[desktopTip][Fôѓmǻť: ["dõḉ","șετţìηģ"]]',

    langTitle: "[langTitle][🌐 Șỳƨţé₥ ŀǡńḡύāḡe (ώꞡ_łàηǵ)]",
    langTip: "[langTip][Vἀļůĕ ìş zн-ċη (Șί₥ρŀìƒìэď Çђίйēƨë), ėή-µš (Ёπɠļĭśħ) òř eŉ-жᾴ (эń-XĄ ƥśėüďõ-ļōɕáĺė).]",
    langOptZh: "[langOptZh][Simplified Chinese (zh-cn)]",
    langOptEn: "[langOptEn][English (en-us)]",
    langOptXa: "[langOptXa][en-XA (pseudo-locale)]",

    btnSave: "[btnSave][💾 Șανè]",
    btnLoad: "[btnLoad][📂 Ŀõàď]",
    btnReset: "[btnReset][↩️ Řêśţóяe đзƒậũļțƨ]",
    btnClear: "[btnClear][🗑️ Çℓėǟѓ]",

    themeInvalidTitle: "[themeInvalidTitle][Ïñνᾂļίδ țĥêṁè]",
    themeInvalidCodeMsg: "[themeInvalidCodeMsg][Îńνἂŀıδ ẄĞ_ċōļøř νàℓϋĕ. Šэŀę¢ţ ḅ öг ш ẚпδ șȧνê.]",
    themeInvalidValueMsg: "[themeInvalidValueMsg][Țнē τĥέṁė νᾰļǘέ ṁúƨŧ вë в õř ẃ.]",

    wallpaperInvalidTitle: "[wallpaperInvalidTitle][Íпνảļǐď ẁảŀĺpầρėґ]",
    wpEmptyMsg: "[wpEmptyMsg][Ŧĥэ ẃǡℓļƥᾃρĕѓ ρᾴτђ ꞔấŉñõт Бè έṁρțŷ.]",
    wpIntervalMsg: "[wpIntervalMsg][Țĥε ώȃļłράpëř ƥἇτĥ ĉáńηŏτ ьe εmφťŷ.]",
    wpNoneMsg: "[wpNoneMsg][Eñťэг ɑŧ ℓéⱥƨť òńë ώἀļľφᾱρěѓ φὰтђ.]",

    jsonErrorTitle: "[jsonErrorTitle][JŞÖŃ eŗгóŗ]",
    saveOkTitle: "[saveOkTitle][Šᾳνėď]",
    wpSavedMsg: "[wgSavedMsg][✅ Şάνэð śµĉĉęŝŝƒùĺłч!]",
    appListSavedMsg: "[appListSavedMsg][✅ Şάνэð śµĉĉęŝŝƒùĺłч!]",
    pinnedSavedMsg: "[pinnedSavedMsg][✅ Şάνэð śµĉĉęŝŝƒùĺłч!]",
    taskbarSavedMsg: "[taskbarSavedMsg][✅ Şάνэð śµĉĉęŝŝƒùĺłч!]",
    desktopSavedMsg: "[desktopSavedMsg][✅ Şάνэð śµĉĉęŝŝƒùĺłч!]",
    langSavedMsg: "[langSavedMsg][✅ Şάνэð śµĉĉęŝŝƒùĺłч!]",

    clearAppListTitle: "[clearAppListTitle][Čĺěẩѓ]",
    clearAppListMsg: "[clearAppListMsg][Άгė ŷõǚ şǜґê ỳõü ωằπţ țø ċłéὰг тħîš?]",
    clearPinnedTitle: "[clearPinnedTitle][Čĺěẩѓ]",
    clearPinnedMsg: "[clearPinnedMsg][Άгė ŷõǚ şǜґê ỳõü ωằπţ țø ċłéὰг тħîš?]",
    clearTaskbarTitle: "[clearTaskbarTitle][Čĺěẩѓ]",
    clearTaskbarMsg: "[clearTaskbarMsg][Άгė ŷõǚ şǜґê ỳõü ωằπţ țø ċłéὰг тħîš?]",
    clearDesktopTitle: "[clearDesktopTitle][Čĺěẩѓ]",
    clearDesktopMsg: "[clearDesktopMsg][Άгė ŷõǚ şǜґê ỳõü ωằπţ țø ċłéὰг тħîš?]",

    langInvalidTitle: "[langInvalidTitle][Ïńνǻŀǐd ļ𐓚лĝǚăĝė]",
    langInvalidMsg: "[langInvalidMsg][Íпνãļįd ľᾃйǧū𐓘ǧéшꞡ_ļẚлĝ ṁǚƨţ ɓэ ᶎђ-ḉл, ĕñ-ùş ōґ ęŉ-xặ.]"
};
