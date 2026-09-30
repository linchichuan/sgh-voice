package com.shingihou.sghvoice.ime

/** Light, legible recording palettes; saved by stable ID, never by list index. */
enum class VoicePalette(val preferenceValue: String, val argb: Int) {
    MINT("mint", 0xFFE1F8EA.toInt()),
    SKY("sky", 0xFFDFEEFC.toInt()),
    LAVENDER("lavender", 0xFFEDE5FA.toInt()),
    PEACH("peach", 0xFFFCE8DA.toInt()),
    ROSE("rose", 0xFFF9E3EC.toInt()),
    SAND("sand", 0xFFF3EDD9.toInt());

    companion object {
        fun fromPreference(value: String?): VoicePalette =
            entries.firstOrNull { it.preferenceValue == value } ?: MINT
    }
}
