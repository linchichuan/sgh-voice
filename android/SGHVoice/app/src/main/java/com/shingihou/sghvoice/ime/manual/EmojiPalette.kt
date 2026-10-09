package com.shingihou.sghvoice.ime.manual

/** Offline, deliberately small palette. Entries are complete Unicode sequences. */
object EmojiPalette {
    val pages: List<List<String>> = listOf(
        listOf("😀", "😊", "😂", "🥰", "😍", "😎", "🤔", "😭", "😅", "😮", "😴", "🥳",
            "👍", "👎", "👏", "🙏", "💪", "👋", "👌", "🙌", "❤️", "💕", "💖", "💔"),
        listOf("🎉", "🎂", "🎁", "✨", "🔥", "✅", "❌", "💯", "🌸", "🌹", "🌻", "🍀",
            "☀️", "🌈", "🌙", "⭐", "☕", "🍵", "🍺", "🍰", "🍜", "🍣", "🍙", "🍎"),
        listOf("🐶", "🐱", "🐰", "🐼", "🐻", "🦊", "🚗", "🚲", "✈️", "🚆", "🏠", "🏥",
            "💻", "📱", "📷", "📚", "👩‍💻", "👨‍💻", "👨‍👩‍👧‍👦", "🏳️‍🌈", "🇯🇵", "🇹🇼", "🤝", "🫶")
    )

    fun normalizedPage(page: Int): Int = Math.floorMod(page, pages.size)
}
